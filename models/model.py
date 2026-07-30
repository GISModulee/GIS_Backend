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
    CheckConstraint,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from geoalchemy2 import Geography, Geometry

from database.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password = Column(Text, nullable=False)
    full_name = Column(String(100))
    role = Column(String(30), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    last_login = Column(DateTime, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "role IN ('Admin', 'Officer', 'Analyst', 'Viewer')",
            name="users_role_check",
        ),
    )

    cases_created = relationship("Case", back_populates="creator")
    features_created = relationship("Feature", back_populates="creator")


class Case(Base):
    __tablename__ = "cases"

    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    status = Column(String(30), default="Open")
    priority = Column(String(20), default="Medium")
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())

    creator = relationship("User", back_populates="cases_created")
    layers = relationship("Layer", back_populates="case")
    features = relationship("Feature", back_populates="case")


class Layer(Base):
    __tablename__ = "layers"

    id = Column(Integer, primary_key=True)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=True)
    name = Column(String(100), nullable=False)
    layer_type = Column(String(50))
    visible = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    file_hash = Column(String(64), nullable=True, index=True)

    case = relationship("Case", back_populates="layers")
    features = relationship("Feature", back_populates="layer")
    images = relationship("ImageRecord", back_populates="layer")

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
    layer_id = Column(Integer, ForeignKey("layers.id", ondelete="CASCADE"))
    case_id = Column(Integer, ForeignKey("cases.id"))
    name = Column(Text)
    geom = Column(Geometry(geometry_type="GEOMETRY", srid=4326))

    geometry_type = Column(String, default="Polygon")
    radius = Column(Float)
    properties = Column(JSON, default=dict)

    image_data = Column(LargeBinary)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    layer = relationship("Layer", back_populates="features")
    case = relationship("Case", back_populates="features")
    creator = relationship("User", back_populates="features_created")
    comments = relationship("Comment", back_populates="feature")


class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True)
    feature_id = Column(Integer, ForeignKey("features.id", ondelete="CASCADE"), nullable=False)

    # FK added (previously a bare Integer column with no constraint) —
    # needed to safely JOIN against `users` in get_feature_comments() so
    # every comment can be attributed to its author for the multi-user
    # thread view. nullable=True kept so historical rows with no user_id
    # (or one that no longer resolves) don't break.
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    comment = Column(Text, nullable=False)

    # RENAMED from image_data + two new columns: comments used to only
    # support a single hardcoded "image/jpeg" attachment. Now supports
    # any of the allowed types (image, PDF, DOCX, plain text) — see
    # services/comment_validator.py — and the real filename/content
    # type are stored so they can be served back correctly instead of
    # always being labeled image/jpeg regardless of what was uploaded.
    attachment_data = Column(LargeBinary, nullable=True)
    attachment_filename = Column(String(255), nullable=True)
    attachment_content_type = Column(String(100), nullable=True)

    created_at = Column(DateTime, server_default=func.now())

    feature = relationship("Feature", back_populates="comments")


class ImageRecord(Base):
    __tablename__ = "image_records"

    id = Column(String, primary_key=True, index=True)
    file_hash = Column(String, unique=True, index=True, nullable=False)
    layer_id = Column(Integer, ForeignKey("layers.id"), nullable=False, index=True)
    image_data = Column(LargeBinary, nullable=False)
    filename = Column(String, nullable=False)

    content_type = Column(String(50), nullable=True)

    location = Column(Geography(geometry_type="POINT", srid=4326))
    raw_metadata = Column("metadata", JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    layer = relationship("Layer", back_populates="images")
