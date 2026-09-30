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

DELETE_ORDER = ("email_dumps", "email_targets", "emails")


def _schema_args():
    return {"schema": SCHEMA} if SCHEMA else {}


def _table_exists(inspector, name):
    return inspector.has_table(name, schema=SCHEMA)


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not _table_exists(inspector, "emails"):
        return

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
