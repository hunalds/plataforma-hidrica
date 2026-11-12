"""Movimiento diario de embalses (M4) y lotes de importación con vista previa."""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime, time
from typing import Any

from sqlalchemy import Date, DateTime, Enum, Float, ForeignKey, String, Text, Time, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class MeasurementSource(enum.StrEnum):
    MANUAL = "MANUAL"  # registro del Operador en la plataforma
    IMPORT = "IMPORT"  # importación de Excel/CSV
    SQL = "SQL"  # conector a la base SQL externa (previsto)


class VolumeSource(enum.StrEnum):
    REPORTED = "REPORTADO"  # vino en el archivo/registro
    CURVE = "CURVA"  # calculado con la curva cota–volumen vigente


class DailyMeasurement(Base):
    """Un registro por embalse y día (la lectura diaria del limnímetro y los caudales del día)."""

    __tablename__ = "daily_measurements"
    __table_args__ = (UniqueConstraint("reservoir_code", "day"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    reservoir_code: Mapped[str] = mapped_column(ForeignKey("reservoirs.code", ondelete="CASCADE"), index=True)
    day: Mapped[date] = mapped_column(Date, index=True)
    reading_time: Mapped[time | None] = mapped_column(Time)  # hora de la lectura (P-20)
    level_m: Mapped[float] = mapped_column(Float)  # cota (m.s.n.m.)
    volume_hm3: Mapped[float | None] = mapped_column(Float)
    volume_source: Mapped[VolumeSource | None] = mapped_column(Enum(VolumeSource, name="volume_source"))
    curve_version: Mapped[int | None] = mapped_column()  # versión de curva usada si volume_source = CURVA
    inflow_m3s: Mapped[float | None] = mapped_column(Float)  # caudal de entrada
    outflow_m3s: Mapped[float | None] = mapped_column(Float)  # salida/extracción a potabilizadoras
    eco_flow_m3s: Mapped[float | None] = mapped_column(Float)  # gasto ecológico
    gate_opening_pct: Mapped[float | None] = mapped_column(Float)  # apertura de compuertas
    intake_m3s: Mapped[float | None] = mapped_column(Float)  # captación (P-19)
    notes: Mapped[str | None] = mapped_column(Text)
    quality_flags: Mapped[list[str] | None] = mapped_column(JSONB)  # avisos de calidad aceptados al guardar
    source: Mapped[MeasurementSource] = mapped_column(Enum(MeasurementSource, name="measurement_source"))
    import_batch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("import_batches.id", ondelete="SET NULL")
    )
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class BatchStatus(enum.StrEnum):
    PREVIEW = "PREVIEW"
    CONFIRMED = "CONFIRMED"
    DISCARDED = "DISCARDED"


class ImportBatch(Base):
    """Archivo importado: se valida y se guarda como vista previa; solo se escribe al confirmar."""

    __tablename__ = "import_batches"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    filename: Mapped[str] = mapped_column(String(255))
    status: Mapped[BatchStatus] = mapped_column(
        Enum(BatchStatus, name="batch_status"), default=BatchStatus.PREVIEW
    )
    summary: Mapped[dict[str, Any]] = mapped_column(JSONB)
    issues: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)  # errores y avisos por fila
    rows: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)  # filas válidas normalizadas
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
