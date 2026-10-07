"""Add the durable FRS registry tables.

`frs_cameras`, `frs_persons` and `frs_person_sightings` hold the Face
Recognition System provider's records as real rows, alongside the map
layer rather than instead of it. The map layer answers "where on the
map"; the person history import deliberately collapses per-detection
entries into one point per camera, which is correct for a map and
destroys exactly the ordering a route view needs. `frs_person_sightings`
keeps the raw detections and their time ordering intact.

Purely additive. No existing table is altered and no data is rewritten,
so this can be applied to a populated database without a maintenance
window.

Every table is created behind an existence check, matching the
`email_dump` tables migration, so re-running against a database that
already has some of them is a no-op rather than an "already exists"
failure. The composite foreign keys are created inline with the tables
that reference them, which is why the order below is the dependency
order and the reverse of the drop order in `downgrade`.
"""

from alembic import op
import sqlalchemy as sa


revision = "20261005_01"
down_revision = "20261001_01"
branch_labels = None
depends_on = None

SCHEMA = None


def _table_exists(inspector, table: str) -> bool:
    return table in set(inspector.get_table_names(schema=SCHEMA))


def _create_frs_cameras() -> None:
    op.create_table(
        "frs_cameras",
        sa.Column("camera_id", sa.String(length=100), nullable=False),
        sa.Column("name", sa.Text, nullable=True),
        sa.Column("zone", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=True),
        sa.Column("latitude", sa.Float, nullable=True),
        sa.Column("longitude", sa.Float, nullable=True),
        sa.Column("frs_case_id", sa.String(length=100), nullable=True),
        sa.Column(
            "coordinates_changed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("camera_id"),
        schema=SCHEMA,
    )


def _create_frs_persons() -> None:
    op.create_table(
        "frs_persons",
        sa.Column("case_id", sa.Integer, nullable=False),
        sa.Column("person_id", sa.String(length=100), nullable=False),
        sa.Column("name", sa.Text, nullable=True),
        sa.Column("organization", sa.Text, nullable=True),
        sa.Column("tags", sa.JSON, nullable=True),
        sa.Column("provider_case_ids", sa.JSON, nullable=True),
        sa.Column(
            "layer_id",
            sa.Integer,
            sa.ForeignKey("layers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("case_id", "person_id"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_frs_persons_case_id", "frs_persons", ["case_id"], schema=SCHEMA
    )


def _create_frs_person_sightings() -> None:
    op.create_table(
        "frs_person_sightings",
        sa.Column("case_id", sa.Integer, nullable=False),
        sa.Column("person_id", sa.String(length=100), nullable=False),
        sa.Column("video_id", sa.String(length=100), nullable=False),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column(
            "camera_id",
            sa.String(length=100),
            sa.ForeignKey("frs_cameras.camera_id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("camera_name", sa.Text, nullable=True),
        sa.Column("latitude", sa.Float, nullable=True),
        sa.Column("longitude", sa.Float, nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column("similarity", sa.Float, nullable=True),
        sa.Column("source", sa.String(length=100), nullable=True),
        sa.Column("video_filename", sa.Text, nullable=True),
        sa.Column(
            "camera_moved",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("case_id", "person_id", "video_id", "started_at"),
        sa.ForeignKeyConstraint(
            ["case_id", "person_id"],
            ["frs_persons.case_id", "frs_persons.person_id"],
            ondelete="CASCADE",
            name="fk_frs_sightings_person",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_frs_person_sightings_camera_id",
        "frs_person_sightings",
        ["camera_id"],
        schema=SCHEMA,
    )
    # The ordered read path: one person's route, in time order.
    op.create_index(
        "ix_frs_sightings_person_started_at",
        "frs_person_sightings",
        ["case_id", "person_id", "started_at"],
        schema=SCHEMA,
    )


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())

    if not _table_exists(inspector, "frs_cameras"):
        _create_frs_cameras()

    if not _table_exists(inspector, "frs_persons"):
        _create_frs_persons()

    if not _table_exists(inspector, "frs_person_sightings"):
        _create_frs_person_sightings()


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())

    # Reverse dependency order: sightings reference persons and cameras,
    # persons references layers.
    for table in ("frs_person_sightings", "frs_persons", "frs_cameras"):
        if _table_exists(inspector, table):
            op.drop_table(table, schema=SCHEMA)