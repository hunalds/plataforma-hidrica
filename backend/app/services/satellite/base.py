"""Contrato común de las fuentes satelitales y climáticas (módulo M5).

Cada fuente (CHIRPS, ERA5-Land, Copernicus Data Space, Planetary Computer, GEE...) implementa
SatelliteProvider. El resto del sistema solo conoce esta interfaz, así una fuente se puede
reemplazar sin tocar la ingesta, el ML ni el panel (ver docs/CAMBIOS-PROMPT.md, C-10).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from typing import Any


class Variable(StrEnum):
    PRECIPITATION = "precipitacion_mm"  # acumulado diario promedio sobre el área (mm/día)
    SOIL_MOISTURE = "humedad_suelo_m3m3"  # contenido volumétrico de agua en el suelo (m³/m³)
    WATER_AREA = "superficie_agua_km2"  # superficie del espejo de agua (km²)
    NDWI = "ndwi_medio"  # índice de agua de diferencia normalizada, promedio (−1..1)


UNITS: dict[Variable, str] = {
    Variable.PRECIPITATION: "mm/día",
    Variable.SOIL_MOISTURE: "m³/m³",
    Variable.WATER_AREA: "km²",
    Variable.NDWI: "adimensional",
}


class Quality(StrEnum):
    GOOD = "buena"
    DOUBTFUL = "dudosa"  # p. ej. nubosidad alta o dato preliminar
    MISSING = "sin_dato"


@dataclass(frozen=True)
class AreaOfInterest:
    """Zona sobre la que se agrega la variable: espejo de agua del embalse o su cuenca."""

    code: str  # p. ej. "TULE" o "TULE_CUENCA"
    geometry: dict[str, Any]  # geometría GeoJSON (Polygon/MultiPolygon) en WGS84


@dataclass(frozen=True)
class SatelliteObservation:
    day: date
    area_code: str
    variable: Variable
    value: float | None
    source: str
    quality: Quality = Quality.GOOD
    cloud_pct: float | None = None  # solo aplica a productos ópticos (NDWI / superficie)
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def unit(self) -> str:
        return UNITS[self.variable]


class UnsupportedVariableError(ValueError):
    pass


class SatelliteProvider(ABC):
    """Fuente de datos satelitales. Debe devolver una observación por día del rango (inclusive)."""

    name: str
    variables: frozenset[Variable]
    requires_credentials: bool = False

    def supports(self, variable: Variable) -> bool:
        return variable in self.variables

    def fetch(
        self, aoi: AreaOfInterest, variable: Variable, start: date, end: date
    ) -> list[SatelliteObservation]:
        if not self.supports(variable):
            raise UnsupportedVariableError(
                f"La fuente {self.name!r} no ofrece la variable {variable.value!r}"
            )
        if end < start:
            raise ValueError("La fecha final es anterior a la inicial")
        return self._fetch(aoi, variable, start, end)

    @abstractmethod
    def _fetch(
        self, aoi: AreaOfInterest, variable: Variable, start: date, end: date
    ) -> list[SatelliteObservation]:
        """Implementación específica de cada fuente."""

    @abstractmethod
    def check(self) -> bool:
        """True si la fuente es accesible desde esta red (sin descargar datos)."""
