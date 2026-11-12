"""Registro en la bitácora de auditoría (M1). El commit lo hace quien llama, junto con el cambio auditado."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.user import User

# Campos que nunca se guardan en la bitácora
_SECRET_FIELDS = {"password", "password_hash", "new_password", "current_password", "token", "token_hash"}


def _clean(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return {k: v for k, v in value.items() if k not in _SECRET_FIELDS}


def log_action(
    session: Session,
    action: str,
    *,
    actor: User | None = None,
    actor_email: str | None = None,
    entity: str | None = None,
    entity_id: str | int | None = None,
    old: dict[str, Any] | None = None,
    new: dict[str, Any] | None = None,
    ip: str | None = None,
) -> AuditLog:
    entry = AuditLog(
        user_id=actor.id if actor else None,
        user_email=actor.email if actor else actor_email,
        action=action,
        entity=entity,
        entity_id=str(entity_id) if entity_id is not None else None,
        old_value=_clean(old),
        new_value=_clean(new),
        ip=ip,
    )
    session.add(entry)
    return entry


def diff(old: dict[str, Any], new: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Devuelve solo los campos que cambiaron (antes, después)."""
    keys = [k for k in new if old.get(k) != new.get(k)]
    return {k: old.get(k) for k in keys}, {k: new.get(k) for k in keys}
