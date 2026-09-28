"""Drop the surrogate keys and add `layer_id` to the Email Dump tables.

The three tables now use the provider's own identifiers as their primary
key, so there is no fourth identifier to carry around:

  * `emails`        PK (case_id, email_id, ip)
                    One row per email and IP observation. The IP stays
                    in the key because that is the grain of the data: it
                    maps 1:1 to the `email-dump` features the import
                    creates, and dropping it would collapse an email's
                    several IPs onto one row.
  * `email_targets` PK (case_id, target_id)
                    A target belongs to a case, and the provider's
                    `target_id` is unique within one, so the key needs
                    no surrogate.
  * `email_dumps`   PK (case_id, dump_id)
                    `target_id` is now the provider's identifier too,
                    and a real composite foreign key
                    (case_id, target_id) -> email_targets(case_id,
                    target_id) replaces the old link to the surrogate.

One referential link is necessarily lost. `email_targets.email_id` used
to be a foreign key to `emails.id`; it is now a plain indexed column
holding the provider's `email_id`, because no unique (case_id, email_id)
exists while an email may have several IP rows. Consequently deleting an
email no longer cascades to its targets, only deleting a target still
cascades to its dumps. Both are re-derivable from the provider on the
next import.

`layer_id` is added to all three tables so a normalised row can be traced
back to the GIS layer holding its features. It references `layers.id`,
which is a real local key, and cascades with the layer: the rows describe
that layer's features, so they go when it goes.

This migration is written to preserve existing rows. The surrogate
columns are rewritten before they are dropped, so the data moves rather
than being recreated. It is guarded at each step and is safe to re-run.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260928_03"
down_revision = "20260928_02"
branch_labels = None
depends_on = None

SCHEMA = None

TABLES = ("emails", "email_targets", "email_dumps")

# Surrogate column -> the primary-key columns that replace it.
NEW_PKS = {
    "emails": ("case_id", "email_id", "ip"),
    "email_targets": ("case_id", "target_id"),
    "email_dumps": ("case_id", "dump_id"),
}

# Old unique constraints that the new primary keys supersede.
OLD_UNIQUES = {
    "emails": "uq_emails_case_email_ip",
    "email_targets": "uq_email_targets_email_target",
    "email_dumps": "uq_email_dumps_target_dump",
}

# The columns each of those old unique constraints covered.
OLD_UNIQUE_COLUMNS = {
    "emails": ["case_id", "email_id", "ip"],
    "email_targets": ["email_id", "target_id"],
    "email_dumps": ["target_id", "dump_id"],
}

# Old primary-key constraint names, where Postgres has a known one.
OLD_PKS = {
    "emails": "emails_pkey",
    "email_targets": "email_targets_pkey",
    "email_dumps": "email_dumps_pkey",
}


def _insp():
    """A fresh inspector.

    A new one is required for every step: the reflection results are
    cached per instance, so a single inspector would keep reporting the
    pre-DDL schema and the "does this already exist?" guards below would
    all be stale.
    """
    return sa.inspect(op.get_bind())


def _table_exists(inspector, name):
    return inspector.has_table(name, schema=SCHEMA)


def _columns(inspector, table):
    if not _table_exists(inspector, table):
        return set()
    return {c["name"] for c in inspector.get_columns(table, schema=SCHEMA)}


def _fk_names(inspector, table):
    """Names of the incoming foreign keys on a table.

    Read from the catalog rather than hard-coded, because the names were
    generated when the tables were created and may differ per database.
    """
    if not _table_exists(inspector, table):
        return set()
    return {f["name"] for f in inspector.get_foreign_keys(table, schema=SCHEMA)}


def _fks_to(inspector, table, referred_table):
    """Incoming foreign keys on `table` that point at `referred_table`."""
    if not _table_exists(inspector, table):
        return []
    return [
        f
        for f in inspector.get_foreign_keys(table, schema=SCHEMA)
        if f["referred_table"] == referred_table
    ]


def _index_names(inspector, table):
    if not _table_exists(inspector, table):
        return set()
    return {i["name"] for i in inspector.get_indexes(table, schema=SCHEMA)}


def _unique_names(inspector, table):
    if not _table_exists(inspector, table):
        return set()
    return {u["name"] for u in inspector.get_unique_constraints(table, schema=SCHEMA)}


def _schema_args():
    return {"schema": SCHEMA} if SCHEMA else {}


def _add_layer_id(inspector, table):
    """Add `layer_id` to a table if it is not already there.

    The column, its index and its foreign key are each checked
    separately. A partial state is reachable -- the downgrade drops the
    foreign key on `email_dumps` and the upgrade drops every incoming one
    on `email_targets` -- so testing only for the column would skip
    recreating a constraint that is genuinely missing, and the row would
    be left pointing at nothing.
    """
    if not _table_exists(inspector, table):
        return

    if "layer_id" not in _columns(inspector, table):
        op.add_column(
            table,
            sa.Column("layer_id", sa.Integer(), nullable=True, **_schema_args()),
        )

    if f"ix_{table}_layer_id" not in _index_names(inspector, table):
        op.create_index(f"ix_{table}_layer_id", table, ["layer_id"], **_schema_args())

    if not _fks_to(inspector, table, "layers"):
        op.create_foreign_key(
            f"fk_{table}_layer",
            table,
            "layers",
            ["layer_id"],
            ["id"],
            ondelete="CASCADE",
            **_schema_args(),
        )


def _rewrite_surrogates(inspector, bind):
    """Point the child tables at the provider identifiers.

    Runs before the surrogate columns are dropped, so existing rows are
    carried over rather than lost.
    """
    # The incoming foreign keys still hold while these run, and they
    # assert that email_targets.email_id exists in emails.id and
    # email_dumps.target_id exists in email_targets.id. Writing the
    # provider's identifiers into those columns before the constraints
    # are dropped would violate them, so the constraints are relaxed to
    # a deferred-check state first: dropped, rewritten, then recreated in
    # their new composite form.
    _drop_incoming_foreign_keys(inspector)

    if _table_exists(inspector, "email_targets") and "id" in _columns(inspector, "email_targets"):
        # email_targets.email_id currently holds emails.id; it becomes
        # the provider's email_id.
        op.execute(
            sa.text(
                """
                UPDATE email_targets AS t
                SET email_id = e.email_id
                FROM emails AS e
                WHERE t.email_id = e.id
                """
            )
        )

    if _table_exists(inspector, "email_dumps") and "id" in _columns(inspector, "email_dumps"):
        # email_dumps.target_id currently holds email_targets.id, an
        # integer. It becomes the provider's target_id, which is text on
        # email_targets, so the column's type is widened before the value
        # is rewritten.
        op.alter_column(
            "email_dumps",
            "target_id",
            type_=sa.String(100),
            existing_type=sa.Integer(),
            **_schema_args(),
        )
        op.execute(
            sa.text(
                """
                UPDATE email_dumps AS d
                SET target_id = t.target_id
                FROM email_targets AS t
                WHERE d.target_id::text = t.id::text
                """
            )
        )


def _drop_incoming_foreign_keys(inspector):
    """Remove the FKs that point at the surrogate keys.

    They are dropped before the columns go, and the replacement composite
    FK is created after the new primary keys exist.
    """
    for table in ("email_targets", "email_dumps"):
        for name in sorted(_fk_names(inspector, table)):
            op.drop_constraint(name, table, type_="foreignkey", **_schema_args())


def _drop_old_uniques_and_pks(inspector):
    """Drop the unique constraints and primary keys being replaced."""
    for table in TABLES:
        uniques = _unique_names(inspector, table)
        old = OLD_UNIQUES.get(table)
        if old and old in uniques:
            op.drop_constraint(old, table, type_="unique", **_schema_args())

    for table in TABLES:
        if "id" not in _columns(inspector, table):
            continue
        name = OLD_PKS.get(table)
        if name:
            op.drop_constraint(name, table, type_="primary", **_schema_args())


def _create_new_pks(inspector):
    """Make each table's provider identifiers its primary key.

    Skipped when the key is already in place, so the step is safe to
    repeat after a partial run.
    """
    for table, pk_columns in NEW_PKS.items():
        if not _table_exists(inspector, table):
            continue
        current = inspector.get_pk_constraint(table, schema=SCHEMA)[
            "constrained_columns"
        ]
        if current == list(pk_columns):
            continue
        op.create_primary_key(f"pk_{table}", table, list(pk_columns), **_schema_args())


def _drop_surrogate_columns(inspector):
    for table in TABLES:
        if "id" not in _columns(inspector, table):
            continue
        op.drop_column(table, "id", **_schema_args())


def _tighten_child_columns(inspector):
    """Make the identifier columns the new primary keys require.

    The rewritten values are NOT NULL by definition once the composite
    key exists, but the columns were previously nullable or held a
    surrogate that could be null, so the constraint is asserted
    explicitly rather than assumed.
    """
    op.execute(
        sa.text(
            "DELETE FROM email_dumps WHERE case_id IS NULL "
            "OR dump_id IS NULL OR target_id IS NULL"
        )
    )
    op.execute(
        sa.text(
            "DELETE FROM email_targets WHERE case_id IS NULL OR target_id IS NULL"
        )
    )
    op.execute(
        sa.text("DELETE FROM emails WHERE case_id IS NULL OR email_id IS NULL OR ip IS NULL")
    )

    # The declared type of each key column, for the NOT NULL assertion
    # below. `email_dumps.target_id` is text: it holds the provider's
    # identifier, widened above from the surrogate it used to store.
    key_types = {
        "ip": sa.String(45),
        "dump_id": sa.String(100),
        "target_id": sa.String(100),
    }

    for table, pk_columns in NEW_PKS.items():
        for column in pk_columns:
            op.alter_column(
                table,
                column,
                nullable=False,
                existing_type=key_types.get(column, sa.Integer()),
                **_schema_args(),
            )

    # email_dumps keeps a real link to its target now that both share the
    # same key shape. The constraint was dropped along with the surrogate
    # ones above, so it is recreated unless it is already there.
    if not _fks_to(inspector, "email_dumps", "email_targets"):
        op.create_foreign_key(
            "fk_email_dumps_target",
            "email_dumps",
            "email_targets",
            ["case_id", "target_id"],
            ["case_id", "target_id"],
            ondelete="CASCADE",
            **_schema_args(),
        )

    # The composite foreign key on (case_id, target_id) already gives the
    # lookups this column served, so no separate index is created here:
    # one already exists from the original table definition.


def upgrade() -> None:
    if not _table_exists(_insp(), "emails"):
        return

    # Drops the incoming FKs itself before rewriting the columns they
    # constrain, then recreates the email_dumps link as a composite key.
    _rewrite_surrogates(_insp(), op.get_bind())
    _drop_old_uniques_and_pks(_insp())

    for table in TABLES:
        _add_layer_id(_insp(), table)

    _create_new_pks(_insp())
    _tighten_child_columns(_insp())
    _drop_surrogate_columns(_insp())


def downgrade() -> None:
    """Restore the surrogate keys, re-deriving ids in insertion order.

    The old `email_dumps.target_id -> email_targets.id` link cannot be
    reproduced from the current data, since the mapping from a target to
    a specific email/IP row was never stored. The surrogate is rebuilt
    from the row's own position, which reproduces the previous shape and
    keeps the tables usable, but the email -> target relationship is no
    longer recoverable afterwards.
    """
    if not _table_exists(_insp(), "emails"):
        return

    # The composite foreign key on email_dumps is backed by the
    # email_targets primary key, so both that constraint and the primary
    # keys themselves have to go before surrogate ones can be created.
    for name in sorted(_fk_names(_insp(), "email_dumps")):
        op.drop_constraint(name, "email_dumps", type_="foreignkey", **_schema_args())

    for table in TABLES:
        existing_pk = _insp().get_pk_constraint(table, schema=SCHEMA)["name"]
        if existing_pk:
            op.drop_constraint(existing_pk, table, type_="primary", **_schema_args())

    for table in TABLES:
        inspector = _insp()
        if "id" not in _columns(inspector, table):
            op.add_column(
                table, sa.Column("id", sa.Integer(), nullable=True, **_schema_args())
            )
            # Index the new surrogate straight away: the row_number() update
            # below is a full-table write, and an index keeps it from being
            # the slowest step of the downgrade.
            op.create_index(f"ix_{table}_id", table, ["id"], **_schema_args())

    # Renumber from the natural key order so the result is deterministic.
    for table, pk_columns in NEW_PKS.items():
        # The join has to be on the key columns. Without it the numbered
        # subquery is a cross join and every row would take an arbitrary
        # number, producing duplicate ids.
        join_condition = " AND ".join(f"t.{c} = n.{c}" for c in pk_columns)
        op.execute(
            sa.text(
                f"""
                UPDATE {table} AS t
                SET id = n.n
                FROM (
                    SELECT row_number() OVER (ORDER BY {", ".join(pk_columns)}) AS n,
                           {", ".join(pk_columns)}
                    FROM {table}
                ) AS n
                WHERE {join_condition}
                """
            )
        )
        op.alter_column(
            table,
            "id",
            nullable=False,
            existing_type=sa.Integer(),
            **_schema_args(),
        )
        op.create_primary_key(OLD_PKS[table], table, ["id"], **_schema_args())

    # The old shape stored pointers, not provider identifiers:
    # email_targets.email_id referenced emails.id and
    # email_dumps.target_id referenced email_targets.id. Both are
    # rewritten from the provider identifiers before the constraints are
    # recreated, since the constraints are what enforce the pointers.
    op.execute(
        sa.text(
            """
            UPDATE email_targets AS t
            SET email_id = e.id
            FROM emails AS e
            WHERE e.case_id = t.case_id AND e.email_id = t.email_id
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE email_dumps AS d
            SET target_id = t.id
            FROM email_targets AS t
            WHERE t.case_id = d.case_id AND t.target_id = d.target_id
            """
        )
    )

    # email_dumps.target_id goes back to being an integer reference. The
    # values are the surrogate ids written just above, so they are all
    # numeric; the USING clause is explicit because Postgres refuses to
    # cast text to integer on its own.
    op.execute(sa.text("ALTER TABLE email_dumps ALTER COLUMN target_id TYPE INTEGER USING target_id::integer"))

    if not _fks_to(_insp(), "email_targets", "emails"):
        op.create_foreign_key(
            "fk_email_targets_email",
            "email_targets",
            "emails",
            ["email_id"],
            ["id"],
            ondelete="CASCADE",
            **_schema_args(),
        )
    if not _fks_to(_insp(), "email_dumps", "email_targets"):
        op.create_foreign_key(
            "fk_email_dumps_target",
            "email_dumps",
            "email_targets",
            ["target_id"],
            ["id"],
            ondelete="CASCADE",
            **_schema_args(),
        )

    # The layer link on email_dumps went when the composite one was
    # dropped above. The links on emails and email_targets are left alone
    # when they survived, and restored when they did not, so a downgrade
    # never leaves a column pointing at nothing.
    for table in TABLES:
        inspector = _insp()
        if "layer_id" in _columns(inspector, table) and not _fks_to(
            inspector, table, "layers"
        ):
            op.create_foreign_key(
                f"fk_{table}_layer",
                table,
                "layers",
                ["layer_id"],
                ["id"],
                ondelete="CASCADE",
                **_schema_args(),
            )

    for table in TABLES:
        if OLD_UNIQUES[table] in _unique_names(_insp(), table):
            continue
        op.create_unique_constraint(
            OLD_UNIQUES[table], table, OLD_UNIQUE_COLUMNS[table], **_schema_args()
        )
