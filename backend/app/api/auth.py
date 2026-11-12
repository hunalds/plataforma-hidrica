"""Autenticación (M1): login, renovación, cierre de sesión, cambio y recuperación de contraseña."""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import (
    AppSettings,
    DbSession,
    api_error,
    client_ip,
    get_current_user_allow_password_change,
)
from app.core.config import Settings
from app.core.permissions import permissions_for
from app.core.security import (
    TokenError,
    burn_verification_time,
    create_token_pair,
    decode_token,
    hash_password,
    hash_reset_token,
    new_reset_token,
    password_policy_errors,
    utcnow,
    verify_password,
)
from app.models.user import PasswordResetToken, RefreshToken, User
from app.schemas.user import (
    ChangePasswordIn,
    ForgotPasswordIn,
    LoginIn,
    MeOut,
    MessageOut,
    RefreshIn,
    ResetPasswordIn,
    TokenOut,
    UserOut,
)
from app.services.audit import log_action
from app.services.email import EmailMessage
from app.services.sessions import revoke_all_sessions

router = APIRouter(prefix="/auth", tags=["autenticación"])

INVALID_CREDENTIALS = "Correo o contraseña incorrectos."


def me_out(user: User) -> MeOut:
    return MeOut(**UserOut.model_validate(user).model_dump(), permissions=permissions_for(user.role))


def _issue_tokens(session: Session, user: User, settings: Settings, ip: str | None) -> TokenOut:
    pair = create_token_pair(user.id, user.role.value, user.token_version, settings)
    session.add(
        RefreshToken(
            id=pair.refresh_jti,
            user_id=user.id,
            expires_at=pair.refresh_expires_at,
            last_used_at=utcnow(),
            ip=ip,
        )
    )
    return TokenOut(
        access_token=pair.access_token,
        refresh_token=pair.refresh_token,
        expires_in=pair.access_expires_in,
        user=me_out(user),
    )


def _check_policy(password: str, email: str) -> None:
    errors = password_policy_errors(password, email)
    if errors:
        raise api_error(422, "WEAK_PASSWORD", " ".join(errors))


