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
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from geoalchemy2 import Geography, Geometry

from database.database import Base


# ============================================================
# Users
# ============================================================
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)

    email = Column(String(255), unique=True, nullable=False)

    password = Column(Text, nullable=False)
    full_name = Column(String(100))
    role = Column(String(30), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    # NEW: updated on every successful login (see auth_service.login_user)
    last_login = Column(DateTime, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "role IN ('Admin', 'Officer', 'Analyst', 'Viewer')",
            name="users_role_check",
        ),
    )

    cases_created = relationship("Case", back_populates="creator")
    features_created = relationship("Feature", back_populates="creator")


# ============================================================
# Cases
# ============================================================
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


# ============================================================
# Layers
# ============================================================
class Layer(Base):
    __tablename__ = "layers"

    id = Column(Integer, primary_key=True)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=True)
    name = Column(String(100), nullable=False)
    layer_type = Column(String(50))
    visible = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    case = relationship("Case", back_populates="layers")
    features = relationship("Feature", back_populates="layer")
    images = relationship("ImageRecord", back_populates="layer")


# ============================================================
# Features
# ============================================================
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


# ============================================================
# Comments
# ============================================================
class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True)
    feature_id = Column(Integer, ForeignKey("features.id", ondelete="CASCADE"), nullable=False)

    user_id = Column(Integer)
    comment = Column(Text, nullable=False)

    image_data = Column(LargeBinary)
    created_at = Column(DateTime, server_default=func.now())

    feature = relationship("Feature", back_populates="comments")


# ============================================================
# GeoCLIP uploaded images
# ============================================================
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