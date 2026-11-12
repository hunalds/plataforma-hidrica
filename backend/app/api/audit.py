"""Consulta de la bitácora de auditoría (M1) — solo Gerencia."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select

from app.api.deps import DbSession, require
from app.core.permissions import Access, Module
from app.models.audit import AuditLog
from app.models.user import User

router = APIRouter(prefix="/audit", tags=["auditoría"])


class AuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    user_id: int | None
    user_email: str | None
    action: str
    entity: str | None
    entity_id: str | None
    old_value: dict[str, Any] | None
    new_value: dict[str, Any] | None
    ip: str | None


class AuditListOut(BaseModel):
    items: list[AuditOut]
    total: int


@router.get("", response_model=AuditListOut, summary="Consultar la bitácora de auditoría")
def list_audit(
    session: DbSession,
    _: Annotated[User, Depends(require(Module.AUDIT, Access.READ))],
    user_id: int | None = None,
    action: str | None = Query(default=None, max_length=60, description="Prefijo, p. ej. 'login' o 'user.'"),
    entity: str | None = Query(default=None, max_length=60),
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> AuditListOut:
    stmt = select(AuditLog)
    if user_id is not None:
        stmt = stmt.where(AuditLog.user_id == user_id)
    if action:
        stmt = stmt.where(AuditLog.action.startswith(action))
    if entity:
        stmt = stmt.where(AuditLog.entity == entity)
    if date_from:
        stmt = stmt.where(AuditLog.created_at >= datetime.combine(date_from, time.min))
    if date_to:
        stmt = stmt.where(AuditLog.created_at < datetime.combine(date_to + timedelta(days=1), time.min))
    total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = session.scalars(
        stmt.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(limit).offset(offset)
    ).all()
    return AuditListOut(items=[AuditOut.model_validate(r) for r in rows], total=total)
