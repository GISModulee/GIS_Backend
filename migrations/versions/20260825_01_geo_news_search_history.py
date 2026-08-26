"""Add geo news search history metadata."""

from alembic import op
import sqlalchemy as sa


revision = "20260825_01"
down_revision = "20260824_01"
branch_labels = None
depends_on = None

SCHEMA = None


def _tables(inspector):
    return set(inspector.get_table_names(schema=SCHEMA))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "geo_news_search_history" in _tables(inspector):
        return

    op.create_table(
        "geo_news_search_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("layer_id", sa.Integer(), nullable=False),
        sa.Column("feature_number", sa.Integer(), nullable=False),
        sa.Column("feature_name", sa.Text(), nullable=False),
        sa.Column("keywords", sa.JSON(), nullable=False),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("max_results", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["layer_id"], ["layers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.create_index("ix_geo_news_search_history_user_id", "geo_news_search_history", ["user_id"], schema=SCHEMA)
    op.create_index("ix_geo_news_search_history_case_id", "geo_news_search_history", ["case_id"], schema=SCHEMA)
    op.create_index("ix_geo_news_search_history_layer_id", "geo_news_search_history", ["layer_id"], schema=SCHEMA)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "geo_news_search_history" not in _tables(inspector):
        return

    op.drop_index("ix_geo_news_search_history_layer_id", table_name="geo_news_search_history", schema=SCHEMA)
    op.drop_index("ix_geo_news_search_history_case_id", table_name="geo_news_search_history", schema=SCHEMA)
    op.drop_index("ix_geo_news_search_history_user_id", table_name="geo_news_search_history", schema=SCHEMA)
    op.drop_table("geo_news_search_history", schema=SCHEMA)
