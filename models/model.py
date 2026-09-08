from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    JSON,
    DateTime,
    LargeBinary,
    Float,
    ForeignKey,
    Boolean,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql import func
from geoalchemy2 import Geography, Geometry
from models.reference_layer import ReferenceLayer
from models.reference_feature import ReferenceFeature


from database.database import Base


class Layer(Base):
    __tablename__ = "layers"

    id = Column(Integer, primary_key=True)
    case_id = Column(Integer, nullable=False)
    name = Column(String(100), nullable=False)
    layer_type = Column(String(50))
    visible = Column(Boolean, default=True)
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
    )


class Feature(Base):
    __tablename__ = "features"

    id = Column(Integer, primary_key=True)
    feature_number = Column(Integer, nullable=False)
    layer_id = Column(Integer, ForeignKey("layers.id", ondelete="CASCADE"))
    case_id = Column(Integer, nullable=False)
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
