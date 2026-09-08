"""Remove the local `users` table and all foreign keys referencing it.

Central Intelligence (CI) is now the sole source of truth for users and
authentication. GIS no longer owns a local User model or `users` table.
The `features.created_by`, `comments.user_id`, and
`geo_news_search_history.user_id` columns remain plain integer columns
holding external CI user IDs, with no FK to a local `users` table.

This migration is idempotent and safe against both databases that still
have the legacy FKs/table and databases already aligned with the CI-owned
architecture. It only drops each object if it exists.

Steps (PostgreSQL-specific constraint handling):
  1. Drop the FK on geo_news_search_history.case_id -> cases.id (the
     stale local-case FK, if a local `cases` table ever existed).
  2. Drop the FK on features.created_by -> users.id.
  3. Drop the FK on comments.user_id -> users.id.
  4. Drop the FK on geo_news_search_history.user_id -> users.id.
  5. Drop the legacy check constraint users_role_check on `users`.
  6. Drop the `users` table itself.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260904_01"
down_revision = "20260825_01"
branch_labels = None
depends_on = None

SCHEMA = None


def _table_exists(inspector, table):
    return table in set(inspector.get_table_names(schema=SCHEMA))


def _foreign_keys(inspector, table):
    return inspector.get_foreign_keys(table, schema=SCHEMA)


def _drop_fk_if_exists(inspector, table, column, referred):
    """Drop the FK on `table`.`column` -> `referred` if it exists."""
    for fk in _foreign_keys(inspector, table):
        if (
            fk.get("constrained_columns") == [column]
            and fk.get("referred_table") == referred
            and fk.get("name")
        ):
            op.drop_constraint(
                fk["name"],
                table,
                type_="foreignkey",
                schema=SCHEMA,
            )
            return True
    return False


def _recreate_fk_if_possible(inspector, table, column, referred):
    if not _table_exists(inspector, referred):
        return
    exists = any(
        fk.get("constrained_columns") == [column]
        and fk.get("referred_table") == referred
        for fk in _foreign_keys(inspector, table)
    )
    if not exists:
        op.create_foreign_key(
            f"{table}_{column}_fkey",
            table,
            referred,
            [column],
            ["id"],
            source_schema=SCHEMA,
            referent_schema=SCHEMA,
        )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # 1. geo_news_search_history.case_id -> cases.id (stale local-case FK)
    _drop_fk_if_exists(inspector, "geo_news_search_history", "case_id", "cases")

    # 2. features.created_by -> users.id
    _drop_fk_if_exists(inspector, "features", "created_by", "users")

    # 3. comments.user_id -> users.id
    _drop_fk_if_exists(inspector, "comments", "user_id", "users")

    # 4. geo_news_search_history.user_id -> users.id
    _drop_fk_if_exists(inspector, "geo_news_search_history", "user_id", "users")

    if _table_exists(inspector, "users"):
        # 5. Drop the legacy local-auth role CHECK so the table can be
        #    dropped cleanly and because roles now come from CI.
        for ck in inspector.get_check_constraints("users", schema=SCHEMA):
            if ck.get("name") == "users_role_check":
                op.drop_constraint(
                    "users_role_check",
                    "users",
                    type_="check",
                    schema=SCHEMA,
                )
                break

        # 6. Drop the `users` table (all FKs referencing it are gone).
        op.drop_table("users", schema=SCHEMA)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Recreate the `users` table if it was dropped and does not already exist.
    if not _table_exists(inspector, "users"):
        op.create_table(
            "users",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("username", sa.String(length=50), nullable=False, unique=True),
            sa.Column("email", sa.String(length=255), nullable=False, unique=True),
            sa.Column("full_name", sa.String(length=100), nullable=True),
            sa.Column("role", sa.String(length=30), nullable=False),
            sa.Column("created_at", sa.DateTime, server_default=sa.text("now()")),
            schema=SCHEMA,
        )

    # Restore the legacy role CHECK constraint.
    if _table_exists(inspector, "users"):
        already = any(
            ck.get("name") == "users_role_check"
            for ck in inspector.get_check_constraints("users", schema=SCHEMA)
        )
        if not already:
            op.create_check_constraint(
                "users_role_check",
                "users",
                "role IN ('Admin', 'Officer', 'Analyst', 'Viewer')",
                schema=SCHEMA,
            )

    # Re-add the FKs now that `users` exists (and `cases`, if present).
    _recreate_fk_if_possible(inspector, "features", "created_by", "users")
    _recreate_fk_if_possible(inspector, "comments", "user_id", "users")
    _recreate_fk_if_possible(inspector, "geo_news_search_history", "user_id", "users")
    _recreate_fk_if_possible(inspector, "geo_news_search_history", "case_id", "cases")
