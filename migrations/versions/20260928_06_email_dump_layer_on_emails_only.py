"""Drop `layer_id` from `email_targets` and `email_dumps`.

`layer_id` belonged on `emails` and nowhere else. That table maps 1:1 onto
the point features the import creates, so its `layer_id` names the layer
those features live in and the cascade is meaningful. `email_targets` and
`email_dumps` have no geometry of their own: they were storing the *email's*
layer as a proxy, which is not a property of the target or the dump at all
-- a target reported by emails in two different layers has no single
answer, so the stored value was a guess dressed up as a fact.

For a target the link is not lost, only derived. `email_targets.email_id`
is the provider's email identifier, and `emails` is keyed by
`(case_id, email_id, ip)`, so the layer is reachable with a join:

    SELECT DISTINCT e.layer_id
    FROM email_targets AS t
    JOIN emails AS e
      ON e.case_id = t.case_id AND e.email_id = t.email_id
    WHERE t.case_id = :case_id AND t.target_id = :target_id

The lookup has to collapse the fan-out, because one email is one row per IP
and so a target reported by an email with four IPs matches four rows. All
of them carry the same `layer_id`, so `DISTINCT` returns the right answer;
a plain join would report the target once per IP.

Dumps resolve their layer the same way through their target, since
`email_dumps.target_id` still points at `email_targets` on
`(case_id, target_id)`.

This also unblocks saving every target the provider returns. Both columns
were `NOT NULL`, which made a target picked from the dropdown
unstorable, because a dropdown selection names no email and therefore no
layer. With the column gone the dropdown listing can be persisted
directly, and `email_dumps` can cache dumps for a target whose email has
never been imported -- previously that had nowhere to point.

One consequence is accepted deliberately. Deleting a layer still cascades
to `emails`, but no longer to `email_targets` or `email_dumps`, so rows for
a deleted layer's emails are left behind. They are removed here, once, for
the data that already exists. Afterwards the provider is the authority: a
target row is rewritten by the next listing or import of that target, and
an origin-IP import removes the targets and dumps of the emails it rewrites.
"""

from alembic import op
import sqlalchemy as sa
import logging


logger = logging.getLogger("alembic.email_dump")

revision = "20260928_06"
down_revision = "20260928_05"
branch_labels = None
depends_on = None

SCHEMA = None

# layer_id is being removed from these two.
TABLES = ("email_dumps", "email_targets")

# `emails` keeps its column, so the order here is only about not touching it.
ALL_TABLES = ("emails", "email_targets", "email_dumps")


def _schema_args():
    return {"schema": SCHEMA} if SCHEMA else {}


def _insp():
    """A fresh inspector; reflection is cached per instance and these
    steps run DDL between checks."""
    return sa.inspect(op.get_bind())


def _table_exists(inspector, name):
    return inspector.has_table(name, schema=SCHEMA)


def _drop_layer_id(inspector, table):
    """Remove a table's `layer_id`, its index and its foreign key.

    The constraint and the index are dropped explicitly. Dropping the
    column alone would leave the foreign key behind, which is a
    constraint on a column that no longer exists, and Postgres rejects
    that.
    """
    if not _table_exists(inspector, table):
        return

    for fk in inspector.get_foreign_keys(table, schema=SCHEMA):
        if fk["referred_table"] == "layers" and "layer_id" in fk["constrained_columns"]:
            op.drop_constraint(fk["name"], table, type_="foreignkey", **_schema_args())

    for index in inspector.get_indexes(table, schema=SCHEMA):
        if index["column_names"] == ["layer_id"]:
            op.drop_index(index["name"], table, **_schema_args())

    columns = {c["name"] for c in inspector.get_columns(table, schema=SCHEMA)}
    if "layer_id" in columns:
        op.drop_column(table, "layer_id", **_schema_args())


def _delete_orphans():
    """Remove targets and dumps whose email is gone.

    Runs before the columns go, while `emails.layer_id` still identifies
    which rows are about to be cascaded. A target is kept when its email
    still has a row and those rows all name a live layer; anything else
    describes an email that no longer exists on the map, and its dumps go
    with it.
    """
    removed_dumps = op.get_bind().execute(
        sa.text(
            """
            DELETE FROM email_dumps AS d
            WHERE NOT EXISTS (
                SELECT 1
                FROM email_targets AS t
                JOIN emails AS e
                  ON e.case_id = t.case_id AND e.email_id = t.email_id
                JOIN layers AS l ON l.id = e.layer_id
                WHERE t.case_id = d.case_id AND t.target_id = d.target_id
            )
            """
        )
    ).rowcount

    removed_targets = op.get_bind().execute(
        sa.text(
            """
            DELETE FROM email_targets AS t
            WHERE NOT EXISTS (
                SELECT 1
                FROM emails AS e
                JOIN layers AS l ON l.id = e.layer_id
                WHERE e.case_id = t.case_id AND e.email_id = t.email_id
            )
            """
        )
    ).rowcount

    if removed_dumps or removed_targets:
        logger.info(
            "Removed %s target(s) and %s dump(s) with no email left on a layer",
            removed_targets,
            removed_dumps,
        )


def upgrade() -> None:
    inspector = _insp()
    if not _table_exists(inspector, "emails"):
        return

    _delete_orphans()

    for table in TABLES:
        _drop_layer_id(_insp(), table)


def downgrade() -> None:
    """Put the two columns back, nullable.

    There is no layer to restore them from: the value they held was the
    email's, and the row that would supply it may have been deleted in
    the meantime. The columns come back empty and the next import or
    listing repopulates them, which is why they are nullable rather than
    `NOT NULL` as they were before.
    """
    inspector = _insp()
    if not _table_exists(inspector, "emails"):
        return

    for table in TABLES:
        if "layer_id" in {c["name"] for c in _insp().get_columns(table, schema=SCHEMA)}:
            continue
        op.add_column(
            table,
            sa.Column("layer_id", sa.Integer(), nullable=True, **_schema_args()),
        )
        op.create_index(f"ix_{table}_layer_id", table, ["layer_id"], **_schema_args())
        op.create_foreign_key(
            f"fk_{table}_layer",
            table,
            "layers",
            ["layer_id"],
            ["id"],
            ondelete="CASCADE",
            **_schema_args(),
        )
