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
    """One Email Dump email and one IP observed for it.

    This is the normalised form of the payload that used to live only in
    `features.properties` for the `email-dump` module. One row per
    (case_id, email_id, ip) pair, so it still maps 1:1 to the IP features
    the import creates.

    The provider's own identifiers are the primary key: there is no
    system-generated `id`. The IP is part of that key because it is the
    grain of the data, not an implementation detail.

    `case_id` is an external Central Intelligence case identifier, not a
    local foreign key: GIS owns no `cases` table (see migration
    20260904_01, which removed the local user and case FKs). It is a
    plain indexed integer here, exactly as on `layers` and `features`.

    `layer_id` points at the GIS layer holding this row's feature, so a
    normalised row can be traced back to the map. It cascades with the
    layer: the row describes that layer's features, so it goes when the
    layer is deleted.
    """

    __tablename__ = "emails"

    case_id = Column(Integer, primary_key=True, index=True)

    # Identifier assigned by the Email Dump Backend, not local.
    email_id = Column(Integer, primary_key=True, index=True)
    email_address = Column(Text, nullable=True)

    ip = Column(String(45), primary_key=True)
    ip_type = Column(String(50), nullable=True)
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

    targets = relationship(
        "EmailTarget",
        back_populates="email",
        # No cascade from the database side any more: email_targets
        # references the provider's email_id, not a row of this table,
        # so an email and its targets are two independent lookups by
        # (case_id, email_id).
        viewonly=True,
        primaryjoin="and_(EmailRecord.case_id == EmailTarget.case_id, "
        "foreign(EmailTarget.email_id) == EmailRecord.email_id)",
    )

    __table_args__ = (
        # The provider's identifiers form the key, so re-importing the
        # same email/IP pair updates the existing row by construction
        # and there is no separate unique constraint to maintain.
    )


class EmailTarget(Base):
    """A target identifier reported for an email by Email Dump.

    The primary key is (case_id, target_id): the provider's own
    identifier, unique within a case, with no system-generated `id` on
    top of it.

    `target_id` is kept as text so the backend never assumes the
    provider's ID type. The provider's target listing returns it as an
    integer while the dumps endpoint leaves it untyped, so storing text
    and forwarding strings keeps both call sites working.

    `email_id` is the provider's email identifier, not a foreign key. It
    used to reference `emails.id`, but an email can have several IP rows
    and so has no single `emails` row to point at; a foreign key would
    force one IP row per target. Deleting an email therefore no longer
    cascades to its targets, and both are re-derived from the provider on
    the next import.

    The row is also written by the case-targets listing, so a target the
    provider reports but whose email has never been imported exists here
    with a null `email_id`. That is why the column is nullable.
    """

    __tablename__ = "email_targets"

    case_id = Column(Integer, primary_key=True, index=True)
    target_id = Column(String(100), primary_key=True)

    # The provider's email_id, indexed for the email -> targets lookup.
    email_id = Column(Integer, nullable=True, index=True)
    target_name = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # No layer_id: a target has no geometry of its own, so it does not
    # belong to a layer. The layer is reached through `email_id` and the
    # `emails` rows, which is a property of the email, not the target.

    email = relationship(
        "EmailRecord",
        back_populates="targets",
        viewonly=True,
        primaryjoin="and_(EmailTarget.case_id == EmailRecord.case_id, "
        "foreign(EmailTarget.email_id) == EmailRecord.email_id)",
    )
    dumps = relationship(
        "EmailDump",
        back_populates="target",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        # (case_id, target_id) is the key, so the provider's identifier
        # is unique within a case by construction.
    )


class EmailDump(Base):
    """A dump belonging to a target.

    The primary key is (case_id, dump_id): the provider's own dump
    identifier, unique within a case. `target_id` is the provider's
    target identifier, and the composite foreign key
    (case_id, target_id) -> email_targets is a real constraint, so
    deleting a target still removes its dumps.
    """

    __tablename__ = "email_dumps"

    case_id = Column(Integer, primary_key=True, index=True)
    dump_id = Column(String(100), primary_key=True)

    # The provider's target identifier. Part of the composite foreign
    # key to email_targets declared in __table_args__, not the identity
    # of this row, which is (case_id, dump_id).
    target_id = Column(String(100), nullable=False, index=True)

    name = Column(Text, nullable=True)

    # Upstream a dump is a bag of counters rather than a labelled
    # record, so these are what the per-case dump listing contributes.
    # A dump has no human-readable name, so `name` remains the best
    # available text for a dropdown entry.
    total_emails = Column(Integer, nullable=True)
    malicious_count = Column(Integer, nullable=True)
    unique_senders = Column(Integer, nullable=True)
    unique_recipients = Column(Integer, nullable=True)
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    # The provider's own creation time, distinct from our `created_at`.
    provider_created_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # No layer_id: a dump is a bag of counters with no geometry, so it
    # does not belong to a layer. Its layer, if one is wanted, is reached
    # through the target and that target's email.

    target = relationship(
        "EmailTarget",
        back_populates="dumps",
        primaryjoin="and_(EmailDump.case_id == EmailTarget.case_id, "
        "EmailDump.target_id == EmailTarget.target_id)",
    )

    __table_args__ = (
        # A real link to the target, on the two columns the target is
        # keyed by. Declared here rather than as a column-level
        # ForeignKey because it spans both.
        ForeignKeyConstraint(
            ["case_id", "target_id"],
            ["email_targets.case_id", "email_targets.target_id"],
            ondelete="CASCADE",
            name="fk_email_dumps_target",
        ),
        # (case_id, dump_id) is the key, so the provider's dump
        # identifier is unique within a case by construction.
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
