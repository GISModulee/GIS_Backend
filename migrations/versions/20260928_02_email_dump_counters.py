from alembic import op
import sqlalchemy as sa


revision = "20260928_02"
down_revision = "20260928_01"
branch_labels = None
depends_on = None

SCHEMA = None

NEW_COLUMNS = (
    ("total_emails", sa.Integer()),
    ("malicious_count", sa.Integer()),
    ("unique_senders", sa.Integer()),
    ("unique_recipients", sa.Integer()),
    ("start_date", sa.DateTime()),
    ("end_date", sa.DateTime()),
    ("provider_created_at", sa.DateTime()),
)


def _table_exists(inspector, name):
    return inspector.has_table(name, schema=SCHEMA)


def _column_names(inspector):
    return {c["name"] for c in inspector.get_columns("email_dumps", schema=SCHEMA)}


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())

    if not _table_exists(inspector, "email_dumps"):
        return

    existing = _column_names(inspector)
    for name, column_type in NEW_COLUMNS:
        if name in existing:
            continue
        kwargs = {"schema": SCHEMA} if SCHEMA else {}
        op.add_column(
            "email_dumps",
            sa.Column(name, column_type, nullable=True, **kwargs),
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())

    if not _table_exists(inspector, "email_dumps"):
        return

    existing = _column_names(inspector)
    for name, _ in reversed(NEW_COLUMNS):
        if name in existing:
            op.drop_column("email_dumps", name, schema=SCHEMA)
