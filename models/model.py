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
