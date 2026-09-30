from alembic import op
import sqlalchemy as sa
import logging


logger = logging.getLogger("alembic.email_dump")

revision = "20260928_07"
down_revision = "20260928_06"
branch_labels = None
depends_on = None

SCHEMA = None

JUNCTION = "email_target_emails"
TARGETS = "email_targets"


def _schema_args():
    return {"schema": SCHEMA} if SCHEMA else {}


def _insp():
    return sa.inspect(op.get_bind())


def _column_names(table):
    return {c["name"] for c in _insp().get_columns(table, schema=SCHEMA)}


def upgrade() -> None:
    inspector = _insp()
    if not inspector.has_table(TARGETS, schema=SCHEMA):
        return

    if not inspector.has_table(JUNCTION, schema=SCHEMA):
        op.create_table(
            JUNCTION,
            sa.Column("case_id", sa.Integer(), nullable=False, **_schema_args()),
            sa.Column("target_id", sa.String(length=100), nullable=False, **_schema_args()),
            sa.Column("email_id", sa.Integer(), nullable=False, **_schema_args()),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                **_schema_args(),
            ),
            sa.ForeignKeyConstraint(
                ["case_id", "target_id"],
                [f"{TARGETS}.case_id", f"{TARGETS}.target_id"],
                ondelete="CASCADE",
                name="fk_email_target_emails_target",
            ),
            sa.PrimaryKeyConstraint("case_id", "target_id", "email_id"),
            **_schema_args(),
        )
        op.create_index(f"ix_{JUNCTION}_case_id", JUNCTION, ["case_id"], **_schema_args())
        op.create_index(f"ix_{JUNCTION}_email_id", JUNCTION, ["email_id"], **_schema_args())

    if "email_id" in _column_names(TARGETS):
        carried = op.get_bind().execute(
            sa.text(
                f"""
                INSERT INTO {JUNCTION} (case_id, target_id, email_id)
                SELECT t.case_id, t.target_id, t.email_id
                FROM {TARGETS} AS t
                WHERE t.email_id IS NOT NULL
                ON CONFLICT DO NOTHING
                """
            )
        ).rowcount
        if carried:
            logger.info("Carried %s existing target/email link(s) into %s", carried, JUNCTION)

        for index in _insp().get_indexes(TARGETS, schema=SCHEMA):
            if index["column_names"] == ["email_id"]:
                op.drop_index(index["name"], TARGETS, **_schema_args())
        op.drop_column(TARGETS, "email_id", **_schema_args())


def downgrade() -> None:
    inspector = _insp()
    if not inspector.has_table(TARGETS, schema=SCHEMA):
        return

    if "email_id" not in _column_names(TARGETS):
        op.add_column(
            TARGETS,
            sa.Column("email_id", sa.Integer(), nullable=True, **_schema_args()),
        )
        op.create_index(f"ix_{TARGETS}_email_id", TARGETS, ["email_id"], **_schema_args())

    if not inspector.has_table(JUNCTION, schema=SCHEMA):
        return

    op.get_bind().execute(
        sa.text(
            f"""
            UPDATE {TARGETS} AS t
            SET email_id = src.email_id
            FROM (
                SELECT case_id, target_id, min(email_id) AS email_id
                FROM {JUNCTION}
                GROUP BY case_id, target_id
            ) AS src
            WHERE src.case_id = t.case_id AND src.target_id = t.target_id
            """
        )
    )

    collapsed = op.get_bind().execute(
        sa.text(
            f"""
            SELECT count(*) FROM (
                SELECT case_id, target_id
                FROM {JUNCTION}
                GROUP BY case_id, target_id
                HAVING count(*) > 1
            ) AS many
            """
        )
    ).scalar()
    if collapsed:
        logger.warning(
            "%s target(s) were reported by more than one email and have been "
            "collapsed to the smallest of their email_ids. This is real data "
            "loss: the other links cannot be represented in this column and "
            "%s is dropped by this migration, so they are gone until the next "
            "import re-walks them from the provider payload.",
            collapsed,
            JUNCTION,
        )

    op.drop_table(JUNCTION, **_schema_args())
