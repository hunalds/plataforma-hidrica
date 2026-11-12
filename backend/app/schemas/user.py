"""Esquemas Pydantic de autenticación y usuarios (M1, M2)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.user import Role


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    role: Role
    is_active: bool
    must_change_password: bool
    reservoir_codes: list[str]
    last_login_at: datetime | None
    created_at: datetime


class MeOut(UserOut):
    permissions: dict[str, str]  # {"M3_embalses": "MANAGE", ...}


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)

    @field_validator("email")
    @classmethod
    def _lower(cls, v: str) -> str:
        return v.lower()


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"  # noqa: S105 — tipo de token OAuth2, no es una contraseña
    expires_in: int
    user: MeOut


class RefreshIn(BaseModel):
    refresh_token: str


class ChangePasswordIn(BaseModel):
    current_password: str = Field(max_length=256)
    new_password: str = Field(max_length=256)


class ForgotPasswordIn(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def _lower(cls, v: str) -> str:
        return v.lower()


class ResetPasswordIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    new_password: str = Field(max_length=256)


class MessageOut(BaseModel):
    message: str


# --- Gestión de usuarios (Gerencia) ---


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=3, max_length=120)
    role: Role
    reservoir_codes: list[str] = []

    @field_validator("email")
    @classmethod
    def _lower(cls, v: str) -> str:
        return v.lower()


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=3, max_length=120)
    role: Role | None = None
    is_active: bool | None = None
    reservoir_codes: list[str] | None = None


class UserCreatedOut(BaseModel):
    user: UserOut
    temporary_password: str  # se muestra una sola vez; el usuario debe cambiarla al entrar


class UserListOut(BaseModel):
    items: list[UserOut]
    total: int
