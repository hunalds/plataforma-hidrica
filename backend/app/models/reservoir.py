"""Embalses, umbrales y curvas cota–área–volumen versionadas (M3)."""

from __future__ import annotations

from datetime import date, datetime

from geoalchemy2 import Geometry
from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Reservoir(Base):
    __tablename__ = "reservoirs"

    code: Mapped[str] = mapped_column(String(20), primary_key=True)  # TULE, MANUELOTE, TRES_RIOS
    name: Mapped[str] = mapped_column(String(80))
    basin: Mapped[str | None] = mapped_column(String(120))  # nombre de la cuenca
    records_start: Mapped[date | None] = mapped_column(Date)
    normal_level: Mapped[float] = mapped_column(Float)  # cota normal (m.s.n.m., P-01)
    dead_level: Mapped[float] = mapped_column(Float)  # cota de volumen muerto / mínimo operativo
    description: Mapped[str | None] = mapped_column(Text)
    # Control de calidad (M4): variación diaria de cota que se considera "salto brusco"
    qc_max_daily_change_m: Mapped[float] = mapped_column(Float, default=1.0, server_default="1.0")
    # Geometrías WGS84 cargadas por los autores (P-07, P-08). Nunca se inventan.
    geom: Mapped[object | None] = mapped_column(Geometry("MULTIPOLYGON", srid=4326, spatial_index=True))
    basin_geom: Mapped[object | None] = mapped_column(Geometry("MULTIPOLYGON", srid=4326, spatial_index=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    thresholds: Mapped[Threshold | None] = relationship(
        back_populates="reservoir", uselist=False, lazy="selectin", cascade="all, delete-orphan"
    )


class Threshold(Base):
    """Umbrales configurables por el Ingeniero.

    Deben cumplir: crítico bajo < alerta baja < alerta alta < alivio.
    """

    __tablename__ = "thresholds"

    reservoir_code: Mapped[str] = mapped_column(
        ForeignKey("reservoirs.code", ondelete="CASCADE"), primary_key=True
    )
    low_critical: Mapped[float | None] = mapped_column(Float)  # nivel bajo crítico
    low_alert: Mapped[float | None] = mapped_column(Float)  # nivel bajo de alerta
    high_alert: Mapped[float | None] = mapped_column(Float)  # nivel alto de alerta
    spill_level: Mapped[float | None] = mapped_column(Float)  # nivel de alivio / inundación
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    reservoir: Mapped[Reservoir] = relationship(back_populates="thresholds")


class ElevationCurve(Base):
    """Versión de la curva cota–área–volumen de un embalse, vigente desde `valid_from`."""

    __tablename__ = "elevation_curves"
    __table_args__ = (UniqueConstraint("reservoir_code", "version"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    reservoir_code: Mapped[str] = mapped_column(ForeignKey("reservoirs.code", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    valid_from: Mapped[date] = mapped_column(Date)
    source_filename: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    points: Mapped[list[ElevationCurvePoint]] = relationship(
        back_populates="curve",
        lazy="selectin",
        order_by="ElevationCurvePoint.elevation",
        cascade="all, delete-orphan",
    )


class ElevationCurvePoint(Base):
    __tablename__ = "elevation_curve_points"
    __table_args__ = (UniqueConstraint("curve_id", "elevation"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    curve_id: Mapped[int] = mapped_column(ForeignKey("elevation_curves.id", ondelete="CASCADE"), index=True)
    elevation: Mapped[float] = mapped_column(Float)  # cota (m.s.n.m.)
    area_km2: Mapped[float | None] = mapped_column(Float)
    volume_hm3: Mapped[float] = mapped_column(Float)

    curve: Mapped[ElevationCurve] = relationship(back_populates="points")
