"""Gestión de usuarios (M2) — solo Gerencia."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import func, or_, select

from app.api.deps import DbSession, api_error, client_ip, require
from app.core.permissions import Access, Module
from app.core.security import generate_temporary_password, hash_password
from app.models.reservoir import Reservoir
from app.models.user import Role, User
from app.schemas.user import UserCreate, UserCreatedOut, UserListOut, UserOut, UserUpdate
from app.services.audit import diff, log_action
from app.services.sessions import revoke_all_sessions

router = APIRouter(prefix="/users", tags=["usuarios"])

Manager = Annotated[User, Depends(require(Module.USERS, Access.MANAGE))]


def _audit_view(user: User) -> dict:
    return {
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value,
        "is_active": user.is_active,
        "reservoir_codes": user.reservoir_codes,
    }


def _load_reservoirs(session, codes: list[str]) -> list[Reservoir]:
    unique = sorted(set(codes))
    found = session.scalars(select(Reservoir).where(Reservoir.code.in_(unique))).all()
    missing = set(unique) - {r.code for r in found}
    if missing:
        raise api_error(422, "UNKNOWN_RESERVOIR", f"Embalses inexistentes: {', '.join(sorted(missing))}")
    return list(found)


def _get_user(session, user_id: int) -> User:
    user = session.get(User, user_id)
    if user is None:
        raise api_error(404, "NOT_FOUND", "Usuario no encontrado.")
    return user


@router.get("", response_model=UserListOut, summary="Listar usuarios")
def list_users(
    session: DbSession,
    _: Manager,
    search: str | None = Query(default=None, max_length=100, description="Busca en nombre o correo"),
    role: Role | None = None,
    active: bool | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> UserListOut:
    stmt = select(User)
    if search:
        like = f"%{search.lower()}%"
        stmt = stmt.where(or_(func.lower(User.full_name).like(like), User.email.like(like)))
    if role:
        stmt = stmt.where(User.role == role)
    if active is not None:
        stmt = stmt.where(User.is_active == active)
    total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    users = session.scalars(stmt.order_by(User.full_name).limit(limit).offset(offset)).all()
    return UserListOut(items=[UserOut.model_validate(u) for u in users], total=total)


@router.post("", response_model=UserCreatedOut, status_code=status.HTTP_201_CREATED, summary="Crear usuario")
def create_user(body: UserCreate, request: Request, session: DbSession, actor: Manager) -> UserCreatedOut:
    if session.scalar(select(User).where(User.email == body.email)):
        raise api_error(409, "EMAIL_EXISTS", "Ya existe un usuario con ese correo.")
    temporary = generate_temporary_password()
    user = User(
        email=body.email,
        full_name=body.full_name.strip(),
        role=body.role,
        password_hash=hash_password(temporary),
        must_change_password=True,
        is_active=True,
    )
    user.reservoirs = _load_reservoirs(session, body.reservoir_codes)
    session.add(user)
    session.flush()
    log_action(
        session,
        "user.create",
        actor=actor,
        entity="user",
        entity_id=user.id,
        new=_audit_view(user),
        ip=client_ip(request),
    )
    session.commit()
    return UserCreatedOut(user=UserOut.model_validate(user), temporary_password=temporary)


@router.get("/{user_id}", response_model=UserOut, summary="Ver usuario")
def get_user(user_id: int, session: DbSession, _: Manager) -> UserOut:
    return UserOut.model_validate(_get_user(session, user_id))


@router.patch(
    "/{user_id}", response_model=UserOut, summary="Editar usuario, rol, estado o embalses asignados"
)
def update_user(
    user_id: int, body: UserUpdate, request: Request, session: DbSession, actor: Manager
) -> UserOut:
    user = _get_user(session, user_id)
    if user.id == actor.id and (
        (body.role is not None and body.role != actor.role) or body.is_active is False
    ):
        raise api_error(409, "SELF_LOCKOUT", "No puedes cambiar tu propio rol ni desactivarte.")

    before = _audit_view(user)
    if body.full_name is not None:
        user.full_name = body.full_name.strip()
    if body.role is not None:
        user.role = body.role
    if body.reservoir_codes is not None:
        user.reservoirs = _load_reservoirs(session, body.reservoir_codes)
    if body.is_active is not None and body.is_active != user.is_active:
        user.is_active = body.is_active
        if not body.is_active:  # cierra sus sesiones de inmediato
            user.token_version += 1
            revoke_all_sessions(session, user.id)
    if body.role is not None and body.role.value != before["role"]:
        user.token_version += 1  # los permisos viajan en el token: se fuerza uno nuevo

    old, new = diff(before, _audit_view(user))
    if new:
        log_action(
            session,
            "user.update",
            actor=actor,
            entity="user",
            entity_id=user.id,
            old=old,
            new=new,
            ip=client_ip(request),
        )
    session.commit()
    return UserOut.model_validate(user)


@router.post(
    "/{user_id}/reset-password",
    response_model=UserCreatedOut,
    summary="Generar una contraseña temporal (desbloquea la cuenta y cierra sus sesiones)",
)
def admin_reset_password(
    user_id: int, request: Request, session: DbSession, actor: Manager
) -> UserCreatedOut:
    user = _get_user(session, user_id)
    temporary = generate_temporary_password()
    user.password_hash = hash_password(temporary)
    user.must_change_password = True
    user.failed_attempts = 0
    user.locked_until = None
    user.token_version += 1
    revoke_all_sessions(session, user.id)
    log_action(
        session, "user.reset_password", actor=actor, entity="user", entity_id=user.id, ip=client_ip(request)
    )
    session.commit()
    return UserCreatedOut(user=UserOut.model_validate(user), temporary_password=temporary)