@router.post("/login", response_model=TokenOut, summary="Iniciar sesión")
def login(body: LoginIn, request: Request, session: DbSession, settings: AppSettings) -> TokenOut:
    ip = client_ip(request)
    limiter = request.app.state.login_limiter
    if not limiter.hit(f"login:{ip}"):
        wait = limiter.retry_after(f"login:{ip}")
        raise api_error(
            429,
            "TOO_MANY_REQUESTS",
            f"Demasiados intentos desde tu conexión. Espera {wait} segundos.",
            {"Retry-After": str(wait)},
        )

    user = session.scalar(select(User).where(User.email == body.email))
    now = utcnow()
    if user is None:
        burn_verification_time(body.password)
        log_action(
            session, "login.fail", actor_email=body.email, entity="user", ip=ip, new={"motivo": "no_existe"}
        )
        session.commit()
        raise api_error(401, "INVALID_CREDENTIALS", INVALID_CREDENTIALS)

    if user.locked_until and user.locked_until > now:
        minutes = max(1, int((user.locked_until - now).total_seconds() // 60) + 1)
        log_action(session, "login.locked", actor=user, entity="user", entity_id=user.id, ip=ip)
        session.commit()
        raise api_error(
            423, "ACCOUNT_LOCKED", f"Cuenta bloqueada temporalmente. Intenta de nuevo en {minutes} minutos."
        )

    if not verify_password(body.password, user.password_hash):
        user.failed_attempts += 1
        if user.failed_attempts >= settings.login_max_attempts:
            user.locked_until = now + timedelta(minutes=settings.login_lockout_minutes)
            user.failed_attempts = 0
            log_action(session, "login.lockout", actor=user, entity="user", entity_id=user.id, ip=ip)
            session.commit()
            raise api_error(
                423,
                "ACCOUNT_LOCKED",
                f"Superaste {settings.login_max_attempts} intentos fallidos. "
                f"Cuenta bloqueada por {settings.login_lockout_minutes} minutos.",
            )
        log_action(session, "login.fail", actor=user, entity="user", entity_id=user.id, ip=ip)
        session.commit()
        raise api_error(401, "INVALID_CREDENTIALS", INVALID_CREDENTIALS)

    if not user.is_active:
        log_action(session, "login.inactive", actor=user, entity="user", entity_id=user.id, ip=ip)
        session.commit()
        raise api_error(403, "USER_INACTIVE", "Tu usuario está desactivado. Contacta a Gerencia.")

    user.failed_attempts = 0
    user.locked_until = None
    user.last_login_at = now
    out = _issue_tokens(session, user, settings, ip)
    log_action(session, "login.ok", actor=user, entity="user", entity_id=user.id, ip=ip)
    session.commit()
    return out


@router.post("/refresh", response_model=TokenOut, summary="Renovar la sesión")
def refresh(body: RefreshIn, request: Request, session: DbSession, settings: AppSettings) -> TokenOut:
    expired = api_error(401, "SESSION_EXPIRED", "Tu sesión expiró. Inicia sesión nuevamente.")
    try:
        claims = decode_token(body.refresh_token, "refresh", settings)
        jti = uuid.UUID(claims["jti"])
    except (TokenError, KeyError, ValueError):
        raise expired from None

    record = session.get(RefreshToken, jti)
    user = session.get(User, int(claims["sub"]))
    if record is None or user is None or record.user_id != user.id:
        raise expired
    now = utcnow()
    if record.revoked_at is not None:
        # Reuso de un token ya rotado: posible robo. Se cierran todas las sesiones del usuario.
        revoke_all_sessions(session, user.id)
        log_action(
            session,
            "session.reuse_detected",
            actor=user,
            entity="user",
            entity_id=user.id,
            ip=client_ip(request),
        )
        session.commit()
        raise expired
    if now - record.last_used_at > timedelta(minutes=settings.session_idle_minutes):
        record.revoked_at = now
        session.commit()
        raise api_error(401, "SESSION_IDLE", "Tu sesión se cerró por inactividad. Inicia sesión nuevamente.")
    if not user.is_active or user.token_version != claims["ver"]:
        record.revoked_at = now
        session.commit()
        raise expired

    record.revoked_at = now  # rotación
    out = _issue_tokens(session, user, settings, client_ip(request))
    session.commit()
    return out


@router.post("/logout", response_model=MessageOut, summary="Cerrar sesión")
def logout(body: RefreshIn, request: Request, session: DbSession, settings: AppSettings) -> MessageOut:
    try:
        claims = decode_token(body.refresh_token, "refresh", settings)
        record = session.get(RefreshToken, uuid.UUID(claims["jti"]))
    except (TokenError, KeyError, ValueError):
        record = None
    if record is not None and record.revoked_at is None:
        record.revoked_at = utcnow()
        user = session.get(User, record.user_id)
        log_action(
            session, "logout", actor=user, entity="user", entity_id=record.user_id, ip=client_ip(request)
        )
        session.commit()
    return MessageOut(message="Sesión cerrada.")


@router.get("/me", response_model=MeOut, summary="Usuario actual y sus permisos")
def me(user: Annotated[User, Depends(get_current_user_allow_password_change)]) -> MeOut:
    return me_out(user)


@router.post("/change-password", response_model=TokenOut, summary="Cambiar mi contraseña")
def change_password(
    body: ChangePasswordIn,
    request: Request,
    session: DbSession,
    settings: AppSettings,
    user: Annotated[User, Depends(get_current_user_allow_password_change)],
) -> TokenOut:
    if not verify_password(body.current_password, user.password_hash):
        raise api_error(400, "WRONG_PASSWORD", "La contraseña actual no es correcta.")
    if body.new_password == body.current_password:
        raise api_error(422, "SAME_PASSWORD", "La nueva contraseña debe ser distinta de la actual.")
    _check_policy(body.new_password, user.email)

    user.password_hash = hash_password(body.new_password)
    user.must_change_password = False
    user.password_changed_at = utcnow()
    user.token_version += 1  # invalida tokens anteriores
    revoke_all_sessions(session, user.id)
    out = _issue_tokens(session, user, settings, client_ip(request))
    log_action(
        session, "password.change", actor=user, entity="user", entity_id=user.id, ip=client_ip(request)
    )
    session.commit()
    return out


@router.post(
    "/forgot-password",
    response_model=MessageOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Solicitar recuperación de contraseña",
)
def forgot_password(
    body: ForgotPasswordIn, request: Request, session: DbSession, settings: AppSettings
) -> MessageOut:
    generic = MessageOut(
        message="Si el correo está registrado, recibirás un enlace para restablecer tu contraseña."
    )
    ip = client_ip(request)
    if not request.app.state.login_limiter.hit(f"forgot:{ip}"):
        return generic  # no se revela el límite para no dar pistas; simplemente no se envía

    user = session.scalar(select(User).where(User.email == body.email))
    if user is None or not user.is_active:
        return generic

    raw, token_hash = new_reset_token()
    session.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=utcnow() + timedelta(minutes=settings.password_reset_minutes),
        )
    )
    log_action(session, "password.reset_requested", actor=user, entity="user", entity_id=user.id, ip=ip)
    session.commit()

    link = f"{settings.frontend_url.rstrip('/')}/restablecer?token={raw}"
    request.app.state.email_sender.send(
        EmailMessage(
            to=user.email,
            subject="Plataforma Hídrica Zulia · Restablecer contraseña",
            body=(
                f"Hola {user.full_name},\n\n"
                f"Recibimos una solicitud para restablecer tu contraseña. Usa este enlace "
                f"(vence en {settings.password_reset_minutes} minutos y sirve una sola vez):\n\n{link}\n\n"
                "Si no lo solicitaste, ignora este correo."
            ),
        )
    )
    return generic


@router.post("/reset-password", response_model=MessageOut, summary="Restablecer la contraseña con el enlace")
def reset_password(body: ResetPasswordIn, request: Request, session: DbSession) -> MessageOut:
    invalid = api_error(400, "INVALID_RESET_TOKEN", "El enlace no es válido o ya expiró. Solicita uno nuevo.")
    record = session.scalar(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_reset_token(body.token))
    )
    now = utcnow()
    if record is None or record.used_at is not None or record.expires_at < now:
        raise invalid
    user = session.get(User, record.user_id)
    if user is None or not user.is_active:
        raise invalid
    _check_policy(body.new_password, user.email)

    user.password_hash = hash_password(body.new_password)
    user.must_change_password = False
    user.password_changed_at = now
    user.failed_attempts = 0
    user.locked_until = None
    user.token_version += 1
    record.used_at = now
    revoke_all_sessions(session, user.id)
    log_action(session, "password.reset", actor=user, entity="user", entity_id=user.id, ip=client_ip(request))
    session.commit()
    return MessageOut(message="Tu contraseña fue restablecida. Ya puedes iniciar sesión.")
