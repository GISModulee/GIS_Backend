"""Add root comment id for flat replies."""

from alembic import op
import sqlalchemy as sa


revision = "20260824_01"
down_revision = "20260814_01"
branch_labels = None
depends_on = None

SCHEMA = None


def _columns(inspector, table):
    return {column["name"] for column in inspector.get_columns(table, schema=SCHEMA)}


def _indexes(inspector, table):
    return {index["name"] for index in inspector.get_indexes(table, schema=SCHEMA)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "root_comment_id" not in _columns(inspector, "comments"):
        op.add_column(
            "comments",
            sa.Column("root_comment_id", sa.Integer(), nullable=True),
            schema=SCHEMA,
        )
        op.create_foreign_key(
            "fk_comments_root_comment_id_comments",
            "comments",
            "comments",
            ["root_comment_id"],
            ["id"],
            ondelete="CASCADE",
            source_schema=SCHEMA,
            referent_schema=SCHEMA,
        )

    if "ix_comments_root_comment_id" not in _indexes(inspector, "comments"):
        op.create_index(
            "ix_comments_root_comment_id",
            "comments",
            ["root_comment_id"],
            schema=SCHEMA,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "ix_comments_root_comment_id" in _indexes(inspector, "comments"):
        op.drop_index("ix_comments_root_comment_id", table_name="comments", schema=SCHEMA)

    if "root_comment_id" in _columns(inspector, "comments"):
        foreign_keys = inspector.get_foreign_keys("comments", schema=SCHEMA)
        for foreign_key in foreign_keys:
            if (
                foreign_key.get("constrained_columns") == ["root_comment_id"]
                and foreign_key.get("name")
            ):
                op.drop_constraint(
                    foreign_key["name"],
                    "comments",
                    type_="foreignkey",
                    schema=SCHEMA,
                )
                break
        op.drop_column("comments", "root_comment_id", schema=SCHEMA)
