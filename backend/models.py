from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    api_channel: Mapped[int] = mapped_column(Integer, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )

    events: Mapped[list["PeopleEvent"]] = relationship(back_populates="camera")


class PeopleEvent(Base):
    __tablename__ = "people_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, index=True
    )
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id"), index=True)
    direction: Mapped[str] = mapped_column(
        Enum("ENTRATA", "USCITA", name="direction_enum"), nullable=False
    )
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    entered_total: Mapped[int] = mapped_column(Integer, nullable=False)
    exited_total: Mapped[int] = mapped_column(Integer, nullable=False)
    occupancy_after: Mapped[int] = mapped_column(Integer, nullable=False)

    camera: Mapped[Camera] = relationship(back_populates="events")


class ResetLog(Base):
    __tablename__ = "reset_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, index=True
    )
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id"), index=True)
    reason: Mapped[str] = mapped_column(String(64), nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

