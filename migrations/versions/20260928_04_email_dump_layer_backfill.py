"""Backfill `layer_id` on the Email Dump tables from the existing layers.

`20260928_03` added `layer_id` to `emails`, `email_targets` and
`email_dumps` and the import now writes it, but the rows that existed
before that migration still carry a null layer. Nothing in the normalised
tables pointed at a layer, so the mapping cannot be read off them; it is
recovered from the `email-dump` layers the import created, whose name is
the email identifier: layer `Email 101` belongs to `email_id` 101.

The backfill is deliberately a join on that name rather than a guess:

  * `emails` is filled per (case_id, email_id). An email has exactly one
    `Email {email_id}` layer, and every IP row of that email belongs to
    it, so the email/IP grain is preserved and no row is left pointing at
    a different email's layer.
  * `email_targets` and `email_dumps` are filled per (case_id,
    email_id) / (case_id, target_id) from the target's own `email_id`,
    which is the same value the import used to attach a target to a
    layer.

Rows with no matching layer keep a null `layer_id`, which is what they
already had: a null is honest about not knowing, and a guess would put a
row on a layer it does not belong to. The columns stay nullable, so no
data is lost by leaving them null.

`layers.name` is not unique, so the join picks the lowest matching id
per (case_id, email_id) rather than failing: an email should have one
layer, and if a duplicate was ever made the earliest one is the one the
import created first.

The old Email Dump layers are not deleted. They hold the features the
import wrote, and `layer_id` now links to them as well; this migration
only adds the link that was missing.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260928_04"
down_revision = "20260928_03"
branch_labels = None
depends_on = None

SCHEMA = None

# The layer name the import gives an email's layer. Kept as a pattern so
# the join stays correct if the prefix ever carries a suffix.
LAYER_NAME_PREFIX = "Email "


def _schema_args():
    return {"schema": SCHEMA} if SCHEMA else {}


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("emails", schema=SCHEMA):
        return

    # A CTE resolving each (case_id, email_id) to its layer once, so the
    # three updates below share the same choice and the name is only
    # parsed a single time.
    resolve_layer = f"""
        WITH email_layer AS (
            SELECT DISTINCT ON (e.case_id, e.email_id)
                   e.case_id,
                   e.email_id,
                   l.id AS layer_id
            FROM emails AS e
            JOIN layers AS l
              ON l.case_id = e.case_id
             AND l.name = '{{prefix}}' || e.email_id::text
            WHERE {{columns}}
            ORDER BY e.case_id, e.email_id, l.id
        )
    """

    # emails: one row per (case_id, email_id, ip), all sharing the email's
    # layer, so this keeps the grain rather than collapsing the rows.
    op.execute(
        sa.text(
            f"""
            {resolve_layer.format(prefix=LAYER_NAME_PREFIX, columns="TRUE")}
            UPDATE emails AS e
            SET layer_id = el.layer_id
            FROM email_layer AS el
            WHERE e.case_id = el.case_id
              AND e.email_id = el.email_id
              AND e.layer_id IS NULL
            """
        )
    )

    # email_targets: the target records the email that reported it.
    op.execute(
        sa.text(
            f"""
            {resolve_layer.format(prefix=LAYER_NAME_PREFIX, columns="TRUE")}
            UPDATE email_targets AS t
            SET layer_id = el.layer_id
            FROM email_layer AS el
            WHERE t.case_id = el.case_id
              AND t.email_id = el.email_id
              AND t.layer_id IS NULL
            """
        )
    )

    # email_dumps: resolved through the target, since a dump is stored
    # against its target and not against an email.
    op.execute(
        sa.text(
            f"""
            {resolve_layer.format(prefix=LAYER_NAME_PREFIX, columns="TRUE")}
            UPDATE email_dumps AS d
            SET layer_id = el.layer_id
            FROM email_targets AS t
            JOIN email_layer AS el
              ON el.case_id = t.case_id
             AND el.email_id = t.email_id
            WHERE t.case_id = d.case_id
              AND t.target_id = d.target_id
              AND d.layer_id IS NULL
            """
        )
    )


def downgrade() -> None:
    """Clear the backfilled links.

    The import writes `layer_id` on every row it touches, so the values
    are not distinguishable from ones written later. Downgrading therefore
    clears the column rather than pretending to restore only the
    pre-backfill state, which is the honest outcome: the next import
    repopulates the rows it owns.
    """
    for table in ("emails", "email_targets", "email_dumps"):
        op.execute(sa.text(f"UPDATE {table} SET layer_id = NULL WHERE layer_id IS NOT NULL"))
