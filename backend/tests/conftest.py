"""Fixtures comunes. Las pruebas usan siempre la base plataforma_hidrica_test.

- Al inicio de la sesión se aplican las migraciones (alembic upgrade head).
- Después de cada prueba se vacían todas las tablas de la aplicación.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

os.environ["APP_ENV"] = "test"

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402

from app.core.config import Settings  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import Base  # noqa: E402
from app.models.reservoir import Reservoir  # noqa: E402
from app.models.user import Role, User  # noqa: E402
from app.seed import seed_reservoirs  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parents[1]
PASSWORD = "Clave-Segura-2026"


@pytest.fixture(scope="session", autouse=True)
def _migrate_test_db() -> None:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(cfg, "head")


@pytest.fixture
def settings() -> Settings:
    return Settings(app_env="test")


@pytest.fixture
def app(settings: Settings):
    application = create_app(settings)
    yield application
    tables = ", ".join(f'"{t.name}"' for t in reversed(Base.metadata.sorted_tables))
    with application.state.engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    application.state.engine.dispose()


@pytest.fixture
def client(app) -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db(app) -> Iterator[Session]:
    with app.state.session_factory() as session:
        yield session


@pytest.fixture
def reservoirs(db: Session) -> list[str]:
    seed_reservoirs(db)
    db.commit()
    return ["MANUELOTE", "TRES_RIOS", "TULE"]


@pytest.fixture
def make_user(db: Session) -> Callable[..., User]:
    def _make(
        role: Role = Role.GERENCIA,
        email: str | None = None,
        password: str = PASSWORD,
        must_change_password: bool = False,
        is_active: bool = True,
        reservoirs: list[str] | None = None,
    ) -> User:
        user = User(
            email=email or f"{role.value.lower()}@hidrica-zulia.com",
            full_name=f"Usuario {role.value.title()}",
            role=role,
            password_hash=hash_password(password),
            must_change_password=must_change_password,
            is_active=is_active,
        )
        if reservoirs:
            user.reservoirs = [db.get(Reservoir, code) for code in reservoirs]
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    return _make


@pytest.fixture
def login(client: TestClient) -> Callable[..., dict]:
    def _login(email: str, password: str = PASSWORD) -> dict:
        r = client.post("/auth/login", json={"email": email, "password": password})
        assert r.status_code == 200, r.text
        return r.json()

    return _login


@pytest.fixture
def auth_headers(make_user, login) -> Callable[..., dict[str, str]]:
    """Crea un usuario del rol indicado, inicia sesión y devuelve el encabezado Authorization."""

    def _headers(role: Role = Role.GERENCIA, **kwargs) -> dict[str, str]:
        user = make_user(role=role, **kwargs)
        tokens = login(user.email)
        return {"Authorization": f"Bearer {tokens['access_token']}"}

    return _headers
