from datetime import datetime
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.database import Base


class ReferenceFeature(Base):
    __tablename__ = "reference_features"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    reference_layer_id: Mapped[int] = mapped_column(
        ForeignKey(
            "reference_layers.id",
            ondelete="CASCADE"
        ),
        nullable=False
    )

    name: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    geom: Mapped[Any] = mapped_column(
        Geometry(
            geometry_type="GEOMETRY",
            srid=4326
        ),
        nullable=True
    )

    properties: Mapped[dict] = mapped_column(
        JSON,
        default=dict
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now
    )

    reference_layer = relationship(
        "ReferenceLayer",
        back_populates="features"
    )