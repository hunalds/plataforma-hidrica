"""Embalses (M3): ficha, geometría, umbrales y curvas cota–área–volumen versionadas.

Permisos (matriz §6): Gerencia y Operador consultan; el Ingeniero gestiona.
Visibilidad: Gerencia ve todos los embalses; Ingeniero y Operador solo los que tienen asignados.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.api.deps import DbSession, api_error, client_ip, require
from app.core.permissions import Access, Module
from app.models.reservoir import ElevationCurve, ElevationCurvePoint, Reservoir, Threshold
from app.models.user import Role, User
from app.schemas.reservoir import (
    CurveDetail,
    CurvePointOut,
    CurveSummary,
    GeometryIn,
    InterpolationOut,
    ReservoirOut,
    ReservoirUpdate,
    ThresholdsIn,
    ThresholdsOut,
)
from app.services.audit import diff, log_action
from app.services.curves import (
    TEMPLATE_CSV,
    CurveFileError,
    CurveRangeError,
    current_curve,
    interpolator_for,
    parse_curve_file,
)

router = APIRouter(prefix="/reservoirs", tags=["embalses"])

Reader = Annotated[User, Depends(require(Module.RESERVOIRS, Access.READ))]
Manager = Annotated[User, Depends(require(Module.RESERVOIRS, Access.MANAGE))]


def _visible_codes(user: User) -> set[str] | None:
    """None = todos (Gerencia)."""
    return None if user.role == Role.GERENCIA else set(user.reservoir_codes)


def _get_visible(session: Session, user: User, code: str) -> Reservoir:
    reservoir = session.get(Reservoir, code.upper())
    visible = _visible_codes(user)
    # 404 también cuando no está asignado: no se revela qué embalses existen
    if reservoir is None or (visible is not None and reservoir.code not in visible):
        raise api_error(404, "NOT_FOUND", "Embalse no encontrado.")
    return reservoir


def _curve_summary(curve: ElevationCurve) -> CurveSummary:
    pts = curve.points
    return CurveSummary(
        id=curve.id,
        version=curve.version,
        valid_from=curve.valid_from,
        source_filename=curve.source_filename,
        notes=curve.notes,
        created_at=curve.created_at,
        points=len(pts),
        min_elevation=pts[0].elevation,
        max_elevation=pts[-1].elevation,
        max_volume_hm3=pts[-1].volume_hm3,
    )


def _reservoir_out(session: Session, r: Reservoir) -> ReservoirOut:
    curve = current_curve(session, r.code)
    dead_v = normal_v = None
    if curve:
        interp = interpolator_for(curve)
        try:
            dead_v = round(interp.volume_at(r.dead_level), 4)
            normal_v = round(interp.volume_at(r.normal_level), 4)
        except CurveRangeError:
            pass
    return ReservoirOut(
        code=r.code,
        name=r.name,
        basin=r.basin,
        description=r.description,
        records_start=r.records_start,
        normal_level=r.normal_level,
        dead_level=r.dead_level,
        has_geometry=r.geom is not None,
        has_basin_geometry=r.basin_geom is not None,
        thresholds=ThresholdsOut.model_validate(r.thresholds) if r.thresholds else ThresholdsOut(),
        current_curve=_curve_summary(curve) if curve else None,
        dead_volume_hm3=dead_v,
        normal_volume_hm3=normal_v,
        useful_capacity_hm3=round(normal_v - dead_v, 4)
        if dead_v is not None and normal_v is not None
        else None,
    )


# ------------------------------------------------------------------ ficha


@router.get("", response_model=list[ReservoirOut], summary="Listar los embalses visibles para el usuario")
def list_reservoirs(session: DbSession, user: Reader) -> list[ReservoirOut]:
    stmt = select(Reservoir).order_by(Reservoir.name)
    visible = _visible_codes(user)
    if visible is not None:
        stmt = stmt.where(Reservoir.code.in_(visible))
    return [_reservoir_out(session, r) for r in session.scalars(stmt).all()]


@router.get(
    "/curve-template.csv", response_class=PlainTextResponse, summary="Plantilla CSV de curva cota–volumen"
)
def curve_template(_: Reader) -> PlainTextResponse:
    return PlainTextResponse(
        TEMPLATE_CSV,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="plantilla_curva_cota_volumen.csv"'},
    )


@router.get("/{code}", response_model=ReservoirOut, summary="Ficha del embalse")
def get_reservoir(code: str, session: DbSession, user: Reader) -> ReservoirOut:
    return _reservoir_out(session, _get_visible(session, user, code))


def _ficha(r: Reservoir) -> dict[str, Any]:
    return {
        "name": r.name,
        "basin": r.basin,
        "description": r.description,
        "records_start": r.records_start.isoformat() if r.records_start else None,
        "normal_level": r.normal_level,
        "dead_level": r.dead_level,
    }


@router.patch("/{code}", response_model=ReservoirOut, summary="Editar la ficha del embalse")
def update_reservoir(
    code: str, body: ReservoirUpdate, request: Request, session: DbSession, user: Manager
) -> ReservoirOut:
    r = _get_visible(session, user, code)
    before = _ficha(r)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(r, field, value)
    if r.dead_level >= r.normal_level:
        raise api_error(422, "INVALID_LEVELS", "La cota de volumen muerto debe ser menor que la cota normal.")
    old, new = diff(before, _ficha(r))
    if new:
        log_action(
            session,
            "reservoir.update",
            actor=user,
            entity="reservoir",
            entity_id=r.code,
            old=old,
            new=new,
            ip=client_ip(request),
        )
    session.commit()
    return _reservoir_out(session, r)


# ------------------------------------------------------------------ geometría

_ALLOWED_GEOMS = {"Polygon", "MultiPolygon"}


def _extract_geometry(geojson: dict[str, Any]) -> dict[str, Any]:
    kind = geojson.get("type")
    if kind == "FeatureCollection":
        geoms = [f.get("geometry") or {} for f in geojson.get("features", [])]
        polys: list[Any] = []
        for g in geoms:
            if g.get("type") == "Polygon":
                polys.append(g["coordinates"])
            elif g.get("type") == "MultiPolygon":
                polys.extend(g["coordinates"])
            else:
                raise api_error(
                    422, "INVALID_GEOMETRY", "Solo se aceptan polígonos (Polygon o MultiPolygon)."
                )
        if not polys:
            raise api_error(422, "INVALID_GEOMETRY", "La colección no contiene polígonos.")
        return {"type": "MultiPolygon", "coordinates": polys}
    if kind == "Feature":
        return _extract_geometry(geojson.get("geometry") or {})
    if kind in _ALLOWED_GEOMS:
        return geojson
    raise api_error(422, "INVALID_GEOMETRY", "Solo se aceptan polígonos (Polygon o MultiPolygon) en GeoJSON.")


@router.put(
    "/{code}/geometry",
    response_model=ReservoirOut,
    summary="Cargar el polígono (GeoJSON) del embalse o su cuenca",
)
def set_geometry(
    code: str, body: GeometryIn, request: Request, session: DbSession, user: Manager
) -> ReservoirOut:
    r = _get_visible(session, user, code)
    geometry = _extract_geometry(body.geojson)
    gj = json.dumps(geometry)
    try:
        valid, inside_wgs84 = session.execute(
            select(
                func.ST_IsValid(func.ST_GeomFromGeoJSON(gj)),
                func.ST_Within(
                    func.ST_SetSRID(func.ST_GeomFromGeoJSON(gj), 4326),
                    func.ST_MakeEnvelope(-180, -90, 180, 90, 4326),
                ),
            )
        ).one()
    except DBAPIError:
        session.rollback()
        raise api_error(422, "INVALID_GEOMETRY", "El GeoJSON no se pudo interpretar.") from None
    if not valid:
        raise api_error(
            422, "INVALID_GEOMETRY", "El polígono no es válido (se cruza a sí mismo o está mal cerrado)."
        )
    if not inside_wgs84:
        raise api_error(
            422, "INVALID_GEOMETRY", "Las coordenadas deben estar en grados WGS84 (longitud, latitud)."
        )

    value = func.ST_Multi(func.ST_SetSRID(func.ST_GeomFromGeoJSON(gj), 4326))
    if body.kind == "reservoir":
        r.geom = value
    else:
        r.basin_geom = value
    log_action(
        session,
        "reservoir.geometry",
        actor=user,
        entity="reservoir",
        entity_id=r.code,
        new={"tipo": body.kind},
        ip=client_ip(request),
    )
    session.commit()
    session.refresh(r)
    return _reservoir_out(session, r)


@router.get("/{code}/geometry", summary="Polígono del embalse o su cuenca en GeoJSON")
def get_geometry(
    code: str,
    session: DbSession,
    user: Reader,
    kind: Annotated[str, Query(pattern="^(reservoir|basin)$")] = "reservoir",
) -> dict[str, Any]:
    r = _get_visible(session, user, code)
    column = Reservoir.geom if kind == "reservoir" else Reservoir.basin_geom
    raw = session.scalar(select(func.ST_AsGeoJSON(column)).where(Reservoir.code == r.code))
    if raw is None:
        raise api_error(404, "NO_GEOMETRY", "Este embalse aún no tiene polígono cargado.")
    return {
        "type": "Feature",
        "properties": {"code": r.code, "name": r.name, "kind": kind},
        "geometry": json.loads(raw),
    }


# ------------------------------------------------------------------ umbrales


@router.get("/{code}/thresholds", response_model=ThresholdsOut, summary="Umbrales del embalse")
def get_thresholds(code: str, session: DbSession, user: Reader) -> ThresholdsOut:
    r = _get_visible(session, user, code)
    return ThresholdsOut.model_validate(r.thresholds) if r.thresholds else ThresholdsOut()


@router.put("/{code}/thresholds", response_model=ThresholdsOut, summary="Definir los umbrales del embalse")
def set_thresholds(
    code: str, body: ThresholdsIn, request: Request, session: DbSession, user: Manager
) -> ThresholdsOut:
    r = _get_visible(session, user, code)
    if body.low_critical is not None and body.low_critical < r.dead_level:
        raise api_error(
            422,
            "INVALID_THRESHOLDS",
            f"El nivel crítico bajo no puede estar por debajo del volumen muerto ({r.dead_level}).",
        )
    t = r.thresholds or Threshold(reservoir_code=r.code)
    before = {k: getattr(t, k) for k in ThresholdsIn.ORDER}
    for k in ThresholdsIn.ORDER:
        setattr(t, k, getattr(body, k))
    t.updated_by = user.id
    r.thresholds = t
    old, new = diff(before, {k: getattr(t, k) for k in ThresholdsIn.ORDER})
    if new:
        log_action(
            session,
            "threshold.update",
            actor=user,
            entity="reservoir",
            entity_id=r.code,
            old=old,
            new=new,
            ip=client_ip(request),
        )
    session.commit()
    session.refresh(t)
    return ThresholdsOut.model_validate(t)


# ------------------------------------------------------------------ curvas


@router.get(
    "/{code}/curves", response_model=list[CurveSummary], summary="Versiones de la curva cota–área–volumen"
)
def list_curves(code: str, session: DbSession, user: Reader) -> list[CurveSummary]:
    r = _get_visible(session, user, code)
    curves = session.scalars(
        select(ElevationCurve)
        .where(ElevationCurve.reservoir_code == r.code)
        .order_by(ElevationCurve.version.desc())
    ).all()
    return [_curve_summary(c) for c in curves]


@router.post(
    "/{code}/curves",
    response_model=CurveSummary,
    status_code=status.HTTP_201_CREATED,
    summary="Cargar una nueva versión de la curva desde CSV o Excel",
)
async def upload_curve(
    code: str,
    request: Request,
    session: DbSession,
    user: Manager,
    file: Annotated[
        UploadFile, File(description="Archivo .csv o .xlsx con columnas cota, volumen y (opcional) área")
    ],
    valid_from: Annotated[date, Form(description="Fecha desde la que rige esta curva")],
    notes: Annotated[str | None, Form(max_length=2000)] = None,
) -> CurveSummary:
    r = _get_visible(session, user, code)
    content = await file.read()
    try:
        points = parse_curve_file(content, file.filename or "")
    except CurveFileError as exc:
        raise api_error(422, "INVALID_CURVE_FILE", str(exc) + _rows_text(exc.rows)) from None

    last = (
        session.scalar(
            select(func.max(ElevationCurve.version)).where(ElevationCurve.reservoir_code == r.code)
        )
        or 0
    )
    curve = ElevationCurve(
        reservoir_code=r.code,
        version=last + 1,
        valid_from=valid_from,
        source_filename=(file.filename or "")[:255],
        notes=notes,
        created_by=user.id,
        points=[
            ElevationCurvePoint(elevation=p.elevation, area_km2=p.area_km2, volume_hm3=p.volume_hm3)
            for p in points
        ],
    )
    session.add(curve)
    session.flush()
    log_action(
        session,
        "curve.upload",
        actor=user,
        entity="reservoir",
        entity_id=r.code,
        new={
            "version": curve.version,
            "valid_from": valid_from.isoformat(),
            "puntos": len(points),
            "archivo": curve.source_filename,
        },
        ip=client_ip(request),
    )
    session.commit()
    session.refresh(curve)
    return _curve_summary(curve)


def _rows_text(rows: list[tuple[int, str]]) -> str:
    if not rows:
        return ""
    parts = [(f"Fila {n}: {msg}" if n else msg) for n, msg in rows[:10]]
    more = f" (y {len(rows) - 10} más)" if len(rows) > 10 else ""
    return " " + " | ".join(parts) + more


@router.get(
    "/{code}/curves/interpolate",
    response_model=InterpolationOut,
    summary="Convertir cota ↔ volumen con la curva vigente",
)
def interpolate(
    code: str,
    session: DbSession,
    user: Reader,
    cota: float | None = None,
    volumen: float | None = Query(default=None, ge=0),
    fecha: date | None = Query(
        default=None, description="Usa la curva vigente en esta fecha (por defecto, hoy)"
    ),
) -> InterpolationOut:
    r = _get_visible(session, user, code)
    if (cota is None) == (volumen is None):
        raise api_error(422, "BAD_QUERY", "Indica exactamente uno de los parámetros: cota o volumen.")
    curve = current_curve(session, r.code, fecha)
    if curve is None:
        raise api_error(404, "NO_CURVE", "No hay una curva vigente para esa fecha.")
    interp = interpolator_for(curve)
    try:
        elevation = cota if cota is not None else interp.elevation_at(volumen)  # type: ignore[arg-type]
        volume = interp.volume_at(elevation)
        area = interp.area_at(elevation)
    except CurveRangeError as exc:
        raise api_error(422, "OUT_OF_RANGE", str(exc)) from None
    return InterpolationOut(
        reservoir_code=r.code,
        curve_version=curve.version,
        elevation=round(elevation, 4),
        volume_hm3=round(volume, 4),
        area_km2=round(area, 4) if area is not None else None,
    )


@router.get(
    "/{code}/curves/{version}", response_model=CurveDetail, summary="Puntos de una versión de la curva"
)
def get_curve(code: str, version: int, session: DbSession, user: Reader) -> CurveDetail:
    r = _get_visible(session, user, code)
    curve = session.scalar(
        select(ElevationCurve).where(
            ElevationCurve.reservoir_code == r.code, ElevationCurve.version == version
        )
    )
    if curve is None:
        raise api_error(404, "NOT_FOUND", "Versión de curva no encontrada.")
    return CurveDetail(
        **_curve_summary(curve).model_dump(),
        data=[
            CurvePointOut(elevation=p.elevation, area_km2=p.area_km2, volume_hm3=p.volume_hm3)
            for p in curve.points
        ],
    )
