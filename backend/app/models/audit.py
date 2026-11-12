"""Bitácora de auditoría (M1).

Registra quién, qué acción, sobre qué entidad, valores antes/después, cuándo y desde qué IP.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    user_email: Mapped[str | None] = mapped_column(String(254))  # se conserva aunque el usuario se elimine
    action: Mapped[str] = mapped_column(String(60), index=True)  # p. ej. "login.ok", "user.update"
    entity: Mapped[str | None] = mapped_column(String(60))  # p. ej. "user", "reservoir", "threshold"
    entity_id: Mapped[str | None] = mapped_column(String(60))
    old_value: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    new_value: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    ip: Mapped[str | None] = mapped_column(String(45))
