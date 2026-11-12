"""Fuente simulada: datos plausibles y deterministas para desarrollo y pruebas (sin red)."""

from __future__ import annotations

import hashlib
import math
from datetime import date, timedelta

from app.services.satellite.base import (
    AreaOfInterest,
    Quality,
    SatelliteObservation,
    SatelliteProvider,
    Variable,
)


def _unit_noise(*parts: object) -> float:
    """Ruido determinista en [0, 1) a partir de un hash (mismos parámetros → mismo valor)."""
    digest = hashlib.sha256("|".join(map(str, parts)).encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


def _wet_season(day: date) -> float:
    """Estacionalidad bimodal (picos en mayo y octubre), en [0, 1]."""
    doy = day.timetuple().tm_yday
    may = math.exp(-0.5 * ((doy - 130) / 22) ** 2)
    oct_ = math.exp(-0.5 * ((doy - 295) / 32) ** 2)
    return min(1.0, 0.55 * may + oct_)


class MockProvider(SatelliteProvider):
    name = "mock"
    variables = frozenset(Variable)

    def check(self) -> bool:
        return True

    def _fetch(
        self, aoi: AreaOfInterest, variable: Variable, start: date, end: date
    ) -> list[SatelliteObservation]:
        out: list[SatelliteObservation] = []
        day = start
        while day <= end:
            out.append(self._one(aoi.code, variable, day))
            day += timedelta(days=1)
        return out

    def _one(self, code: str, variable: Variable, day: date) -> SatelliteObservation:
        u = _unit_noise(code, variable.value, day.isoformat())
        wet = _wet_season(day)
        cloud = None
        quality = Quality.GOOD
        match variable:
            case Variable.PRECIPITATION:
                value = round(0.0 if u < 0.55 - 0.35 * wet else -math.log(1 - u) * (2 + 10 * wet), 2)
            case Variable.SOIL_MOISTURE:
                value = round(0.18 + 0.20 * wet + 0.04 * (u - 0.5), 4)
            case Variable.WATER_AREA:
                value = round(20 + 6 * wet + (u - 0.5), 3)
            case Variable.NDWI:
                value = round(0.25 + 0.2 * wet + 0.1 * (u - 0.5), 4)
        if variable in (Variable.WATER_AREA, Variable.NDWI):
            cloud = round(100 * min(1.0, 0.2 + 0.7 * wet * u), 1)
            if cloud > 80:
                value, quality = None, Quality.MISSING
            elif cloud > 40:
                quality = Quality.DOUBTFUL
        return SatelliteObservation(
            day=day,
            area_code=code,
            variable=variable,
            value=value,
            source=self.name,
            quality=quality,
            cloud_pct=cloud,
        )
