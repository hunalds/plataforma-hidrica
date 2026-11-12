"""Panel principal (M7) y mapa geoespacial (M8): todos los roles consultan.

- /reservoirs/{code}/history: cota del período con mínimos y máximos históricos del mismo día del año.
- /map/features: polígonos (embalse y área de influencia) con el semáforo y los indicadores del panel.
- /dashboard/comparison: disponibilidad diaria de los embalses visibles (comparativo).
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select

from app.api.deps import DbSession, require
from app.api.measurements import _book, _status
from app.api.reservoirs import get_visible_reservoir, visible_codes
from app.core.permissions import Access, Module
from app.models.measurement import DailyMeasurement
from app.models.reservoir import Reservoir
from app.models.satellite import SatelliteObservation
from app.models.user import User
from app.services.curves import CurveRangeError
from app.services.ml_service import SAT_SOURCES

router = APIRouter(tags=["panel y mapa"])

PanelReader = Annotated[User, Depends(require(Module.DASHBOARD, Access.READ))]
MapReader = Annotated[User, Depends(require(Module.MAP, Access.READ))]


class HistoryPoint(BaseModel):
    day: date
    level_m: float | None
    hist_min: float | None
    hist_max: float | None
    hist_mean: float | None


class HistoryOut(BaseModel):
    reservoir_code: str
    years: str
    points: list[HistoryPoint]


@router.get(
    "/reservoirs/{code}/history", response_model=HistoryOut, summary="Cota del período y rango histórico"
)
def history(
    code: str, session: DbSession, user: PanelReader, days: int = Query(default=365, ge=30, le=3660)
) -> HistoryOut:
    r = get_visible_reservoir(session, user, code)
    rows = session.execute(
        select(DailyMeasurement.day, DailyMeasurement.level_m)
        .where(DailyMeasurement.reservoir_code == r.code)
        .order_by(DailyMeasurement.day)
    ).all()
    if not rows:
        return HistoryOut(reservoir_code=r.code, years="—", points=[])
    last = rows[-1][0]
    start = last - timedelta(days=days - 1)
    # Climatología por día del año, con todos los años excepto el período mostrado
    by_doy: dict[int, list[float]] = {}
    for d, lvl in rows:
        if d < start and lvl is not None:
            by_doy.setdefault(min(d.timetuple().tm_yday, 365), []).append(lvl)
    points = []
    for d, lvl in rows:
        if d < start:
            continue
        vals = by_doy.get(min(d.timetuple().tm_yday, 365), [])
        points.append(
            HistoryPoint(
                day=d,
                level_m=lvl,
                hist_min=round(min(vals), 3) if vals else None,
                hist_max=round(max(vals), 3) if vals else None,
                hist_mean=round(sum(vals) / len(vals), 3) if vals else None,
            )
        )
    return HistoryOut(
        reservoir_code=r.code,
        years=f"{rows[0][0].year}–{start.year - 1}" if rows[0][0] < start else "—",
        points=points,
    )


@router.get("/dashboard/comparison", summary="Disponibilidad diaria comparada entre embalses")
def comparison(
    session: DbSession, user: PanelReader, days: int = Query(default=365, ge=30, le=3660)
) -> list[dict[str, Any]]:
    stmt = select(Reservoir).order_by(Reservoir.name)
    visible = visible_codes(user)
    if visible is not None:
        stmt = stmt.where(Reservoir.code.in_(visible))
    out = []
    for r in session.scalars(stmt):
        rows = session.scalars(
            select(DailyMeasurement)
            .where(DailyMeasurement.reservoir_code == r.code)
            .order_by(DailyMeasurement.day.desc())
            .limit(days)
        ).all()
        book = _book(session, r.code)
        series = []
        for m in reversed(rows):
            curve = book.for_day(m.day)
            if curve is None:
                continue
            _, interp = curve
            try:
                dead, normal = interp.volume_at(r.dead_level), interp.volume_at(r.normal_level)
                v = m.volume_hm3 if m.volume_hm3 is not None else interp.volume_at(m.level_m)
            except CurveRangeError:
                continue
            series.append([m.day.isoformat(), round(max(0.0, v - dead) / (normal - dead) * 100, 1)])
        out.append({"reservoir_code": r.code, "name": r.name, "availability": series})
    return out


def _precip_30d(session, code: str, source: str) -> float | None:
    last = session.scalar(
        select(func.max(SatelliteObservation.day)).where(
            SatelliteObservation.reservoir_code == code,
            SatelliteObservation.variable == "precipitacion_mm",
            SatelliteObservation.source == source,
        )
    )
    if last is None:
        return None
    total = session.scalar(
        select(func.sum(SatelliteObservation.value)).where(
            SatelliteObservation.reservoir_code == code,
            SatelliteObservation.variable == "precipitacion_mm",
            SatelliteObservation.source == source,
            SatelliteObservation.day > last - timedelta(days=30),
        )
    )
    return round(float(total), 1) if total is not None else None


def _latest(
    session, code: str, variable: str, source: str | None = None, good_only: bool = False
) -> tuple[float | None, date | None]:
    stmt = select(SatelliteObservation.value, SatelliteObservation.day).where(
        SatelliteObservation.reservoir_code == code,
        SatelliteObservation.variable == variable,
        SatelliteObservation.value.is_not(None),
    )
    if source:
        stmt = stmt.where(SatelliteObservation.source == source)
    if good_only:
        stmt = stmt.where(SatelliteObservation.quality == "buena")
    row = session.execute(stmt.order_by(SatelliteObservation.day.desc()).limit(1)).first()
    return (round(float(row[0]), 3), row[1]) if row else (None, None)


@router.get(
    "/map/features", summary="Capas del mapa: embalses con semáforo y áreas de influencia con indicadores"
)
def map_features(
    session: DbSession,
    user: MapReader,
    source: Annotated[
        str, Query(pattern="^(real|sintetico)$", description="Fuente de lluvia y humedad para las capas")
    ] = "real",
) -> dict[str, Any]:
    stmt = select(Reservoir).order_by(Reservoir.name)
    visible = visible_codes(user)
    if visible is not None:
        stmt = stmt.where(Reservoir.code.in_(visible))
    src = SAT_SOURCES[source]
    today = date.today()
    reservoirs, basins = [], []
    for r in session.scalars(stmt):
        geom, basin = session.execute(
            select(
                func.ST_AsGeoJSON(func.ST_SimplifyPreserveTopology(Reservoir.geom, 0.0003), 5),
                func.ST_AsGeoJSON(func.ST_SimplifyPreserveTopology(Reservoir.basin_geom, 0.002), 4),
            ).where(Reservoir.code == r.code)
        ).one()
        st = _status(session, r, today)
        water, water_day = _latest(session, r.code, "superficie_agua_km2", good_only=True)
        soil, soil_day = _latest(session, r.code, "humedad_suelo_m3m3", src["soil_moisture"])
        props = {
            "code": r.code,
            "name": r.name,
            "light": st.light,
            "direction": st.direction,
            "light_reason": st.light_reason,
            "level_m": st.level_m,
            "availability_pct": st.availability_pct,
            "reserve_days": st.reserve_days,
            "last_day": st.last_day.isoformat() if st.last_day else None,
            "is_stale": st.is_stale,
            "precip_30d_mm": _precip_30d(session, r.code, src["precip_mm"]),
            "soil_moisture": soil,
            "soil_moisture_day": soil_day.isoformat() if soil_day else None,
            "water_area_km2": water,
            "water_area_day": water_day.isoformat() if water_day else None,
            "geometry_source": r.geom_source,
        }
        if geom:
            reservoirs.append({"type": "Feature", "properties": props, "geometry": json.loads(geom)})
        if basin:
            basins.append(
                {
                    "type": "Feature",
                    "properties": {
                        **{k: props[k] for k in ("code", "name", "precip_30d_mm", "soil_moisture")},
                        "source": r.basin_source,
                    },
                    "geometry": json.loads(basin),
                }
            )
    return {
        "reservoirs": {"type": "FeatureCollection", "features": reservoirs},
        "basins": {"type": "FeatureCollection", "features": basins},
        "satellite_source": source,
        "attribution": (
            "Polígonos © colaboradores de OpenStreetMap (ODbL) · CHIRPS (UCSB) · "
            "ERA5-Land (ECMWF/Copernicus vía Open-Meteo)"
        ),
    }
