"""Canales de notificación de alertas (M9) detrás de una interfaz común.

- plataforma: la alerta queda visible en la aplicación (siempre).
- correo: SMTP (o el registro en desarrollo).
- telegram: Bot API (requiere TELEGRAM_BOT_TOKEN; el destinatario es el chat_id).
- sms / whatsapp: interfaz lista para conectar un proveedor (P-17); hoy se registran como "omitida".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import httpx

from app.core.config import Settings
from app.models.alert import Alert
from app.services.email import EmailMessage, EmailSender

SEVERITY_LABEL = {"informativa": "INFORMATIVA", "alerta": "ALERTA", "critica": "CRÍTICA"}


@dataclass(frozen=True)
class DeliveryResult:
    status: str  # enviada | error | omitida
    detail: str | None = None


class NotificationChannel(Protocol):
    name: str

    def send(self, alert: Alert, reservoir_name: str, target: str) -> DeliveryResult: ...


def render_text(alert: Alert, reservoir_name: str, frontend_url: str) -> str:
    return (
        f"[{SEVERITY_LABEL.get(alert.severity, alert.severity)}] Embalse {reservoir_name}\n"
        f"{alert.title}\n\n{alert.message}\n\n"
        f"Ver en la plataforma: {frontend_url.rstrip('/')}/embalses/{alert.reservoir_code}"
    )


class EmailChannel:
    name = "correo"

    def __init__(self, sender: EmailSender, settings: Settings) -> None:
        self.sender, self.settings = sender, settings

    def send(self, alert, reservoir_name, target):
        try:
            self.sender.send(
                EmailMessage(
                    to=target,
                    subject=f"[{SEVERITY_LABEL.get(alert.severity)}] {reservoir_name}: {alert.title}",
                    body=render_text(alert, reservoir_name, self.settings.frontend_url),
                )
            )
            return DeliveryResult("enviada")
        except Exception as exc:  # noqa: BLE001 — un canal caído no detiene a los demás
            return DeliveryResult("error", f"{type(exc).__name__}: {exc}"[:300])


class TelegramChannel:
    name = "telegram"

    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        self.settings = settings
        self.client = client or httpx.Client(timeout=15)

    def send(self, alert, reservoir_name, target):
        token = self.settings.telegram_bot_token.get_secret_value()
        if not token:
            return DeliveryResult("omitida", "TELEGRAM_BOT_TOKEN no configurado")
        try:
            r = self.client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={
                    "chat_id": target,
                    "text": render_text(alert, reservoir_name, self.settings.frontend_url),
                },
            )
            if r.status_code == 200 and r.json().get("ok"):
                return DeliveryResult("enviada")
            return DeliveryResult("error", f"Telegram respondió {r.status_code}")
        except httpx.HTTPError as exc:
            return DeliveryResult("error", type(exc).__name__)


class PendingProviderChannel:
    """SMS y WhatsApp: se conectan cuando MINAGUAS defina el proveedor (P-17)."""

    def __init__(self, name: str) -> None:
        self.name = name

    def send(self, alert, reservoir_name, target):
        return DeliveryResult("omitida", f"Canal {self.name} sin proveedor configurado (P-17)")


def build_channels(settings: Settings, email_sender: EmailSender) -> dict[str, NotificationChannel]:
    return {
        "correo": EmailChannel(email_sender, settings),
        "telegram": TelegramChannel(settings),
        "sms": PendingProviderChannel("sms"),
        "whatsapp": PendingProviderChannel("whatsapp"),
    }
