"""Contraseñas (Argon2id), tokens JWT y tokens de recuperación (M1)."""

from __future__ import annotations

import hashlib
import re
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import Settings

_hasher = PasswordHasher()  # Argon2id con parámetros recomendados por la librería

PASSWORD_MIN_LENGTH = 10


def utcnow() -> datetime:
    return datetime.now(UTC)


# --- Contraseñas -------------------------------------------------------------


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


# Hash fijo para gastar el mismo tiempo cuando el usuario no existe (evita enumerar correos por tiempo)
_DUMMY_HASH = _hasher.hash("contrasena-ficticia-para-igualar-tiempos")


def burn_verification_time(password: str) -> None:
    verify_password(password, _DUMMY_HASH)


def password_policy_errors(password: str, email: str | None = None) -> list[str]:
    """Política mínima: longitud, letras y números, y distinta del correo. Mensajes en español."""
    errors: list[str] = []
    if len(password) < PASSWORD_MIN_LENGTH:
        errors.append(f"Debe tener al menos {PASSWORD_MIN_LENGTH} caracteres.")
    if not re.search(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]", password):
        errors.append("Debe incluir al menos una letra.")
    if not re.search(r"\d", password):
        errors.append("Debe incluir al menos un número.")
    if email and password.strip().lower() in {email.lower(), email.split("@")[0].lower()}:
        errors.append("No puede ser igual a tu correo.")
    return errors


def generate_temporary_password() -> str:
    """Contraseña temporal legible (se cambia en el primer acceso)."""
    alphabet = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ"
    letters = "".join(secrets.choice(alphabet) for _ in range(8))
    digits = "".join(secrets.choice("23456789") for _ in range(4))
    return f"{letters}-{digits}"


# --- JWT -------------------------------------------------------------------------

TokenType = Literal["access", "refresh"]


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    access_expires_in: int  # segundos
    refresh_jti: uuid.UUID
    refresh_expires_at: datetime


class TokenError(Exception):
    pass


def _encode(claims: dict[str, Any], settings: Settings) -> str:
    return jwt.encode(claims, settings.jwt_secret.get_secret_value(), algorithm=settings.jwt_algorithm)


def create_token_pair(user_id: int, role: str, token_version: int, settings: Settings) -> TokenPair:
    now = utcnow()
    access_exp = now + timedelta(minutes=settings.jwt_access_minutes)
    refresh_exp = now + timedelta(days=settings.jwt_refresh_days)
    jti = uuid.uuid4()
    base = {"sub": str(user_id), "ver": token_version, "iat": now}
    access = _encode({**base, "type": "access", "role": role, "exp": access_exp}, settings)
    refresh = _encode({**base, "type": "refresh", "jti": str(jti), "exp": refresh_exp}, settings)
    return TokenPair(access, refresh, settings.jwt_access_minutes * 60, jti, refresh_exp)


def decode_token(token: str, expected: TokenType, settings: Settings) -> dict[str, Any]:
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "sub", "type", "ver"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("expired") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenError("invalid") from exc
    if claims.get("type") != expected:
        raise TokenError("wrong_type")
    return claims


# --- Recuperación de contraseña ------------------------------------------------


def new_reset_token() -> tuple[str, str]:
    """Devuelve (valor para el enlace, hash SHA-256 para guardar)."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_reset_token(raw)


def hash_reset_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()
