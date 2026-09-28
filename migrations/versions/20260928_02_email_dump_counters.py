"""Add the dump counters reported by the per-case dumps endpoint.

The provider's `EmailDumpSchema` describes a dump with counters, not with
a display name:

  dump_id, total_emails, malicious_count, unique_senders,
  unique_recipients, start_date, end_date, created_at

`email_dumps` previously only stored `dump_id` and `name`, because the
nested target/dump blocks inside the origin-IP payload carry nothing
else. Those counts are the useful part of a dump, so they are now
persisted.

Two naming decisions:

  * `provider_created_at` holds the provider's `created_at`, kept
    distinct from our own audit `created_at` (when GIS first saw the row).
  * `start_date` / `end_date` keep their provider names.

`name` is left in place: a dump has no human-readable label upstream, so
it is the best available dropdown text, and dropping a populated column
would lose data.

Every column is nullable and added only when missing, so this migration
is idempotent and safe to re-run.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260928_02"
down_revision = "20260928_01"
branch_labels = None
depends_on = None

SCHEMA = None

# (column name, postgres type) for the counters added to email_dumps.
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

    # Guarded rather than assumed: a fresh database is built from the
    # models by the first migration, but an existing one already has the
    # table from 20260928_01.
    if not _table_exists(inspector, "email_dumps"):
        return

    existing = _column_names(inspector)
    for name, column_type in NEW_COLUMNS:
        if name in existing:
            continue
        # `schema` is only passed when a schema is actually configured:
        # op.add_column() forwards it straight to the DDL, and passing
        # schema=None is not the same as omitting it.
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
    # Reverse order, and only columns this migration actually added.
    for name, _ in reversed(NEW_COLUMNS):
        if name in existing:
            op.drop_column("email_dumps", name, schema=SCHEMA)
