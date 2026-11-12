"""Comandos de administración (app/cli.py) sobre la base de pruebas."""

from __future__ import annotations

from sqlalchemy import func, select

from app.cli import main
from app.models.reservoir import ElevationCurve, Reservoir
from app.models.user import User


def test_seed_is_idempotent(db, app):
    assert main(["seed"]) == 0
    assert main(["seed"]) == 0
    assert db.scalar(select(func.count()).select_from(Reservoir)) == 3


def test_demo_users_and_create_user(db, app, capsys):
    assert main(["demo-users"]) == 0
    out = capsys.readouterr().out
    assert "gerencia@" in out and "operador@" in out
    users = db.scalars(select(User)).all()
    assert len(users) == 3 and all(u.must_change_password for u in users)

    assert main(["create-user", "--email", "Nuevo@Hidrica-Zulia.com", "--name", "Nuevo", "--role", "INGENIERO"]) == 0
    assert main(["create-user", "--email", "nuevo@hidrica-zulia.com", "--name", "Otro", "--role", "OPERADOR"]) == 1


def test_load_synthetic_curves(db, app, capsys):
    assert main(["load-synthetic-curves"]) == 0
    curves = db.scalars(select(ElevationCurve)).all()
    assert {c.reservoir_code for c in curves} == {"TULE", "MANUELOTE", "TRES_RIOS"}
    assert all("SINTÉTICA" in (c.notes or "") for c in curves)
    # una segunda ejecución no duplica
    assert main(["load-synthetic-curves"]) == 0
    assert db.scalar(select(func.count()).select_from(ElevationCurve)) == 3
