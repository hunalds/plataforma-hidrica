"""Ingesta satelital (M5): descarga por embalse, guarda en satellite_observations y reporta avance.

La usan la CLI (backfill histórico) y las tareas en segundo plano de la API (descarga manual).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.reservoir import Reservoir
from app.models.satellite import SatelliteObservation as ObservationRow
from app.models.satellite import Scope
from app.services.satellite import registry
from app.services.satellite.base import AreaOfInterest, SatelliteObservation, Variable


@dataclass(frozen=True)
class Kind:
    label: str
    provider: str
    variables: tuple[Variable, ...]
    scope: Scope
    chunk_days: int  # tamaño de cada bloque de descarga (para reportar avance)


KINDS: dict[str, Kind] = {
    "precipitacion": Kind("Precipitación (CHIRPS)", "chirps", (Variable.PRECIPITATION,), Scope.BASIN, 366),
    "humedad_suelo": Kind(
        "Humedad del suelo (ERA5-Land)", "era5_land_openmeteo", (Variable.SOIL_MOISTURE,), Scope.BASIN, 366
    ),
    "agua": Kind(
        "NDWI y superficie de agua (Sentinel-2 / Landsat)",
        "planetary_computer",
        (Variable.NDWI, Variable.WATER_AREA),
        Scope.RESERVOIR,
        92,
    ),
}

Progress = Callable[[float, str], None]


class MissingGeometryError(ValueError):
    pass


def areas(session: Session, codes: list[str], scope: Scope) -> list[AreaOfInterest]:
    column = Reservoir.geom if scope == Scope.RESERVOIR else Reservoir.basin_geom
    rows = session.execute(
        select(Reservoir.code, func.ST_AsGeoJSON(column))
        .where(Reservoir.code.in_(codes))
        .order_by(Reservoir.code)
    ).all()
    missing = [c for c, g in rows if g is None]
    if missing:
        what = "polígono del embalse" if scope == Scope.RESERVOIR else "cuenca o área de influencia"
        raise MissingGeometryError(f"Falta el {what} de: {', '.join(missing)}. Cárgalo antes de descargar.")
    return [AreaOfInterest(code=c, geometry=json.loads(g)) for c, g in rows]


def save(session: Session, observations: list[SatelliteObservation], scope: Scope) -> int:
    if not observations:
        return 0
    rows = [
        {
            "reservoir_code": o.area_code,
            "scope": scope,
            "day": o.day,
            "variable": o.variable.value,
            "value": o.value,
            "source": o.source,
            "quality": o.quality.value,
            "cloud_pct": o.cloud_pct,
            "meta": o.meta or None,
        }
        for o in observations
    ]
    # Una misma fecha puede venir dos veces (p. ej. final y preliminar): se queda la última
    unique = {(r["reservoir_code"], r["variable"], r["source"], r["day"]): r for r in rows}
    values = list(unique.values())
    for i in range(0, len(values), 2000):
        stmt = insert(ObservationRow).values(values[i : i + 2000])
        stmt = stmt.on_conflict_do_update(
            index_elements=["reservoir_code", "scope", "variable", "source", "day"],
            set_={c: stmt.excluded[c] for c in ("value", "quality", "cloud_pct", "meta")},
        )
        session.execute(stmt)
    return len(values)


def _chunks(start: date, end: date, days: int) -> list[tuple[date, date]]:
    out, cursor = [], start
    while cursor <= end:
        stop = min(end, cursor + timedelta(days=days - 1))
        out.append((cursor, stop))
        cursor = stop + timedelta(days=1)
    return out


def run(
    session: Session,
    kind_key: str,
    codes: list[str],
    start: date,
    end: date,
    progress: Progress | None = None,
) -> dict[str, Any]:
    """Descarga y guarda. Hace commit por bloque: si se interrumpe, lo ya descargado queda guardado."""
    kind = KINDS[kind_key]
    provider = registry.get_provider(kind.provider)
    aois = areas(session, codes, kind.scope)
    chunks = _chunks(start, end, kind.chunk_days)
    total_steps = len(chunks) * (
        1 if hasattr(provider, "fetch_many") and kind_key == "precipitacion" else len(aois)
    )
    done, saved, valid = 0, 0, 0

    def tick(message: str) -> None:
        nonlocal done
        done += 1
        if progress:
            progress(done / max(total_steps, 1), message)

    for lo, hi in chunks:
        if kind_key == "precipitacion" and hasattr(provider, "fetch_many"):
            obs = provider.fetch_many(aois, kind.variables[0], lo, hi)
            saved += save(session, obs, kind.scope)
            valid += sum(1 for o in obs if o.value is not None)
            session.commit()
            tick(f"{kind.label}: {lo.isoformat()} a {hi.isoformat()}")
            continue
        for aoi in aois:
            if kind_key == "agua" and hasattr(provider, "fetch_both"):
                obs = provider.fetch_both(aoi, lo, hi)
            else:
                obs = [o for v in kind.variables for o in provider.fetch(aoi, v, lo, hi)]
            saved += save(session, obs, kind.scope)
            valid += sum(1 for o in obs if o.value is not None)
            session.commit()
            tick(f"{kind.label} · {aoi.code}: {lo.isoformat()} a {hi.isoformat()}")
    return {
        "tipo": kind_key,
        "embalses": codes,
        "desde": start.isoformat(),
        "hasta": end.isoformat(),
        "guardadas": saved,
        "con_valor": valid,
    }
