"""Dependencias comunes: sesión de base de datos, usuario autenticado y permisos por rol."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.permissions import Access, Module, can
from app.core.security import TokenError, decode_token
from app.db import get_session
from app.models.user import User

bearer = HTTPBearer(auto_error=False, description="Token de acceso (JWT)")

DbSession = Annotated[Session, Depends(get_session)]


def api_error(
    status_code: int, code: str, message: str, headers: dict[str, str] | None = None
) -> HTTPException:
    """Error con cuerpo uniforme: {"detail": {"code": ..., "message": ...}} (mensajes en español)."""
    return HTTPException(status_code=status_code, detail={"code": code, "message": message}, headers=headers)


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


AppSettings = Annotated[Settings, Depends(get_settings_dep)]


def client_ip(request: Request) -> str | None:
    # Detrás de un proxy inverso (Iteración 7) se configurará uvicorn --proxy-headers
    return request.client.host if request.client else None


def _authenticate(
    session: DbSession,
    settings: AppSettings,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User:
    unauthorized = api_error(
        status.HTTP_401_UNAUTHORIZED,
        "NOT_AUTHENTICATED",
        "Tu sesión no es válida o expiró. Inicia sesión nuevamente.",
        {"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    try:
        claims = decode_token(credentials.credentials, "access", settings)
    except TokenError:
        raise unauthorized from None
    user = session.get(User, int(claims["sub"]))
    if user is None or not user.is_active or user.token_version != claims["ver"]:
        raise unauthorized
    return user


def get_current_user_allow_password_change(user: Annotated[User, Depends(_authenticate)]) -> User:
    """Usuario autenticado, aunque deba cambiar su contraseña (para /auth/me y /auth/change-password)."""
    return user


def get_current_user(user: Annotated[User, Depends(_authenticate)]) -> User:
    if user.must_change_password:
        raise api_error(
            status.HTTP_403_FORBIDDEN,
            "PASSWORD_CHANGE_REQUIRED",
            "Debes cambiar tu contraseña antes de continuar.",
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require(module: Module, needed: Access = Access.READ) -> Callable[..., User]:
    """Dependencia que exige el nivel de acceso de la matriz de permisos para el módulo."""

    def checker(user: CurrentUser) -> User:
        if not can(user.role, module, needed):
            raise api_error(
                status.HTTP_403_FORBIDDEN,
                "FORBIDDEN",
                "Tu rol no tiene permiso para realizar esta acción.",
            )
        return user

    return checker
