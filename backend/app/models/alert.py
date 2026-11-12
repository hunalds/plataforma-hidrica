"""Alertas tempranas (M9): alertas, acuses de recibo, envíos por canal y destinatarios."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

SEVERITIES = ("informativa", "alerta", "critica")


class Alert(Base):
    """Una alerta por evento. Mientras el evento siga activo se ACTUALIZA (no se duplica); al
    desaparecer la condición se marca resuelta (resolved_at)."""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    reservoir_code: Mapped[str] = mapped_column(ForeignKey("reservoirs.code", ondelete="CASCADE"), index=True)
    dedup_key: Mapped[str] = mapped_column(String(120), index=True)  # embalse:tipo:umbral
    kind: Mapped[str] = mapped_column(String(20))  # observada | proyectada
    direction: Mapped[str] = mapped_column(String(30))  # escasez | inundacion_alivio
    severity: Mapped[str] = mapped_column(String(20))  # informativa | alerta | critica
    threshold: Mapped[str] = mapped_column(String(40))
    threshold_level: Mapped[float] = mapped_column(Float)
    title: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text)
    value: Mapped[float | None] = mapped_column(Float)  # cota observada o probabilidad proyectada
    horizon_days: Mapped[int | None] = mapped_column(Integer)
    probability: Mapped[float | None] = mapped_column(Float)
    event_day: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    acknowledgements: Mapped[list[AlertAck]] = relationship(lazy="selectin", cascade="all, delete-orphan")
    deliveries: Mapped[list[AlertDelivery]] = relationship(lazy="selectin", cascade="all, delete-orphan")


class AlertAck(Base):
    """Acuse de recibo: quién vio la alerta y cuándo."""

    __tablename__ = "alert_acks"
    __table_args__ = (UniqueConstraint("alert_id", "user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    alert_id: Mapped[int] = mapped_column(ForeignKey("alerts.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    user_email: Mapped[str] = mapped_column(String(254))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AlertDelivery(Base):
    """Intento de envío por un canal (plataforma, correo, telegram, sms, whatsapp)."""

    __tablename__ = "alert_deliveries"

    id: Mapped[int] = mapped_column(primary_key=True)
    alert_id: Mapped[int] = mapped_column(ForeignKey("alerts.id", ondelete="CASCADE"), index=True)
    channel: Mapped[str] = mapped_column(String(20))
    recipient: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20))  # enviada | error | omitida
    detail: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(20))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AlertRecipient(Base):
    """Destinatario configurable por embalse (o todos) y severidad mínima."""

    __tablename__ = "alert_recipients"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))  # p. ej. "Director Estadal"
    channel: Mapped[str] = mapped_column(String(20))  # correo | telegram | sms | whatsapp
    target: Mapped[str] = mapped_column(String(200))  # correo, chat_id o teléfono
    reservoir_code: Mapped[str | None] = mapped_column(
        ForeignKey("reservoirs.code", ondelete="CASCADE")
    )  # None = todos
    min_severity: Mapped[str] = mapped_column(String(20), default="alerta")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
