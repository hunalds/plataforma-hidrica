"""Movimiento diario por embalse: registro manual, consulta, estado operativo y balance (M4, M12).

- POST/PATCH registro manual: roles con M4 = MANAGE (Ingeniero y Operador). El Operador solo
  corrige registros propios del mismo día de carga (24 h).
- Estado y balance: lectura de M12 (todos los roles).
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import DbSession, api_error, client_ip, require
from app.api.reservoirs import get_visible_reservoir, visible_codes
from app.core.permissions import Access, Module
from app.core.security import utcnow
from app.models.measurement import DailyMeasurement, MeasurementSource
from app.models.reservoir import ElevationCurve, Reservoir
from app.models.user import Role, User
from app.services import hydro_calcs as hc
from app.services.audit import diff, log_action
from app.services.curves import CurveRangeError
from app.services.ingest import CurveBook, RawRow, issues_to_json, save_rows, validate

router = APIRouter(prefix="/reservoirs", tags=["movimiento diario"])

IngestManager = Annotated[User, Depends(require(Module.HYDRO_INGEST, Access.MANAGE))]
IngestReader = Annotated[User, Depends(require(Module.HYDRO_INGEST, Access.READ))]
CalcReader = Annotated[User, Depends(require(Module.CALCS, Access.READ))]

STALE_AFTER_DAYS = 2  # el último dato se considera desactualizado después de 2 días


class MeasurementIn(BaseModel):
    day: date
    reading_time: time | None = None
    level_m: float = Field(description="Cota (m.s.n.m.)")
    volume_hm3: float | None = None
    inflow_m3s: float | None = None
    outflow_m3s: float | None = None
    eco_flow_m3s: float | None = None
    gate_opening_pct: float | None = None
    intake_m3s: float | None = None
    notes: str | None = Field(default=None, max_length=2000)


class MeasurementPatch(BaseModel):
    reading_time: time | None = None
    level_m: float | None = None
    volume_hm3: float | None = None
    inflow_m3s: float | None = None
    outflow_m3s: float | None = None
    eco_flow_m3s: float | None = None
    gate_opening_pct: float | None = None
    intake_m3s: float | None = None
    notes: str | None = Field(default=None, max_length=2000)


class MeasurementOut(BaseModel):
    day: date
    reading_time: time | None
    level_m: float
    volume_hm3: float | None
    volume_source: str | None
    inflow_m3s: float | None
    outflow_m3s: float | None
    eco_flow_m3s: float | None
    gate_opening_pct: float | None
    intake_m3s: float | None
    notes: str | None
    quality_flags: list[str] | None
    source: str
    created_at: datetime
    # Calculados (M12) con la curva vigente
    useful_volume_hm3: float | None = None
    availability_pct: float | None = None
    reserve_days: float | None = None
    spill_hm3: float | None = None


class SavedMeasurementOut(BaseModel):
    measurement: MeasurementOut
    warnings: list[dict]


class StatusOut(BaseModel):
    reservoir_code: str
    reservoir_name: str
    last_day: date | None
    last_reading_time: time | None
    days_since_last: int | None
    is_stale: bool
    level_m: float | None
    volume_hm3: float | None
    dead_volume_hm3: float | None
    normal_volume_hm3: float | None
    useful_volume_hm3: float | None
    useful_capacity_hm3: float | None
    availability_pct: float | None
    reserve_days: float | None
    spill_hm3: float | None
    is_spilling: bool | None
    inflow_m3s: float | None
    outflow_m3s: float | None
    eco_flow_m3s: float | None
    light: str
    direction: str
    light_reason: str
    thresholds_defined: bool
    level_change_7d_m: float | None
    curve_version: int | None
    missing_curve: bool


class BalanceDayOut(BaseModel):
    day: date
    level_m: float
    volume_hm3: float | None
    inflow_hm3: float
    outflow_hm3: float
    eco_hm3: float
    net_hm3: float
    observed_change_hm3: float | None
    spill_estimate_hm3: float
    residual_hm3: float | None


class BalanceOut(BaseModel):
    reservoir_code: str
    date_from: date
    date_to: date
    days: list[BalanceDayOut]
    totals: dict[str, float | None]
    note: str


# ------------------------------------------------------------------ utilidades


def _book(session: Session, code: str) -> CurveBook:
    return CurveBook(
        list(session.scalars(select(ElevationCurve).where(ElevationCurve.reservoir_code == code)).all())
    )


def _with_calcs(m: DailyMeasurement, res: Reservoir, book: CurveBook) -> MeasurementOut:
    out = MeasurementOut.model_validate(m, from_attributes=True)
    curve = book.for_day(m.day)
    if curve is None:
        return out
    _, interp = curve
    try:
        s = hc.operational_status(
            level_m=m.level_m,
            volume_hm3=m.volume_hm3,
            normal_level=res.normal_level,
            dead_level=res.dead_level,
            volume_at=interp.volume_at,
            outflow_m3s=m.outflow_m3s,
            eco_flow_m3s=m.eco_flow_m3s,
        )
    except CurveRangeError:
        return out
    out.useful_volume_hm3 = round(s.useful_volume_hm3, 4)
    out.availability_pct = round(s.availability_pct, 2) if s.availability_pct is not None else None
    out.reserve_days = round(s.reserve_days, 1) if s.reserve_days is not None else None
    out.spill_hm3 = round(s.spill_hm3, 4)
    return out


def _get_measurement(session: Session, code: str, day: date) -> DailyMeasurement:
    m = session.scalar(
        select(DailyMeasurement).where(DailyMeasurement.reservoir_code == code, DailyMeasurement.day == day)
    )
    if m is None:
        raise api_error(404, "NOT_FOUND", "No hay registro para esa fecha.")
    return m


def _snapshot(m: DailyMeasurement) -> dict:
    fields = (
        "level_m",
        "volume_hm3",
        "inflow_m3s",
        "outflow_m3s",
        "eco_flow_m3s",
        "gate_opening_pct",
        "intake_m3s",
        "notes",
    )
    data = {f: getattr(m, f) for f in fields}
    data["reading_time"] = m.reading_time.isoformat(timespec="minutes") if m.reading_time else None
    return data


# ------------------------------------------------------------------ consulta


@router.get(
    "/{code}/measurements", response_model=list[MeasurementOut], summary="Movimiento diario del embalse"
)
def list_measurements(
    code: str,
    session: DbSession,
    user: IngestReader,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(default=60, ge=1, le=10_000),
) -> list[MeasurementOut]:
    res = get_visible_reservoir(session, user, code)
    stmt = select(DailyMeasurement).where(DailyMeasurement.reservoir_code == res.code)
    if date_from:
        stmt = stmt.where(DailyMeasurement.day >= date_from)
    if date_to:
        stmt = stmt.where(DailyMeasurement.day <= date_to)
    rows = session.scalars(stmt.order_by(DailyMeasurement.day.desc()).limit(limit)).all()
    book = _book(session, res.code)
    return [_with_calcs(m, res, book) for m in rows]


# ------------------------------------------------------------------ registro manual (HU-2.5)


@router.post(
    "/{code}/measurements",
    response_model=SavedMeasurementOut,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar el movimiento del día (registro manual)",
)
def create_measurement(
    code: str, body: MeasurementIn, request: Request, session: DbSession, user: IngestManager
) -> SavedMeasurementOut:
    res = get_visible_reservoir(session, user, code)
    allowed = None if user.role == Role.GERENCIA else set(user.reservoir_codes)
    raw = RawRow(
        row=None,
        reservoir=res.code,
        day=body.day,
        time=body.reading_time,
        **body.model_dump(exclude={"day", "reading_time"}),
    )
    result = validate(session, [raw], allowed_codes=allowed)
    errors = [i for i in result.issues if i.severity == "error"]
    if errors:
        raise api_error(422, "INVALID_MEASUREMENT", " ".join(i.message for i in errors))
    row = result.rows[0]
    if row["_exists"]:
        raise api_error(
            409,
            "ALREADY_EXISTS",
            f"Ya existe un registro del {body.day.isoformat()}. Corrígelo en lugar de crear otro.",
        )
    save_rows(session, [row], overwrite=False, source=MeasurementSource.MANUAL, user_id=user.id)
    warnings = [i for i in result.issues if i.severity == "aviso" and i.code != "MISSING_DAYS"]
    log_action(
        session,
        "measurement.create",
        actor=user,
        entity="measurement",
        entity_id=f"{res.code}:{body.day.isoformat()}",
        new={k: row[k] for k in ("level_m", "volume_hm3", "inflow_m3s", "outflow_m3s", "eco_flow_m3s")},
        ip=client_ip(request),
    )
    session.commit()
    m = _get_measurement(session, res.code, body.day)
    return SavedMeasurementOut(
        measurement=_with_calcs(m, res, _book(session, res.code)), warnings=issues_to_json(warnings)
    )


@router.patch(
    "/{code}/measurements/{day}", response_model=SavedMeasurementOut, summary="Corregir un registro"
)
def update_measurement(
    code: str, day: date, body: MeasurementPatch, request: Request, session: DbSession, user: IngestManager
) -> SavedMeasurementOut:
    res = get_visible_reservoir(session, user, code)
    m = _get_measurement(session, res.code, day)
    if user.role == Role.OPERADOR and (
        m.created_by != user.id or utcnow() - m.created_at > timedelta(hours=24)
    ):
        raise api_error(
            403,
            "FORBIDDEN",
            "El Operador solo puede corregir sus propios registros durante las primeras 24 horas.",
        )

    before = _snapshot(m)
    merged = {**before, **body.model_dump(exclude_unset=True)}
    if isinstance(merged.get("reading_time"), str):
        merged["reading_time"] = time.fromisoformat(merged["reading_time"])
    # Si cambió la cota y el volumen venía de la curva, se recalcula
    if (
        "level_m" in body.model_fields_set
        and "volume_hm3" not in body.model_fields_set
        and m.volume_source == "CURVA"
    ):
        merged["volume_hm3"] = None
    raw = RawRow(row=None, reservoir=res.code, day=day, time=merged.pop("reading_time"), **merged)
    result = validate(session, [raw], allowed_codes=None)
    errors = [i for i in result.issues if i.severity == "error"]
    if errors:
        raise api_error(422, "INVALID_MEASUREMENT", " ".join(i.message for i in errors))
    save_rows(session, result.rows, overwrite=True, source=m.source, user_id=m.created_by)
    session.flush()
    session.refresh(m)
    old, new = diff(before, _snapshot(m))
    if new:
        log_action(
            session,
            "measurement.update",
            actor=user,
            entity="measurement",
            entity_id=f"{res.code}:{day.isoformat()}",
            old=old,
            new=new,
            ip=client_ip(request),
        )
    session.commit()
    warnings = [
        i for i in result.issues if i.severity == "aviso" and i.code not in ("MISSING_DAYS", "EXISTS")
    ]
    return SavedMeasurementOut(
        measurement=_with_calcs(m, res, _book(session, res.code)), warnings=issues_to_json(warnings)
    )


# ------------------------------------------------------------------ estado operativo (M12)


def _status(session: Session, res: Reservoir, today: date) -> StatusOut:
    last = session.scalar(
        select(DailyMeasurement)
        .where(DailyMeasurement.reservoir_code == res.code)
        .order_by(DailyMeasurement.day.desc())
        .limit(1)
    )
    t = res.thresholds
    th = {k: getattr(t, k) if t else None for k in ("low_critical", "low_alert", "high_alert", "spill_level")}
    light = hc.traffic_light(
        last.level_m if last else None, normal_level=res.normal_level, dead_level=res.dead_level, **th
    )
    base = {
        "reservoir_code": res.code,
        "reservoir_name": res.name,
        "light": light.light.value,
        "direction": light.direction.value,
        "light_reason": light.reason,
        "thresholds_defined": light.thresholds_defined,
    }
    empty = dict.fromkeys(
        (
            "last_day", "last_reading_time", "days_since_last", "level_m", "volume_hm3",
            "dead_volume_hm3", "normal_volume_hm3", "useful_volume_hm3", "useful_capacity_hm3",
            "availability_pct", "reserve_days", "spill_hm3", "is_spilling", "inflow_m3s", "outflow_m3s",
            "eco_flow_m3s", "level_change_7d_m", "curve_version",
        )
    )  # fmt: skip
    if last is None:
        return StatusOut(**base, **empty, is_stale=True, missing_curve=False)

    days_since = (today - last.day).days
    week_ago = session.scalar(
        select(DailyMeasurement.level_m).where(
            DailyMeasurement.reservoir_code == res.code, DailyMeasurement.day == last.day - timedelta(days=7)
        )
    )
    out = {
        **base,
        **empty,
        "last_day": last.day,
        "last_reading_time": last.reading_time,
        "days_since_last": days_since,
        "is_stale": days_since > STALE_AFTER_DAYS,
        "level_m": last.level_m,
        "volume_hm3": last.volume_hm3,
        "inflow_m3s": last.inflow_m3s,
        "outflow_m3s": last.outflow_m3s,
        "eco_flow_m3s": last.eco_flow_m3s,
        "level_change_7d_m": round(last.level_m - week_ago, 2) if week_ago is not None else None,
    }
    curve = _book(session, res.code).for_day(last.day)
    if curve is None:
        return StatusOut(**out, missing_curve=True)
    version, interp = curve
    try:
        s = hc.operational_status(
            level_m=last.level_m,
            volume_hm3=last.volume_hm3,
            normal_level=res.normal_level,
            dead_level=res.dead_level,
            volume_at=interp.volume_at,
            outflow_m3s=last.outflow_m3s,
            eco_flow_m3s=last.eco_flow_m3s,
        )
    except CurveRangeError:
        return StatusOut(**out, missing_curve=True)
    out.update(
        volume_hm3=round(s.volume_hm3, 3),
        dead_volume_hm3=round(s.dead_volume_hm3, 3),
        normal_volume_hm3=round(s.normal_volume_hm3, 3),
        useful_volume_hm3=round(s.useful_volume_hm3, 3),
        useful_capacity_hm3=round(s.useful_capacity_hm3, 3),
        availability_pct=round(s.availability_pct, 1) if s.availability_pct is not None else None,
        reserve_days=round(s.reserve_days) if s.reserve_days is not None else None,
        spill_hm3=round(s.spill_hm3, 3),
        is_spilling=s.is_spilling,
        curve_version=version,
    )
    return StatusOut(**out, missing_curve=False)


@router.get("/status", response_model=list[StatusOut], summary="Estado operativo de los embalses visibles")
def all_status(session: DbSession, user: CalcReader) -> list[StatusOut]:
    stmt = select(Reservoir).order_by(Reservoir.name)
    visible = visible_codes(user)
    if visible is not None:
        stmt = stmt.where(Reservoir.code.in_(visible))
    today = date.today()
    return [_status(session, r, today) for r in session.scalars(stmt).all()]


@router.get("/{code}/status", response_model=StatusOut, summary="Estado operativo actual (último dato)")
def reservoir_status(code: str, session: DbSession, user: CalcReader) -> StatusOut:
    return _status(session, get_visible_reservoir(session, user, code), date.today())


@router.get("/{code}/balance", response_model=BalanceOut, summary="Balance hídrico diario")
def balance(
    code: str,
    session: DbSession,
    user: CalcReader,
    date_from: date | None = None,
    date_to: date | None = None,
) -> BalanceOut:
    res = get_visible_reservoir(session, user, code)
    if date_to is None:
        date_to = (
            session.scalar(
                select(DailyMeasurement.day)
                .where(DailyMeasurement.reservoir_code == res.code)
                .order_by(DailyMeasurement.day.desc())
                .limit(1)
            )
            or date.today()
        )
    date_from = date_from or date_to - timedelta(days=30)
    if (date_to - date_from).days > 3660:
        raise api_error(422, "RANGE_TOO_LONG", "El rango máximo del balance es de 10 años.")
    rows = session.scalars(
        select(DailyMeasurement)
        .where(
            DailyMeasurement.reservoir_code == res.code,
            DailyMeasurement.day >= date_from - timedelta(days=1),
            DailyMeasurement.day <= date_to,
        )
        .order_by(DailyMeasurement.day)
    ).all()
    by_day = {m.day: m for m in rows}
    days: list[BalanceDayOut] = []
    for m in rows:
        if m.day < date_from:
            continue
        prev = by_day.get(m.day - timedelta(days=1))
        b = hc.daily_balance(
            volume_today_hm3=m.volume_hm3,
            volume_yesterday_hm3=prev.volume_hm3 if prev else None,
            inflow_m3s=m.inflow_m3s,
            outflow_m3s=m.outflow_m3s,
            eco_flow_m3s=m.eco_flow_m3s,
            level_m=m.level_m,
            normal_level_m=res.normal_level,
        )
        days.append(
            BalanceDayOut(
                day=m.day,
                level_m=m.level_m,
                volume_hm3=m.volume_hm3,
                inflow_hm3=round(b.inflow_hm3, 4),
                outflow_hm3=round(b.outflow_hm3, 4),
                eco_hm3=round(b.eco_hm3, 4),
                net_hm3=round(b.net_hm3, 4),
                observed_change_hm3=round(b.observed_change_hm3, 4)
                if b.observed_change_hm3 is not None
                else None,
                spill_estimate_hm3=round(b.spill_estimate_hm3, 4),
                residual_hm3=round(b.residual_hm3, 4) if b.residual_hm3 is not None else None,
            )
        )

    def total(attr: str) -> float | None:
        vals = [getattr(d, attr) for d in days if getattr(d, attr) is not None]
        return round(sum(vals), 3) if vals else None

    return BalanceOut(
        reservoir_code=res.code,
        date_from=date_from,
        date_to=date_to,
        days=days,
        totals={
            k: total(k)
            for k in (
                "inflow_hm3",
                "outflow_hm3",
                "eco_hm3",
                "net_hm3",
                "observed_change_hm3",
                "spill_estimate_hm3",
                "residual_hm3",
            )
        },
        note=(
            "Fórmulas por validar con MINAGUAS (P-09 a P-13). El alivio diario se estima en días con la cota "
            "sobre el nivel normal; el residuo incluye evaporación, filtraciones y errores de medición."
        ),
    )
