"""Let camera-source detections reach frs_person_sightings.

The FRS provider reports two kinds of history detection. `source:
"video"` entries carry a video_id plus a started_at. `source: "camera"`
entries carry a camera, a started_at and — critically — the coordinates,
but no video_id, and before this migration that made them unrestorable:
video_id was a NOT NULL member of the primary key, so the detections most
worth mapping were exactly the ones dropped from the registry and the
route.

This migration swaps the composite primary key for a surrogate `id` and
makes `video_id` nullable, so both kinds share one table. Idempotency
moves to a unique constraint on (case_id, person_id, video_id, camera_id,
started_at): the video detected on one clip and the person seen at one
camera at one instant are the two natural keys, and `upsert_sightings`
matches on the same tuple in Python before writing. PostgreSQL treats the
NULLs in that unique index as distinct — the constraint alone cannot
deduplicate two camera-source rows — so the application-level match is
what actually keeps a re-import from duplicating; the constraint is the
belt for the non-null combinations.

Backwards-compatible forward: a populated database keeps its rows and the
video-source ordering still carries the full weight of the old key. The
downgrade refuses to run once a NULL video_id row exists, because
restoring a NOT NULL primary key column over data that can never satisfy
it would corrupt the table rather than reverse it.
"""

from alembic import op
import sqlalchemy as sa


revision = "20261006_01"
down_revision = "20261005_01"
branch_labels = None
depends_on = None

SCHEMA = None

TABLE = "frs_person_sightings"


def _table_exists(inspector, table: str) -> bool:
    return table in set(inspector.get_table_names(schema=SCHEMA))


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not _table_exists(inspector, TABLE):
        return

    columns = {c["name"] for c in inspector.get_columns(TABLE, schema=SCHEMA)}
    if "id" in columns:
        return

    op.add_column(
        TABLE,
        sa.Column("id", sa.Integer(), sa.Identity(), nullable=False),
        schema=SCHEMA,
    )
    op.drop_constraint(
        "frs_person_sightings_pkey", TABLE, type_="primary", schema=SCHEMA
    )
    op.alter_column(
        TABLE,
        "video_id",
        existing_type=sa.String(length=100),
        nullable=True,
        schema=SCHEMA,
    )
    op.create_unique_constraint(
        "uq_frs_sightings_detection_key",
        TABLE,
        ["case_id", "person_id", "video_id", "camera_id", "started_at"],
        schema=SCHEMA,
    )
    op.create_primary_key(
        "frs_person_sightings_pkey", TABLE, ["id"], schema=SCHEMA
    )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not _table_exists(inspector, TABLE):
        return

    columns = {c["name"] for c in inspector.get_columns(TABLE, schema=SCHEMA)}
    if "id" not in columns:
        return

    existing_nulls = op.get_bind().exec_driver_sql(
        "SELECT count(*) FROM frs_person_sightings WHERE video_id IS NULL"
    ).scalar()
    if existing_nulls:
        raise RuntimeError(
            "cannot downgrade frs_person_sightings: "
            "camera-source rows (video_id IS NULL) exist"
        )

    op.drop_constraint(
        "uq_frs_sightings_detection_key", TABLE, type_="unique", schema=SCHEMA
    )
    op.drop_constraint(
        "frs_person_sightings_pkey", TABLE, type_="primary", schema=SCHEMA
    )
    op.alter_column(
        TABLE,
        "video_id",
        existing_type=sa.String(length=100),
        nullable=False,
        schema=SCHEMA,
    )
    op.drop_column(TABLE, "id", schema=SCHEMA)
    op.create_primary_key(
        "frs_person_sightings_pkey",
        TABLE,
        ["case_id", "person_id", "video_id", "started_at"],
        schema=SCHEMA,
    )