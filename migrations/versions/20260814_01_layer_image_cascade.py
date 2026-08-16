"""Cascade image records when deleting layers."""

from alembic import op
import sqlalchemy as sa


revision = "20260814_01"
down_revision = "20260727_01"
branch_labels = None
depends_on = None

SCHEMA = None


def _foreign_keys(inspector, table):
    return inspector.get_foreign_keys(table, schema=SCHEMA)


def _layer_id_fk(inspector):
    for foreign_key in _foreign_keys(inspector, "image_records"):
        if (
            foreign_key.get("constrained_columns") == ["layer_id"]
            and foreign_key.get("referred_table") == "layers"
        ):
            return foreign_key
    return None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    foreign_key = _layer_id_fk(inspector)
    if foreign_key and foreign_key.get("options", {}).get("ondelete") == "CASCADE":
        return

    if foreign_key and foreign_key.get("name"):
        op.drop_constraint(
            foreign_key["name"],
            "image_records",
            type_="foreignkey",
            schema=SCHEMA,
        )

    op.create_foreign_key(
        "fk_image_records_layer_id_layers",
        "image_records",
        "layers",
        ["layer_id"],
        ["id"],
        ondelete="CASCADE",
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    foreign_key = _layer_id_fk(inspector)
    if foreign_key and foreign_key.get("name"):
        op.drop_constraint(
            foreign_key["name"],
            "image_records",
            type_="foreignkey",
            schema=SCHEMA,
        )

    op.create_foreign_key(
        "fk_image_records_layer_id_layers",
        "image_records",
        "layers",
        ["layer_id"],
        ["id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
    )
