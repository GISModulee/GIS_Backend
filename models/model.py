from sqlalchemy import (
    and_,
    Column,
    Integer,
    String,
    Text,
    JSON,
    DateTime,
    LargeBinary,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Boolean,
    Index,
    UniqueConstraint,
    CheckConstraint,
)
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql import func
from sqlalchemy.orm import foreign
from geoalchemy2 import Geography, Geometry
from models.reference_layer import ReferenceLayer
from models.reference_feature import ReferenceFeature


from database.database import Base
from utils.constants import ALLOWED_MODULE_SLUGS, MAX_MODULE_SLUG_LENGTH


_MODULE_SLUG_ALLOWED_SQL = (
    f"module_slug IN ({', '.join(repr(s) for s in sorted(ALLOWED_MODULE_SLUGS))})"
)


class Layer(Base):
    __tablename__ = "layers"

    id = Column(Integer, primary_key=True)
    case_id = Column(Integer, nullable=False)
    name = Column(String(100), nullable=False)
    layer_type = Column(String(50))
    visible = Column(Boolean, default=True)
    module_slug = Column(String(MAX_MODULE_SLUG_LENGTH), nullable=False, server_default="gis", index=True)
    created_at = Column(DateTime, server_default=func.now())
    file_hash = Column(String(64), nullable=True, index=True)

    features = relationship(
        "Feature",
        back_populates="layer",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    images = relationship(
        "ImageRecord",
        back_populates="layer",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        # No two layers in the same case may share a name. NULL case_id
        # is exempt from this (Postgres treats NULLs as distinct in a
        # unique constraint), but every layer creation path in this app
        # now resolves a real case_id before inserting, so this should
        # never actually be relied on for NULL case_id layers.
        UniqueConstraint("case_id", "name", name="uq_layers_case_id_name"),
        CheckConstraint(
            _MODULE_SLUG_ALLOWED_SQL,
            name="ck_layers_module_slug_allowed",
        ),
    )


class Feature(Base):
    __tablename__ = "features"

    id = Column(Integer, primary_key=True)
    feature_number = Column(Integer, nullable=False)
    layer_id = Column(Integer, ForeignKey("layers.id", ondelete="CASCADE"))
    case_id = Column(Integer, nullable=False)
    module_slug = Column(String(MAX_MODULE_SLUG_LENGTH), nullable=False, server_default="gis", index=True)
    name = Column(Text)
    geom = Column(Geometry(geometry_type="GEOMETRY", srid=4326))

    geometry_type = Column(String, default="Polygon")
    radius = Column(Float)
    properties = Column(JSON, default=dict)

    image_data = Column(LargeBinary)
    # CI user ID (external Central Intelligence user identifier), not a
    # local users foreign key. GIS does not own a local User source of
    # truth; identity is provided by Central Intelligence.
    created_by = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    layer = relationship("Layer", back_populates="features")
    comments = relationship(
        "Comment",
        back_populates="feature",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    __table_args__ = (
        UniqueConstraint(
            "case_id",
            "feature_number",
            name="uq_feature_case_number",
        ),
        CheckConstraint(
            _MODULE_SLUG_ALLOWED_SQL,
            name="ck_features_module_slug_allowed",
        ),
    )


class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True)

    feature_id = Column(
        Integer,
        ForeignKey("features.id", ondelete="CASCADE"),
        nullable=False
    )

    feature_number = Column(Integer, nullable=False)

    case_id = Column(Integer, nullable=False)

    layer_id = Column(
        Integer,
        ForeignKey("layers.id", ondelete="CASCADE"),
        nullable=False
    )

    parent_comment_id = Column(
        Integer,
        ForeignKey("comments.id", ondelete="CASCADE"),
        nullable=True
    )

    root_comment_id = Column(
        Integer,
        ForeignKey("comments.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )

    user_id = Column(
        Integer,
        # CI user ID (external CI user identifier) — intentionally NOT a
        # foreign key to a local users table. Identity comes from CI.
        nullable=False
    )

    comment = Column(Text, nullable=False)

    attachment_data = Column(LargeBinary, nullable=True)
    attachment_filename = Column(String(255), nullable=True)
    attachment_content_type = Column(String(100), nullable=True)

    created_at = Column(DateTime, server_default=func.now())

    feature = relationship("Feature", back_populates="comments")

    replies = relationship(
        "Comment",
        backref=backref("parent", remote_side=[id]),
        foreign_keys=[parent_comment_id],
        cascade="all, delete-orphan",
        single_parent=True,
    )

class ImageRecord(Base):
    __tablename__ = "image_records"

    id = Column(String, primary_key=True, index=True)
    file_hash = Column(String, unique=True, index=True, nullable=False)
    layer_id = Column(Integer, ForeignKey("layers.id", ondelete="CASCADE"), nullable=False, index=True)
    image_data = Column(LargeBinary, nullable=False)
    filename = Column(String, nullable=False)

    content_type = Column(String(50), nullable=True)

    location = Column(Geography(geometry_type="POINT", srid=4326))
    raw_metadata = Column("metadata", JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    layer = relationship("Layer", back_populates="images")


class EmailRecord(Base):

    __tablename__ = "emails"

    case_id = Column(Integer, primary_key=True, index=True)

    email_id = Column(Integer, primary_key=True, index=True)
    email_address = Column(Text, nullable=True)

    ip = Column(String(45), primary_key=True)
    ip_type = Column(String(50), primary_key=True)
    count = Column(Integer, nullable=True)

    risk_level = Column(String(50), nullable=True)
    is_suspicious = Column(Boolean, default=False, nullable=False, server_default="false")
    country = Column(String(100), nullable=True)
    isp = Column(String(255), nullable=True)

    first_seen = Column(DateTime(timezone=True), nullable=True)
    last_seen = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    layer_id = Column(
        Integer,
        ForeignKey("layers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    __table_args__ = (
    )


class EmailTarget(Base):

    __tablename__ = "email_targets"

    case_id = Column(Integer, primary_key=True, index=True)
    target_id = Column(String(100), primary_key=True)

    target_name = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


    emails_ = relationship(
        "EmailTargetEmail",
        back_populates="target",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    dumps = relationship(
        "EmailDump",
        back_populates="target",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
    )


class EmailTargetEmail(Base):

    __tablename__ = "email_target_emails"

    case_id = Column(Integer, primary_key=True, index=True)
    target_id = Column(String(100), primary_key=True)
    email_id = Column(Integer, primary_key=True, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    target = relationship(
        "EmailTarget",
        back_populates="emails_",
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["case_id", "target_id"],
            ["email_targets.case_id", "email_targets.target_id"],
            ondelete="CASCADE",
        ),
    )


class EmailDump(Base):

    __tablename__ = "email_dumps"

    case_id = Column(Integer, primary_key=True)
    target_id = Column(String(100), primary_key=True, index=True)
    dump_id = Column(String(100), primary_key=True)


    name = Column(Text, nullable=True)

    total_emails = Column(Integer, nullable=True)
    malicious_count = Column(Integer, nullable=True)
    unique_senders = Column(Integer, nullable=True)
    unique_recipients = Column(Integer, nullable=True)
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    provider_created_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


    target = relationship(
        "EmailTarget",
        back_populates="dumps",
        primaryjoin="and_(EmailDump.case_id == EmailTarget.case_id, "
        "EmailDump.target_id == EmailTarget.target_id)",
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["case_id", "target_id"],
            ["email_targets.case_id", "email_targets.target_id"],
            ondelete="CASCADE",
            name="fk_email_dumps_target",
        ),
    )


class GeoNewsSearchHistory(Base):
    __tablename__ = "geo_news_search_history"

    id = Column(Integer, primary_key=True)
    # CI user ID (external CI user identifier) — intentionally NOT a
    # foreign key to a local users table. Identity comes from CI.
    user_id = Column(Integer, nullable=False, index=True)
    case_id = Column(Integer, nullable=False, index=True)
    layer_id = Column(Integer, ForeignKey("layers.id", ondelete="CASCADE"), nullable=False, index=True)
    feature_number = Column(Integer, nullable=False)
    feature_name = Column(Text, nullable=False)
    keywords = Column(JSON, default=list, nullable=False)
    start_date = Column(DateTime(timezone=True), nullable=True)
    end_date = Column(DateTime(timezone=True), nullable=True)
    max_results = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ---------------------------------------------------------------------------
# FRS registry tables
#
# These hold the provider's records as real rows, alongside the map layer
# rather than instead of it. The layer answers "where on the map"; the
# person history import deliberately collapses per-detection entries into
# one point per camera, which is right for a map and destroys exactly the
# ordering a route view needs. The registry keeps the raw detections so
# "in what order was this person seen" survives.
#
# They follow the email_dump precedent: composite natural keys built from
# provider ids, composite foreign keys, and real columns for provider
# fields rather than an opaque JSON blob.
# ---------------------------------------------------------------------------


class FrsCamera(Base):
    """One row per camera in the provider's global camera registry.

    Deliberately NOT case-scoped. The provider owns one registry, sends
    no case filter on GET /api/cameras, and the same cameras serve every
    case. A camera imported into three cases is therefore one row here and
    three layers in `layers`; the case-scoped layer is what carries the
    case relationship, and duplicating this row per case would let three
    copies drift apart.

    camera_id is the provider id rather than a surrogate because it is the
    sync key every import resolves against, including the sighting FK.
    """

    __tablename__ = "frs_cameras"

    camera_id = Column(String(100), primary_key=True)
    name = Column(Text, nullable=True)
    zone = Column(String(100), nullable=True)
    status = Column(String(50), nullable=True)

    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    # The provider's own case association, recorded for traceability only.
    # The registry is global, so GIS decides placement; this is not what
    # determines where the camera goes or which case it lands in.
    frs_case_id = Column(String(100), nullable=True)

    # When the camera last moved. Sightings deliberately keep the position
    # they were captured at, so this is the only record that the camera is
    # no longer where its historical sightings say it was.
    coordinates_changed_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class FrsPerson(Base):
    """One row per person the provider holds for a case.

    Case-scoped, unlike cameras: GET /api/persons requires case_id, a
    person's registry membership is a per-case fact, and their sightings
    are evidence within that case.

    person_id is a String even though the provider declares it as an
    integer, for the same reason camera ids are strings: it is a sync key
    and a payload, a fixture or a future upstream change can deliver it as
    a string, and int 12 and "12" must not resolve to two rows.

    The provider's thumbnail is deliberately NOT a column here. It is
    display-only and tens of kilobytes per person, so there is nothing to
    query, join or retain by storing it; it is forwarded verbatim on
    GET .../persons responses instead, and this table stays out of it.
    """

    __tablename__ = "frs_persons"

    case_id = Column(Integer, primary_key=True, index=True)
    person_id = Column(String(100), primary_key=True)

    name = Column(Text, nullable=True)
    organization = Column(Text, nullable=True)

    tags = Column(JSON, nullable=True)
    # The provider's multi-case membership array, stored verbatim. A person
    # can belong to several cases at once, so this is a list rather than
    # the single frs_case_id the camera payload carries.
    provider_case_ids = Column(JSON, nullable=True)

    # Set by the history import, which is what creates the layer. Nullable
    # and SET NULL because a person can sit in the case's person dropdown
    # long before anyone pulls their history, and deleting the layer must
    # not delete the record that the person exists.
    layer_id = Column(
        Integer, ForeignKey("layers.id", ondelete="SET NULL"), nullable=True
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    sightings = relationship(
        "FrsPersonSighting",
        back_populates="person",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class FrsPersonSighting(Base):
    """One row per raw detection. This is the table routes are built on.

    The provider emits no per-detection id, so the durable key is
    (case_id, person_id, video_id, camera_id, started_at) enforced by a
    unique constraint. The surrogate `id` column carries the primary key
    instead, because video_id may be NULL: a `source: "camera"` detection
    is reported with a camera and a timestamp but no video, and dropping
    it used to mean the richest detections never reached the route.
    video_id carries the weight where it exists: one video is one camera
    recording on one clock, so timestamps inside a single video_id are
    mutually consistent. Camera-source detections without a video fall
    back to the provider's own UTC timestamp for ordering.

    latitude/longitude SNAPSHOT the camera's own position as reported on
    this detection. Joining to frs_cameras instead would silently
    relocate historical evidence every time a camera is repositioned,
    rewriting where past sightings were actually captured. The
    disagreement between the snapshot and the current registry position is
    recorded as camera_moved.
    """

    __tablename__ = "frs_person_sightings"

    id = Column(Integer, primary_key=True, autoincrement=True)

    case_id = Column(Integer, nullable=False)
    person_id = Column(String(100), nullable=False)
    video_id = Column(String(100), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=False)

    camera_id = Column(
        String(100),
        ForeignKey("frs_cameras.camera_id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    camera_name = Column(Text, nullable=True)

    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    ended_at = Column(DateTime(timezone=True), nullable=True)
    confidence = Column(Float, nullable=True)
    similarity = Column(Float, nullable=True)
    source = Column(String(100), nullable=True)
    video_filename = Column(Text, nullable=True)

    # True when the camera had a registry position at import time and this
    # entry's coordinates disagreed with it. False means "consistent", and
    # also covers a camera absent from the registry, which has no known
    # position to disagree with.
    camera_moved = Column(
        Boolean, nullable=False, server_default="false"
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    person = relationship(
        "FrsPerson",
        back_populates="sightings",
        primaryjoin="and_(FrsPersonSighting.case_id == FrsPerson.case_id, "
        "FrsPersonSighting.person_id == FrsPerson.person_id)",
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["case_id", "person_id"],
            ["frs_persons.case_id", "frs_persons.person_id"],
            ondelete="CASCADE",
            name="fk_frs_sightings_person",
        ),
        # The idempotency key for both detection kinds. video_id is NULL
        # for camera-source detections, so this is a UNIQUE constraint on
        # nullable columns: PostgreSQL's index treats NULLs as distinct,
        # but upsert_sightings matches on the same key in Python before
        # writing, which is what actually deduplicates a re-import.
        UniqueConstraint(
            "case_id",
            "person_id",
            "video_id",
            "camera_id",
            "started_at",
            name="uq_frs_sightings_detection_key",
        ),
        # The ordered read path: one person's route, in time order.
        Index(
            "ix_frs_sightings_person_started_at",
            "case_id",
            "person_id",
            "started_at",
        ),
    )
