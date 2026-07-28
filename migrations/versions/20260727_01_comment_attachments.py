"""Align comment attachments and layer import hashes with ORM models."""

from alembic import op
import sqlalchemy as sa


revision = "20260727_01"
down_revision = None
branch_labels = None
depends_on = None

# Tables are unqualified in the ORM and may live in either the first
# available search-path schema or public. None keeps migration behavior
# aligned with the application's configured search path.
SCHEMA = None


def _columns(inspector, table):
    return {column["name"] for column in inspector.get_columns(table, schema=SCHEMA)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    comment_columns = _columns(inspector, "comments")
    if "attachment_data" not in comment_columns:
        if "image_data" in comment_columns:
            op.alter_column(
                "comments",
                "image_data",
                new_column_name="attachment_data",
                existing_type=sa.LargeBinary(),
                schema=SCHEMA,
            )
        else:
            op.add_column(
                "comments",
                sa.Column("attachment_data", sa.LargeBinary(), nullable=True),
                schema=SCHEMA,
            )
    if "attachment_filename" not in comment_columns:
        op.add_column(
            "comments",
            sa.Column("attachment_filename", sa.String(length=255), nullable=True),
            schema=SCHEMA,
        )
    if "attachment_content_type" not in comment_columns:
        op.add_column(
            "comments",
            sa.Column("attachment_content_type", sa.String(length=100), nullable=True),
            schema=SCHEMA,
        )

    layer_columns = _columns(inspector, "layers")
    if "file_hash" not in layer_columns:
        op.add_column(
            "layers",
            sa.Column("file_hash", sa.String(length=64), nullable=True),
            schema=SCHEMA,
        )
    indexes = {index["name"] for index in inspector.get_indexes("layers", schema=SCHEMA)}
    if "ix_layers_file_hash" not in indexes:
        op.create_index("ix_layers_file_hash", "layers", ["file_hash"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_index("ix_layers_file_hash", table_name="layers", schema=SCHEMA)
    op.drop_column("layers", "file_hash", schema=SCHEMA)
    op.drop_column("comments", "attachment_content_type", schema=SCHEMA)
    op.drop_column("comments", "attachment_filename", schema=SCHEMA)
    op.alter_column(
        "comments",
        "attachment_data",
        new_column_name="image_data",
        existing_type=sa.LargeBinary(),
        schema=SCHEMA,
    )
