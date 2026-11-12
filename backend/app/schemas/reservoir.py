"""Esquemas Pydantic de embalses, umbrales y curvas (M3)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ThresholdsIn(BaseModel):
    low_critical: float | None = Field(default=None, description="Nivel bajo crítico (m.s.n.m.)")
    low_alert: float | None = Field(default=None, description="Nivel bajo de alerta")
    high_alert: float | None = Field(default=None, description="Nivel alto de alerta")
    spill_level: float | None = Field(default=None, description="Nivel de alivio / inundación")

    ORDER: ClassVar[tuple[str, ...]] = ("low_critical", "low_alert", "high_alert", "spill_level")
    LABELS: ClassVar[dict[str, str]] = {
        "low_critical": "crítico bajo",
        "low_alert": "alerta baja",
        "high_alert": "alerta alta",
        "spill_level": "alivio/inundación",
    }

    @model_validator(mode="after")
    def _ordered(self) -> ThresholdsIn:
        given = [(k, getattr(self, k)) for k in self.ORDER if getattr(self, k) is not None]
        for (k1, v1), (k2, v2) in zip(given, given[1:], strict=False):
            if not v1 < v2:
                raise ValueError(
                    f"El nivel de {self.LABELS[k1]} ({v1}) debe ser menor que el de {self.LABELS[k2]} ({v2})."
                )
        return self


class ThresholdsOut(ThresholdsIn):
    model_config = ConfigDict(from_attributes=True)
    updated_at: datetime | None = None


class CurveSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    version: int
    valid_from: date
    source_filename: str | None
    notes: str | None
    created_at: datetime
    points: int
    min_elevation: float
    max_elevation: float
    max_volume_hm3: float


class CurvePointOut(BaseModel):
    elevation: float
    area_km2: float | None
    volume_hm3: float


class CurveDetail(CurveSummary):
    data: list[CurvePointOut]


class ReservoirOut(BaseModel):
    code: str
    name: str
    basin: str | None
    description: str | None
    records_start: date | None
    normal_level: float
    dead_level: float
    has_geometry: bool
    has_basin_geometry: bool
    thresholds: ThresholdsOut
    current_curve: CurveSummary | None
    dead_volume_hm3: float | None = Field(description="Volumen muerto según la curva vigente")
    normal_volume_hm3: float | None = Field(description="Volumen al nivel normal según la curva vigente")
    useful_capacity_hm3: float | None = Field(description="Capacidad útil = normal − muerto")


class ReservoirUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=80)
    basin: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    records_start: date | None = None
    normal_level: float | None = None
    dead_level: float | None = None


class GeometryIn(BaseModel):
    kind: Literal["reservoir", "basin"] = "reservoir"
    geojson: dict[str, Any] = Field(description="Polygon, MultiPolygon, Feature o FeatureCollection en WGS84")


class InterpolationOut(BaseModel):
    reservoir_code: str
    curve_version: int
    elevation: float
    volume_hm3: float
    area_km2: float | None
