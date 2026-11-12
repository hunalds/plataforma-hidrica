"""Datos satelitales (M5): fuentes, cobertura, descargas en segundo plano y series por embalse.

Permisos (matriz §6): M5 → Gerencia consulta, Ingeniero gestiona, Operador sin acceso.
Las series y el resumen por embalse se leen con M7 (panel), que tienen todos los roles, porque el
panel principal muestra precipitación, humedad del suelo y superficie de agua (sección 3.3).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select

from app.api.deps import DbSession, api_error, client_ip, require
from app.api.reservoirs import get_visible_reservoir
from app.core.permissions import Access, Module
from app.models.reservoir import Reservoir
from app.models.satellite import Job, SatelliteObservation
from app.models.user import User
from app.services.audit import log_action
from app.services.jobs import create_job, run_job
from app.services.satellite import ingest as sat_ingest
from app.services.satellite.base import UNITS, Variable

router = APIRouter(tags=["datos satelitales"])

SatReader = Annotated[User, Depends(require(Module.SATELLITE, Access.READ))]
SatManager = Annotated[User, Depends(require(Module.SATELLITE, Access.MANAGE))]
PanelReader = Annotated[User, Depends(require(Module.DASHBOARD, Access.READ))]

SOURCES = [
    {
        "clave": "chirps",
        "nombre": "CHIRPS v3 (UCSB Climate Hazards Center)",
        "variables": ["precipitacion_mm"],
        "acceso": "dynamical.org · sin cuenta",
        "resolucion": "0,05° (~5,5 km), diario, desde 1981",
        "atribucion": "Funk et al. (2015), CHIRPS; distribución dynamical.org",
    },
    {
        "clave": "era5_land_openmeteo",
        "nombre": "ERA5-Land (ECMWF / Copernicus) vía Open-Meteo",
        "variables": ["humedad_suelo_m3m3"],
        "acceso": "Open-Meteo · sin cuenta (uso no comercial)",
        "resolucion": "~9 km, horario → diario, desde 1950",
        "atribucion": "Muñoz-Sabater et al. (2021), ERA5-Land; API de Open-Meteo (CC BY 4.0)",
    },
    {
        "clave": "planetary_computer",
        "nombre": "Sentinel-2 L2A y Landsat C2 L2 (Microsoft Planetary Computer)",
        "variables": ["ndwi_medio", "superficie_agua_km2"],
        "acceso": "STAC abierto · sin cuenta",
        "resolucion": "10 m (Sentinel-2, 2017→) y 30 m (Landsat, 2005→); cada 2–8 días con nubes",
        "atribucion": "Copernicus Sentinel-2 (ESA); Landsat (USGS/NASA); McFeeters (1996) NDWI",
    },
]


class JobIn(BaseModel):
    kind: str = Field(description="precipitacion | humedad_suelo | agua")
    reservoir_codes: list[str] | None = Field(default=None, description="Por defecto, los tres embalses")
    date_from: date
    date_to: date

    @model_validator(mode="after")
    def _check(self) -> JobIn:
        if self.kind not in sat_ingest.KINDS:
            raise ValueError(f"Tipo desconocido. Usa uno de: {', '.join(sat_ingest.KINDS)}")
        if self.date_to < self.date_from:
            raise ValueError("La fecha final es anterior a la inicial.")
        if self.date_to > date.today():
            raise ValueError("La fecha final no puede ser futura.")
        if self.date_from < date(2005, 1, 1):
            raise ValueError("Los registros de los embalses empiezan en 2005.")
        return self


class JobOut(BaseModel):
    id: uuid.UUID
    kind: str
    params: dict[str, Any]
    status: str
    progress: float
    message: str | None
    result: dict[str, Any] | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class CoverageOut(BaseModel):
    reservoir_code: str
    variable: str
    source: str
    observations: int
    with_value: int
    good: int
    first_day: date | None
    last_day: date | None


class SeriesPoint(BaseModel):
    day: date
    value: float | None
    source: str
    quality: str
    cloud_pct: float | None


class SatelliteSummary(BaseModel):
    reservoir_code: str
    precipitation_7d_mm: float | None
    precipitation_30d_mm: float | None
    precipitation_30d_normal_mm: float | None = Field(
        description="Promedio del mismo período en los años disponibles"
    )
    precipitation_30d_anomaly_pct: float | None
    precipitation_last_day: date | None
    soil_moisture: float | None
    soil_moisture_day: date | None
    soil_moisture_normal: float | None
    water_area_km2: float | None
    water_area_day: date | None
    water_area_source: str | None
    water_area_reference_km2: float | None = Field(
        description="Área del polígono del embalse (OSM u oficial)"
    )
    ndwi: float | None
    geometry_source: str | None
    basin_source: str | None


def _job_out(j: Job) -> JobOut:
    return JobOut.model_validate(j, from_attributes=True)


# ------------------------------------------------------------------ fuentes, cobertura y tareas


@router.get("/satellite/sources", summary="Fuentes satelitales configuradas")
def sources(_: SatReader) -> list[dict[str, Any]]:
    return SOURCES


@router.get("/satellite/coverage", response_model=list[CoverageOut], summary="Datos satelitales disponibles")
def coverage(session: DbSession, _: SatReader) -> list[CoverageOut]:
    O = SatelliteObservation  # noqa: N806, E741
    rows = session.execute(
        select(
            O.reservoir_code,
            O.variable,
            O.source,
            func.count(),
            func.count(O.value),
            func.count().filter(O.quality == "buena"),
            func.min(O.day),
            func.max(O.day),
        )
        .group_by(O.reservoir_code, O.variable, O.source)
        .order_by(O.reservoir_code, O.variable, O.source)
    ).all()
    return [
        CoverageOut(
            reservoir_code=r[0],
            variable=r[1],
            source=r[2],
            observations=r[3],
            with_value=r[4],
            good=r[5],
            first_day=r[6],
            last_day=r[7],
        )
        for r in rows
    ]


@router.post(
    "/satellite/jobs",
    response_model=JobOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Lanzar una descarga satelital",
)
def launch_job(
    body: JobIn, request: Request, background: BackgroundTasks, session: DbSession, user: SatManager
) -> JobOut:
    codes = body.reservoir_codes or [
        r for (r,) in session.execute(select(Reservoir.code).order_by(Reservoir.code))
    ]
    unknown = set(codes) - {r for (r,) in session.execute(select(Reservoir.code))}
    if unknown:
        raise api_error(422, "UNKNOWN_RESERVOIR", f"Embalses inexistentes: {', '.join(sorted(unknown))}")
    kind = sat_ingest.KINDS[body.kind]
    try:
        sat_ingest.areas(session, codes, kind.scope)  # valida que existan las geometrías antes de encolar
    except sat_ingest.MissingGeometryError as exc:
        raise api_error(422, "MISSING_GEOMETRY", str(exc)) from None
    running = session.scalar(
        select(func.count())
        .select_from(Job)
        .where(Job.kind == f"satelite.{body.kind}", Job.status.in_(["PENDIENTE", "EN_CURSO"]))
    )
    if running:
        raise api_error(
            409, "JOB_RUNNING", "Ya hay una descarga de este tipo en curso. Espera a que termine."
        )

    params = {
        "tipo": body.kind,
        "embalses": codes,
        "desde": body.date_from.isoformat(),
        "hasta": body.date_to.isoformat(),
    }
    job = create_job(session, f"satelite.{body.kind}", params, user.id)
    log_action(
        session,
        "satellite.job",
        actor=user,
        entity="job",
        entity_id=str(job.id),
        new=params,
        ip=client_ip(request),
    )
    session.commit()

    def work(s, progress):
        return sat_ingest.run(s, body.kind, codes, body.date_from, body.date_to, progress)

    background.add_task(run_job, request.app.state.session_factory, job.id, work)
    return _job_out(job)


@router.get("/satellite/jobs", response_model=list[JobOut], summary="Últimas descargas")
def list_jobs(session: DbSession, _: SatReader) -> list[JobOut]:
    jobs = session.scalars(
        select(Job).where(Job.kind.startswith("satelite.")).order_by(Job.created_at.desc()).limit(20)
    ).all()
    return [_job_out(j) for j in jobs]


@router.get("/satellite/jobs/{job_id}", response_model=JobOut, summary="Estado de una descarga")
def get_job(job_id: uuid.UUID, session: DbSession, _: SatReader) -> JobOut:
    job = session.get(Job, job_id)
    if job is None:
        raise api_error(404, "NOT_FOUND", "Tarea no encontrada.")
    return _job_out(job)


# ------------------------------------------------------------------ series y resumen por embalse


@router.get(
    "/reservoirs/{code}/satellite/series",
    response_model=list[SeriesPoint],
    summary="Serie de una variable satelital",
)
def series(
    code: str,
    session: DbSession,
    user: PanelReader,
    variable: Variable,
    date_from: date | None = None,
    date_to: date | None = None,
    only_good: bool = Query(default=False, description="Solo observaciones de calidad buena"),
) -> list[SeriesPoint]:
    r = get_visible_reservoir(session, user, code)
    date_to = date_to or date.today()
    date_from = date_from or date_to - timedelta(days=90)
    stmt = select(SatelliteObservation).where(
        SatelliteObservation.reservoir_code == r.code,
        SatelliteObservation.variable == variable.value,
        SatelliteObservation.day >= date_from,
        SatelliteObservation.day <= date_to,
    )
    if only_good:
        stmt = stmt.where(SatelliteObservation.quality == "buena")
    rows = session.scalars(stmt.order_by(SatelliteObservation.day)).all()
    return [
        SeriesPoint(day=o.day, value=o.value, source=o.source, quality=o.quality, cloud_pct=o.cloud_pct)
        for o in rows
    ]


@router.get(
    "/reservoirs/{code}/satellite/summary",
    response_model=SatelliteSummary,
    summary="Indicadores satelitales recientes",
)
def summary(code: str, session: DbSession, user: PanelReader) -> SatelliteSummary:
    r = get_visible_reservoir(session, user, code)
    O = SatelliteObservation  # noqa: N806, E741
    base = select(O).where(O.reservoir_code == r.code)

    def latest(variable: Variable, good_only: bool = False) -> SatelliteObservation | None:
        stmt = base.where(O.variable == variable.value, O.value.is_not(None))
        if good_only:
            stmt = stmt.where(O.quality == "buena")
        return session.scalars(stmt.order_by(O.day.desc()).limit(1)).first()

    def precip_sum(lo: date, hi: date) -> float | None:
        return session.scalar(
            select(func.sum(O.value)).where(
                O.reservoir_code == r.code,
                O.variable == Variable.PRECIPITATION.value,
                O.day >= lo,
                O.day <= hi,
            )
        )

    last_rain = latest(Variable.PRECIPITATION)
    p7 = p30 = p30_normal = anomaly = None
    if last_rain:
        d = last_rain.day
        p7 = precip_sum(d - timedelta(days=6), d)
        p30 = precip_sum(d - timedelta(days=29), d)
        # "Normal": promedio del mismo período de 30 días en los años anteriores con datos
        past = [
            precip_sum(d.replace(year=y) - timedelta(days=29), d.replace(year=y))
            for y in range(2005, d.year)
            if not (d.month == 2 and d.day == 29)
        ]
        past = [p for p in past if p is not None]
        if past:
            p30_normal = sum(past) / len(past)
            anomaly = (p30 / p30_normal - 1) * 100 if p30 is not None and p30_normal else None

    soil = latest(Variable.SOIL_MOISTURE)
    soil_normal = None
    if soil:
        soil_normal = session.scalar(
            select(func.avg(O.value)).where(
                O.reservoir_code == r.code,
                O.variable == Variable.SOIL_MOISTURE.value,
                func.extract("month", O.day) == soil.day.month,
            )
        )
    water = latest(Variable.WATER_AREA, good_only=True)
    ndwi_obs = None
    if water:
        ndwi_obs = session.scalars(
            base.where(O.variable == Variable.NDWI.value, O.day == water.day, O.source == water.source)
        ).first()
    ref_area = session.scalar(
        select(func.ST_Area(func.Geography(Reservoir.geom)) / 1e6).where(Reservoir.code == r.code)
    )

    def rnd(v, n=1):
        return round(float(v), n) if v is not None else None

    return SatelliteSummary(
        reservoir_code=r.code,
        precipitation_7d_mm=rnd(p7),
        precipitation_30d_mm=rnd(p30),
        precipitation_30d_normal_mm=rnd(p30_normal),
        precipitation_30d_anomaly_pct=rnd(anomaly, 0),
        precipitation_last_day=last_rain.day if last_rain else None,
        soil_moisture=rnd(soil.value, 3) if soil else None,
        soil_moisture_day=soil.day if soil else None,
        soil_moisture_normal=rnd(soil_normal, 3),
        water_area_km2=rnd(water.value, 2) if water else None,
        water_area_day=water.day if water else None,
        water_area_source=water.source if water else None,
        water_area_reference_km2=rnd(ref_area, 2),
        ndwi=rnd(ndwi_obs.value, 3) if ndwi_obs else None,
        geometry_source=r.geom_source,
        basin_source=r.basin_source,
    )


__all__ = ["router", "UNITS"]
