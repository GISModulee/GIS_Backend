"""Add `module_slug` to `layers` and `features`.

Identifies the source module that created a layer/feature. All existing
rows are backfilled to `gis` (the GIS default) before the column is made
NOT NULL, matching the application whitelist enforced by the CHECK
constraints and the SQLAlchemy models.

Steps per table:
  1. Add the column as nullable.
  2. Backfill NULL rows with 'gis'.
  3. Enforce NOT NULL with a server default so future inserts without an
     explicit value still receive 'gis'.
  4. Add an index.
  5. Add a CHECK constraint limiting values to the whitelist.

This migration is idempotent and safe against databases already aligned
with this architecture (nothing is dropped blindly).
"""

from alembic import op
import sqlalchemy as sa

from utils.constants import ALLOWED_MODULE_SLUGS, DEFAULT_MODULE_SLUG, MAX_MODULE_SLUG_LENGTH


revision = "20260923_01"
down_revision = "20260904_01"
branch_labels = None
depends_on = None

# Tables are unqualified in the ORM and may live in either the first
# available search-path schema or public. None keeps migration behavior
# aligned with the application's configured search path.
SCHEMA = None

# Keep the SQL literal in lock-step with ALLOWED_MODULE_SLUGS so the DB
# constraint and the application whitelist cannot drift apart.
_SQL_ALLOWED = ", ".join(
    f"'{slug}'" for slug in sorted(ALLOWED_MODULE_SLUGS)
)


def _columns(inspector, table):
    return {column["name"] for column in inspector.get_columns(table, schema=SCHEMA)}


def _add_module_slug(table: str) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    columns = _columns(inspector, table)
    if "module_slug" not in columns:
        op.add_column(
            table,
            sa.Column("module_slug", sa.String(length=MAX_MODULE_SLUG_LENGTH), nullable=True),
            schema=SCHEMA,
        )

    # Backfill existing rows before enforcing NOT NULL.
    op.execute(
        sa.text(
            f"UPDATE {table} SET module_slug = '{DEFAULT_MODULE_SLUG}' "
            f"WHERE module_slug IS NULL"
        )
    )

    op.alter_column(
        table,
        "module_slug",
        existing_type=sa.String(length=MAX_MODULE_SLUG_LENGTH),
        nullable=False,
        server_default=DEFAULT_MODULE_SLUG,
        schema=SCHEMA,
    )

    indexes = {index["name"] for index in inspector.get_indexes(table, schema=SCHEMA)}
    index_name = f"ix_{table}_module_slug"
    if index_name not in indexes:
        op.create_index(index_name, table, ["module_slug"], schema=SCHEMA)

    constraints = {
        constraint.get("name")
        for constraint in inspector.get_check_constraints(table, schema=SCHEMA)
    }
    constraint_name = f"ck_{table}_module_slug_allowed"
    if constraint_name not in constraints:
        op.create_check_constraint(
            constraint_name,
            table,
            f"module_slug IN ({_SQL_ALLOWED})",
            schema=SCHEMA,
        )


def _drop_module_slug(table: str) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    constraint_name = f"ck_{table}_module_slug_allowed"
    constraints = {
        constraint.get("name")
        for constraint in inspector.get_check_constraints(table, schema=SCHEMA)
    }
    if constraint_name in constraints:
        op.drop_constraint(
            constraint_name,
            table,
            type_="check",
            schema=SCHEMA,
        )

    index_name = f"ix_{table}_module_slug"
    indexes = {index["name"] for index in inspector.get_indexes(table, schema=SCHEMA)}
    if index_name in indexes:
        op.drop_index(index_name, table_name=table, schema=SCHEMA)

    columns = _columns(inspector, table)
    if "module_slug" in columns:
        op.drop_column(table, "module_slug", schema=SCHEMA)


def upgrade() -> None:
    _add_module_slug("layers")
    _add_module_slug("features")


def downgrade() -> None:
    _drop_module_slug("features")
    _drop_module_slug("layers")