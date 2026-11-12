"""Reportes y exportación (M10). Matriz §6: Gerencia e Ingeniero gestionan; el Operador no tiene acceso."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response

from app.api.deps import AppSettings, DbSession, api_error, client_ip, require
from app.api.reservoirs import get_visible_reservoir, visible_codes
from app.core.permissions import Access, Module
from app.models.user import User
from app.services import ml_service
from app.services import reports as rep
from app.services.audit import log_action

router = APIRouter(prefix="/reports", tags=["reportes"])

Reporter = Annotated[User, Depends(require(Module.REPORTS, Access.MANAGE))]
Fmt = Literal["pdf", "xlsx", "csv", "png", "geojson", "kml"]


def _send(report: rep.Report, fmt: str, request: Request, session, user: User, kind: str) -> Response:
    try:
        content = rep.render(report, fmt)
    except rep.ReportError as exc:
        raise api_error(422, "REPORT_ERROR", str(exc)) from None
    log_action(
        session,
        "report.export",
        actor=user,
        entity="report",
        entity_id=kind,
        new={"formato": fmt, "archivo": report.filename},
        ip=client_ip(request),
    )
    session.commit()
    ext = "xlsx" if fmt == "xlsx" else fmt
    return Response(
        content,
        media_type=rep.FORMATS[fmt],
        headers={"Content-Disposition": f'attachment; filename="{report.filename}.{ext}"'},
    )


def _range(date_from: date | None, date_to: date | None, default_days: int = 30) -> tuple[date, date]:
    end = date_to or date.today()
    start = date_from or end - timedelta(days=default_days)
    if start > end:
        raise api_error(422, "BAD_RANGE", "La fecha inicial es posterior a la final.")
    if (end - start).days > 3660:
        raise api_error(422, "RANGE_TOO_LONG", "El rango máximo es de 10 años.")
    return start, end


@router.get("/bulletin", summary="Boletín diario del estado de los embalses")
def bulletin(
    request: Request, session: DbSession, user: Reporter, format: Fmt = "pdf", day: date | None = None
) -> Response:
    return _send(rep.bulletin(session, visible_codes(user), day), format, request, session, user, "boletin")


@router.get("/prediction/{code}", summary="Reporte de predicción de un embalse")
def prediction(
    code: str,
    request: Request,
    session: DbSession,
    settings: AppSettings,
    user: Reporter,
    format: Fmt = "pdf",
) -> Response:
    r = get_visible_reservoir(session, user, code)
    try:
        forecast = ml_service.forecast(session, settings, r.code)
    except ml_service.MLDataError as exc:
        raise api_error(404, "NO_FORECAST", str(exc)) from None
    return _send(rep.prediction(session, forecast, r), format, request, session, user, "prediccion")


@router.get("/historical/{code}", summary="Histórico comparativo entre dos períodos")
def historical(
    code: str,
    request: Request,
    session: DbSession,
    user: Reporter,
    a_from: date,
    a_to: date,
    b_from: date,
    b_to: date,
    format: Fmt = "pdf",
) -> Response:
    r = get_visible_reservoir(session, user, code)
    return _send(
        rep.historical(session, r, _range(a_from, a_to), _range(b_from, b_to)),
        format,
        request,
        session,
        user,
        "historico",
    )


@router.get("/comparison", summary="Comparativo entre embalses")
def comparison(
    request: Request,
    session: DbSession,
    user: Reporter,
    date_from: date | None = None,
    date_to: date | None = None,
    format: Fmt = "pdf",
) -> Response:
    start, end = _range(date_from, date_to, 365)
    try:
        report = rep.between(session, visible_codes(user), start, end)
    except rep.ReportError as exc:
        raise api_error(422, "REPORT_ERROR", str(exc)) from None
    return _send(report, format, request, session, user, "comparativo")


@router.get("/alerts", summary="Registro de alertas")
def alerts(
    request: Request,
    session: DbSession,
    user: Reporter,
    date_from: date | None = None,
    date_to: date | None = None,
    format: Fmt = Query(default="pdf"),
) -> Response:
    start, end = _range(date_from, date_to, 90)
    return _send(
        rep.alerts_log(session, visible_codes(user), start, end), format, request, session, user, "alertas"
    )
