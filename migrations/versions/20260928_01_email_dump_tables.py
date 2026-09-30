from alembic import op
import sqlalchemy as sa


revision = "20260928_01"
down_revision = "20260923_01"
branch_labels = None
depends_on = None

SCHEMA = None


def _table_exists(inspector, table: str) -> bool:
    return table in set(inspector.get_table_names(schema=SCHEMA))


def _index_exists(inspector, table: str, name: str) -> bool:
    return name in {index["name"] for index in inspector.get_indexes(table, schema=SCHEMA)}


def _unique_exists(inspector, table: str, name: str) -> bool:
    return name in {
        constraint.get("name")
        for constraint in inspector.get_unique_constraints(table, schema=SCHEMA)
    }


def _create_emails() -> None:
    op.create_table(
        "emails",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("case_id", sa.Integer, nullable=False),
        sa.Column("email_id", sa.Integer, nullable=False),
        sa.Column("email_address", sa.Text, nullable=True),
        sa.Column("ip", sa.String(length=45), nullable=False),
        sa.Column("ip_type", sa.String(length=50), nullable=True),
        sa.Column("count", sa.Integer, nullable=True),
        sa.Column("risk_level", sa.String(length=50), nullable=True),
        sa.Column(
            "is_suspicious",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("country", sa.String(length=100), nullable=True),
        sa.Column("isp", sa.String(length=255), nullable=True),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("case_id", "email_id", "ip", name="uq_emails_case_email_ip"),
        schema=SCHEMA,
    )
    op.create_index("ix_emails_case_id", "emails", ["case_id"], schema=SCHEMA)
    op.create_index("ix_emails_email_id", "emails", ["email_id"], schema=SCHEMA)


def _create_email_targets() -> None:
    op.create_table(
        "email_targets",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("case_id", sa.Integer, nullable=False),
        sa.Column(
            "email_id",
            sa.Integer,
            sa.ForeignKey("emails.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("target_id", sa.String(length=100), nullable=False),
        sa.Column("target_name", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("email_id", "target_id", name="uq_email_targets_email_target"),
        schema=SCHEMA,
    )
    op.create_index("ix_email_targets_case_id", "email_targets", ["case_id"], schema=SCHEMA)
    op.create_index("ix_email_targets_email_id", "email_targets", ["email_id"], schema=SCHEMA)


def _create_email_dumps() -> None:
    op.create_table(
        "email_dumps",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("case_id", sa.Integer, nullable=False),
        sa.Column(
            "target_id",
            sa.Integer,
            sa.ForeignKey("email_targets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("dump_id", sa.String(length=100), nullable=False),
        sa.Column("name", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("target_id", "dump_id", name="uq_email_dumps_target_dump"),
        schema=SCHEMA,
    )
    op.create_index("ix_email_dumps_case_id", "email_dumps", ["case_id"], schema=SCHEMA)
    op.create_index("ix_email_dumps_target_id", "email_dumps", ["target_id"], schema=SCHEMA)


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())

    if not _table_exists(inspector, "emails"):
        _create_emails()

    if not _table_exists(inspector, "email_targets"):
        _create_email_targets()

    if not _table_exists(inspector, "email_dumps"):
        _create_email_dumps()


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())

    for table in ("email_dumps", "email_targets", "emails"):
        if _table_exists(inspector, table):
            op.drop_table(table, schema=SCHEMA)
