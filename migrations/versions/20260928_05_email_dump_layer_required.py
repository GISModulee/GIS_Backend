"""Require `layer_id` on the Email Dump tables and drop the rows that have no layer.

Every imported email is already a layer: the import creates one
`Email {email_id}` layer per email and points that email's point features
at it. `layer_id` on the three normalised tables records that same layer,
so a row can always be traced back to the map and an email is visible in
the layers list rather than only in SQL.

The column is now NOT NULL, which turns "should be linked to a layer"
from a convention into a constraint the database enforces. A row that
does not name a layer is not describing anything on the map.

Rows that cannot satisfy that are removed rather than left dangling. They
are only ever created by an import that resolved a layer, so a null
`layer_id` means the layer was deleted out from under the row, or the row
predates the column. A row in that state describes no layer, no features
and no provider target, and the import recreates all of it from the
provider on the next run, so keeping it would only preserve a broken
reference. The deletion is reported per table rather than done silently.

The foreign keys already cascade, so deleting a layer cleans up its rows
on the way out and the two rules agree.
"""

from alembic import op
import sqlalchemy as sa
import logging


logger = logging.getLogger("alembic.email_dump")


revision = "20260928_05"
down_revision = "20260928_04"
branch_labels = None
depends_on = None

SCHEMA = None

TABLES = ("email_dumps", "email_targets", "emails")

# The order matters: a dump is removed before its target, and a target
# before its email, so no statement has to work around a reference to a
# row that is about to disappear. The foreign keys are deferred, not
# dropped, for the same reason.
DELETE_ORDER = ("email_dumps", "email_targets", "emails")


def _schema_args():
    return {"schema": SCHEMA} if SCHEMA else {}


def _table_exists(inspector, name):
    return inspector.has_table(name, schema=SCHEMA)


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not _table_exists(inspector, "emails"):
        return

    # Children first, and a row is removed when it names no layer *or*
    # names one that is gone. The second case cannot normally arise
    # because the foreign key cascades, but a row inserted while the
    # constraint was absent could name a layer that was never created,
    # and leaving it would fail the NOT NULL assertion below for a reason
    # that has nothing to do with nulls.
    for table in DELETE_ORDER:
        count = op.get_bind().execute(
            sa.text(
                f"""
                SELECT count(*)
                FROM {table} AS t
                WHERE t.layer_id IS NULL
                   OR NOT EXISTS (
                       SELECT 1 FROM layers AS l WHERE l.id = t.layer_id
                   )
                """
            )
        ).scalar()
        if count:
            logger.info(
                "Deleting %s Email Dump row(s) in %s that name no existing layer",
                count,
                table,
            )
            op.get_bind().execute(
                sa.text(
                    f"""
                    DELETE FROM {table} AS t
                    WHERE t.layer_id IS NULL
                       OR NOT EXISTS (
                           SELECT 1 FROM layers AS l WHERE l.id = t.layer_id
                       )
                    """
                )
            )

    for table in DELETE_ORDER:
        op.alter_column(
            table,
            "layer_id",
            nullable=False,
            existing_type=sa.Integer(),
            **_schema_args(),
        )


def downgrade() -> None:
    """Allow rows with no layer again.

    The rows deleted on the way up are not recreated: their layer is gone,
    so there is nothing to restore them against. They return on the next
    import from the provider.
    """
    inspector = sa.inspect(op.get_bind())
    if not _table_exists(inspector, "emails"):
        return

    for table in DELETE_ORDER:
        op.alter_column(
            table,
            "layer_id",
            nullable=True,
            existing_type=sa.Integer(),
            **_schema_args(),
        )
