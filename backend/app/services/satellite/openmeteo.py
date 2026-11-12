"""Humedad del suelo ERA5-Land (capa 0–7 cm) a través de la API histórica de Open-Meteo.

- Sin cuenta ni clave. Reanálisis ERA5-Land del ECMWF/Copernicus (~9 km), desde 1950.
- Open-Meteo es gratuito para uso no comercial (tesis). Para uso institucional permanente se debe
  revisar su licencia o cambiar al Copernicus CDS con cuenta propia (P-15, C-20).
- Se muestrea una malla de puntos (0,1°) dentro del área de influencia y se promedia: equivale a
  promediar las celdas de ERA5-Land que caen en el polígono.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

import httpx
import numpy as np
import shapely
from shapely.geometry import shape

from app.services.satellite.base import (
    AreaOfInterest,
    Quality,
    SatelliteObservation,
    SatelliteProvider,
    Variable,
)

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
GRID_DEG = 0.1
MAX_POINTS = 30
USER_AGENT = "plataforma-hidrica-zulia/0.1 (tesis URBE)"


def sample_points(geom, step: float = GRID_DEG, max_points: int = MAX_POINTS) -> list[tuple[float, float]]:
    """Puntos (lat, lon) de una malla regular dentro del polígono (al menos el centroide)."""
    minx, miny, maxx, maxy = geom.bounds
    lons = np.arange(np.floor(minx / step) * step + step / 2, maxx, step)
    lats = np.arange(np.floor(miny / step) * step + step / 2, maxy, step)
    lon2d, lat2d = np.meshgrid(lons, lats)
    inside = shapely.contains_xy(geom, lon2d, lat2d)
    pts = [
        (round(float(la), 4), round(float(lo), 4))
        for la, lo in zip(lat2d[inside], lon2d[inside], strict=True)
    ]
    if not pts:
        c = geom.representative_point()
        pts = [(round(c.y, 4), round(c.x, 4))]
    if len(pts) > max_points:  # submuestreo uniforme para no exceder el límite de la API
        idx = np.linspace(0, len(pts) - 1, max_points).round().astype(int)
        pts = [pts[i] for i in idx]
    return pts


class OpenMeteoSoilProvider(SatelliteProvider):
    name = "era5_land_openmeteo"
    variables = frozenset({Variable.SOIL_MOISTURE})

    def __init__(self, client: httpx.Client | None = None) -> None:
        self.client = client or httpx.Client(timeout=120, headers={"User-Agent": USER_AGENT})

    def check(self) -> bool:
        try:
            r = self.client.get(
                ARCHIVE_URL,
                params={
                    "latitude": 10.9,
                    "longitude": -72.1,
                    "start_date": "2020-01-01",
                    "end_date": "2020-01-01",
                    "daily": "precipitation_sum",
                },
            )
            return r.status_code == 200
        except httpx.HTTPError:
            return False

    def _fetch(
        self, aoi: AreaOfInterest, variable: Variable, start: date, end: date
    ) -> list[SatelliteObservation]:
        points = sample_points(shape(aoi.geometry))
        out: list[SatelliteObservation] = []
        # Por años para respetar el tamaño de respuesta de la API (horario × puntos)
        cursor = start
        while cursor <= end:
            chunk_end = min(end, date(cursor.year, 12, 31))
            out.extend(self._fetch_chunk(aoi.code, points, cursor, chunk_end))
            cursor = chunk_end + timedelta(days=1)
        return out

    def _fetch_chunk(
        self, code: str, points: list[tuple[float, float]], start: date, end: date
    ) -> list[SatelliteObservation]:
        r = self.client.get(
            ARCHIVE_URL,
            params={
                "latitude": ",".join(str(p[0]) for p in points),
                "longitude": ",".join(str(p[1]) for p in points),
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "hourly": "soil_moisture_0_to_7cm",
                "models": "era5_land",
                "timezone": "America/Caracas",
            },
        )
        r.raise_for_status()
        payload = r.json()
        locations = payload if isinstance(payload, list) else [payload]
        daily: dict[date, list[float]] = defaultdict(list)
        for loc in locations:
            times = loc["hourly"]["time"]
            values = loc["hourly"]["soil_moisture_0_to_7cm"]
            per_day: dict[date, list[float]] = defaultdict(list)
            for t, v in zip(times, values, strict=True):
                if v is not None:
                    per_day[date.fromisoformat(t[:10])].append(v)
            for d, vals in per_day.items():
                daily[d].append(sum(vals) / len(vals))
        out = []
        d = start
        while d <= end:
            vals = daily.get(d)
            out.append(
                SatelliteObservation(
                    day=d,
                    area_code=code,
                    variable=Variable.SOIL_MOISTURE,
                    value=round(float(np.mean(vals)), 4) if vals else None,
                    source=self.name,
                    quality=Quality.GOOD if vals else Quality.MISSING,
                    meta={"puntos": len(points), "puntos_con_dato": len(vals or [])},
                )
            )
            d += timedelta(days=1)
        return out
