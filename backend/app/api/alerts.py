"""Alertas tempranas (M9). Matriz §6: Gerencia y Operador consultan (y acusan recibo); el Ingeniero gestiona."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select

from app.api.deps import AppSettings, DbSession, api_error, client_ip, require
from app.api.reservoirs import visible_codes
from app.core.permissions import Access, Module
from app.models.alert import SEVERITIES, Alert, AlertAck, AlertRecipient
from app.models.reservoir import Reservoir
from app.models.user import User
from app.services import alerts as alert_service
from app.services import ml_service
from app.services.audit import log_action

router = APIRouter(prefix="/alerts", tags=["alertas"])

Reader = Annotated[User, Depends(require(Module.ALERTS, Access.READ))]
Manager = Annotated[User, Depends(require(Module.ALERTS, Access.MANAGE))]
CHANNELS = ("correo", "telegram", "sms", "whatsapp")


class AlertOut(BaseModel):
    id: int
    reservoir_code: str
    reservoir_name: str
    kind: str
    direction: str
    severity: str
    threshold: str
    threshold_level: float
    title: str
    message: str
    value: float | None
    horizon_days: int | None
    probability: float | None
    event_day: date
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
    acknowledged_by_me: bool
    acknowledgements: list[dict]
    deliveries: list[dict]


class RecipientIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    channel: Literal["correo", "telegram", "sms", "whatsapp"]
    target: str = Field(min_length=3, max_length=200)
    reservoir_code: str | None = None
    min_severity: Literal["informativa", "alerta", "critica"] = "alerta"
    active: bool = True

    @field_validator("target")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


class RecipientOut(RecipientIn):
    id: int


def _out(a: Alert, names: dict[str, str], me: User) -> AlertOut:
    return AlertOut(
        **{
            c: getattr(a, c)
            for c in (
                "id",
                "reservoir_code",
                "kind",
                "direction",
                "severity",
                "threshold",
                "threshold_level",
                "title",
                "message",
                "value",
                "horizon_days",
                "probability",
                "event_day",
                "created_at",
                "updated_at",
                "resolved_at",
            )
        },
        reservoir_name=names.get(a.reservoir_code, a.reservoir_code),
        acknowledged_by_me=any(k.user_id == me.id for k in a.acknowledgements),
        acknowledgements=[{"user": k.user_email, "at": k.at.isoformat()} for k in a.acknowledgements],
        deliveries=[
            {
                "channel": d.channel,
                "status": d.status,
                "to": d.recipient,
                "detail": d.detail,
                "at": d.at.isoformat(),
            }
            for d in a.deliveries
        ],
    )


def run_evaluation(request: Request, codes: list[str]) -> dict:
    """Evalúa con su propia sesión (se usa en segundo plano tras registrar o importar datos)."""
    settings = request.app.state.settings
    with request.app.state.session_factory() as session:
        return alert_service.evaluate(
            session,
            settings,
            codes,
            request.app.state.channels,
            lambda c: ml_service.forecast(session, settings, c),
        )


def schedule_evaluation(background: BackgroundTasks, request: Request, codes: list[str]) -> None:
    background.add_task(run_evaluation, request, codes)


@router.get("", response_model=list[AlertOut], summary="Alertas (activas o historial)")
def list_alerts(
    session: DbSession,
    user: Reader,
    active: bool | None = None,
    reservoir: str | None = None,
    severity: str | None = Query(default=None, pattern="^(informativa|alerta|critica)$"),
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[AlertOut]:
    stmt = select(Alert)
    visible = visible_codes(user)
    if visible is not None:
        stmt = stmt.where(Alert.reservoir_code.in_(visible))
    if active is True:
        stmt = stmt.where(Alert.resolved_at.is_(None))
    elif active is False:
        stmt = stmt.where(Alert.resolved_at.is_not(None))
    if reservoir:
        stmt = stmt.where(Alert.reservoir_code == reservoir.upper())
    if severity:
        stmt = stmt.where(Alert.severity == severity)
    if date_from:
        stmt = stmt.where(Alert.created_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        stmt = stmt.where(Alert.created_at < datetime.combine(date_to, datetime.max.time()))
    rows = session.scalars(
        stmt.order_by(Alert.resolved_at.is_not(None), Alert.created_at.desc()).limit(limit)
    ).all()
    rank = {s: i for i, s in enumerate(SEVERITIES)}
    rows = sorted(
        rows, key=lambda a: (a.resolved_at is not None, -rank[a.severity], -a.created_at.timestamp())
    )
    names = dict(session.execute(select(Reservoir.code, Reservoir.name)).all())
    return [_out(a, names, user) for a in rows]


@router.post("/{alert_id}/ack", response_model=AlertOut, summary="Acusar recibo de una alerta")
def acknowledge(alert_id: int, request: Request, session: DbSession, user: Reader) -> AlertOut:
    a = session.get(Alert, alert_id)
    visible = visible_codes(user)
    if a is None or (visible is not None and a.reservoir_code not in visible):
        raise api_error(404, "NOT_FOUND", "Alerta no encontrada.")
    if not any(k.user_id == user.id for k in a.acknowledgements):
        a.acknowledgements.append(AlertAck(user_id=user.id, user_email=user.email))
        log_action(session, "alert.ack", actor=user, entity="alert", entity_id=a.id, ip=client_ip(request))
        session.commit()
        session.refresh(a)
    names = dict(session.execute(select(Reservoir.code, Reservoir.name)).all())
    return _out(a, names, user)


@router.post("/evaluate", summary="Evaluar ahora las alertas de todos los embalses")
def evaluate_now(request: Request, session: DbSession, settings: AppSettings, user: Manager) -> dict:
    codes = [c for (c,) in session.execute(select(Reservoir.code).order_by(Reservoir.code))]
    result = alert_service.evaluate(
        session,
        settings,
        codes,
        request.app.state.channels,
        lambda c: ml_service.forecast(session, settings, c),
    )
    log_action(session, "alert.evaluate", actor=user, entity="alert", new=result, ip=client_ip(request))
    session.commit()
    return result


# ------------------------------------------------------------------ destinatarios


@router.get("/recipients", response_model=list[RecipientOut], summary="Destinatarios de alertas")
def list_recipients(session: DbSession, _: Manager) -> list[RecipientOut]:
    return [
        RecipientOut.model_validate(r, from_attributes=True)
        for r in session.scalars(select(AlertRecipient).order_by(AlertRecipient.name))
    ]


def _validate(session, body: RecipientIn) -> None:
    if body.reservoir_code and session.get(Reservoir, body.reservoir_code) is None:
        raise api_error(422, "UNKNOWN_RESERVOIR", "Embalse desconocido.")
    if body.channel == "correo" and "@" not in body.target:
        raise api_error(422, "INVALID_TARGET", "Escribe un correo válido.")


@router.post(
    "/recipients",
    response_model=RecipientOut,
    status_code=status.HTTP_201_CREATED,
    summary="Agregar destinatario",
)
def create_recipient(body: RecipientIn, request: Request, session: DbSession, user: Manager) -> RecipientOut:
    _validate(session, body)
    r = AlertRecipient(**body.model_dump())
    session.add(r)
    session.flush()
    log_action(
        session,
        "alert.recipient.create",
        actor=user,
        entity="alert_recipient",
        entity_id=r.id,
        new=body.model_dump(),
        ip=client_ip(request),
    )
    session.commit()
    return RecipientOut.model_validate(r, from_attributes=True)


@router.put("/recipients/{rid}", response_model=RecipientOut, summary="Editar destinatario")
def update_recipient(
    rid: int, body: RecipientIn, request: Request, session: DbSession, user: Manager
) -> RecipientOut:
    r = session.get(AlertRecipient, rid)
    if r is None:
        raise api_error(404, "NOT_FOUND", "Destinatario no encontrado.")
    _validate(session, body)
    old = RecipientIn.model_validate(r, from_attributes=True).model_dump()
    for k, v in body.model_dump().items():
        setattr(r, k, v)
    log_action(
        session,
        "alert.recipient.update",
        actor=user,
        entity="alert_recipient",
        entity_id=r.id,
        old=old,
        new=body.model_dump(),
        ip=client_ip(request),
    )
    session.commit()
    return RecipientOut.model_validate(r, from_attributes=True)


@router.delete("/recipients/{rid}", status_code=status.HTTP_204_NO_CONTENT, summary="Eliminar destinatario")
def delete_recipient(rid: int, request: Request, session: DbSession, user: Manager) -> None:
    r = session.get(AlertRecipient, rid)
    if r is None:
        raise api_error(404, "NOT_FOUND", "Destinatario no encontrado.")
    log_action(
        session,
        "alert.recipient.delete",
        actor=user,
        entity="alert_recipient",
        entity_id=r.id,
        old={"nombre": r.name, "canal": r.channel},
        ip=client_ip(request),
    )
    session.delete(r)
    session.commit()


@router.post("/recipients/{rid}/test", summary="Enviar un mensaje de prueba")
def test_recipient(rid: int, request: Request, session: DbSession, _: Manager) -> dict:
    r = session.get(AlertRecipient, rid)
    if r is None:
        raise api_error(404, "NOT_FOUND", "Destinatario no encontrado.")
    probe = Alert(
        reservoir_code=r.reservoir_code or "TULE",
        severity="informativa",
        title="Mensaje de prueba",
        message="Si recibes esto, el canal está bien configurado.",
        kind="observada",
        direction="escasez",
        threshold="prueba",
        threshold_level=0,
        event_day=date.today(),
        dedup_key="prueba",
    )
    result = request.app.state.channels[r.channel].send(probe, "Plataforma Hídrica Zulia", r.target)
    return {"status": result.status, "detail": result.detail}
