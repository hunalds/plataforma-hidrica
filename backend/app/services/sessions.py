"""Gestión de sesiones (refresh tokens) compartida por los routers de autenticación y usuarios."""

from __future__ import annotations

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.security import utcnow
from app.models.user import RefreshToken


def revoke_all_sessions(session: Session, user_id: int) -> None:
    """Revoca todas las sesiones activas del usuario (cambio de contraseña, desactivación, robo de token)."""
    session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )
