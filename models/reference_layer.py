from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.database import Base


class ReferenceLayer(Base):
    __tablename__ = "reference_layers"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    name: Mapped[str] = mapped_column(
        Text,
        unique=True,
        nullable=False
    )

    layer_type: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    visible: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now
    )

    features = relationship(
        "ReferenceFeature",
        back_populates="reference_layer",
        cascade="all, delete-orphan"
    )