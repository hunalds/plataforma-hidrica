"""Observaciones satelitales y climáticas (M5) y tareas en segundo plano."""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, DateTime, Enum, Float, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Scope(enum.StrEnum):
    RESERVOIR = "EMBALSE"  # espejo de agua (NDWI, superficie)
    BASIN = "CUENCA"  # cuenca o área de influencia (precipitación, humedad del suelo)


class SatelliteObservation(Base):
    """Un valor diario por embalse, ámbito, variable y fuente."""

    __tablename__ = "satellite_observations"
    __table_args__ = (UniqueConstraint("reservoir_code", "scope", "variable", "source", "day"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    reservoir_code: Mapped[str] = mapped_column(ForeignKey("reservoirs.code", ondelete="CASCADE"), index=True)
    scope: Mapped[Scope] = mapped_column(Enum(Scope, name="satellite_scope"))
    day: Mapped[date] = mapped_column(Date, index=True)
    variable: Mapped[str] = mapped_column(String(40), index=True)  # ver services/satellite/base.Variable
    value: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(60))  # chirps, era5_land_openmeteo, sentinel-2-l2a…
    quality: Mapped[str] = mapped_column(String(20))  # buena | dudosa | sin_dato
    cloud_pct: Mapped[float | None] = mapped_column(Float)
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class JobStatus(enum.StrEnum):
    PENDING = "PENDIENTE"
    RUNNING = "EN_CURSO"
    DONE = "TERMINADA"
    FAILED = "FALLIDA"


class Job(Base):
    """Tarea pesada lanzada manualmente (descarga satelital, más adelante reentrenamiento y reportes)."""

    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(40), index=True)
    params: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus, name="job_status"), default=JobStatus.PENDING)
    progress: Mapped[float] = mapped_column(Float, default=0.0)  # 0 a 1
    message: Mapped[str | None] = mapped_column(Text)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
