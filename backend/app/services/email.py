"""Envío de correo (recuperación de contraseña; luego alertas M9).

- SmtpEmailSender: si SMTP_HOST está configurado.
- ConsoleEmailSender: en desarrollo escribe el correo en el log (no envía nada).
- MemoryEmailSender: para pruebas automatizadas.
"""

from __future__ import annotations

import smtplib
from dataclasses import dataclass
from email.message import EmailMessage as MimeMessage
from typing import Protocol

from app.core.config import Settings
from app.core.logging import get_logger

log = get_logger(__name__)


@dataclass(frozen=True)
class EmailMessage:
    to: str
    subject: str
    body: str


class EmailSender(Protocol):
    def send(self, message: EmailMessage) -> None: ...


class ConsoleEmailSender:
    def send(self, message: EmailMessage) -> None:
        log.warning("email_console", to=message.to, subject=message.subject, body=message.body)


class MemoryEmailSender:
    def __init__(self) -> None:
        self.outbox: list[EmailMessage] = []

    def send(self, message: EmailMessage) -> None:
        self.outbox.append(message)


class SmtpEmailSender:
    def __init__(self, settings: Settings) -> None:
        self.s = settings

    def send(self, message: EmailMessage) -> None:
        mime = MimeMessage()
        mime["From"] = self.s.smtp_from or self.s.smtp_user
        mime["To"] = message.to
        mime["Subject"] = message.subject
        mime.set_content(message.body)
        with smtplib.SMTP(self.s.smtp_host, self.s.smtp_port, timeout=15) as smtp:
            smtp.starttls()
            if self.s.smtp_user:
                smtp.login(self.s.smtp_user, self.s.smtp_password.get_secret_value())
            smtp.send_message(mime)


def build_email_sender(settings: Settings) -> EmailSender:
    if settings.app_env == "test":
        return MemoryEmailSender()
    if settings.smtp_host:
        return SmtpEmailSender(settings)
    return ConsoleEmailSender()
