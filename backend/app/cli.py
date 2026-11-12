"""Comandos de administración (desde backend/):

    uv run python -m app.cli seed                       # crea los 3 embalses (si faltan)
    uv run python -m app.cli create-user --email ... --name ... --role GERENCIA
    uv run python -m app.cli demo-users                 # usuarios de prueba, uno por rol (solo desarrollo)
    uv run python -m app.cli load-synthetic-curves      # curvas SINTÉTICAS (solo desarrollo)

Las contraseñas generadas son temporales: se muestran una sola vez y deben cambiarse al entrar.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from sqlalchemy import func, select

from app.core.config import ROOT_DIR, get_settings
from app.core.security import generate_temporary_password, hash_password
from app.db import build_engine
from app.models.reservoir import ElevationCurve, ElevationCurvePoint, Reservoir
from app.models.user import Role, User
from app.seed import seed_reservoirs
from app.services.audit import log_action
from app.services.curves import parse_curve_file

SYNTHETIC_DIR = ROOT_DIR / "ml" / "data" / "synthetic"
DEMO_DOMAIN = "hidrica-zulia.com"  # dominio ficticio; .local/.test los rechaza el validador de correos


def _session():
    from sqlalchemy.orm import sessionmaker

    return sessionmaker(build_engine(get_settings()), expire_on_commit=False)()


def _create_user(session, email: str, name: str, role: Role, reservoirs: list[str]) -> str | None:
    if session.scalar(select(User).where(User.email == email.lower())):
        return None
    temporary = generate_temporary_password()
    user = User(
        email=email.lower(),
        full_name=name,
        role=role,
        password_hash=hash_password(temporary),
        must_change_password=True,
    )
    user.reservoirs = [session.get(Reservoir, c) for c in reservoirs if session.get(Reservoir, c)]
    session.add(user)
    session.flush()
    log_action(
        session,
        "user.create",
        actor_email="cli",
        entity="user",
        entity_id=user.id,
        new={"email": user.email, "role": role.value},
    )
    return temporary


def cmd_seed(_: argparse.Namespace) -> int:
    with _session() as s:
        created = seed_reservoirs(s)
        s.commit()
    print("Embalses creados:", ", ".join(created) if created else "ninguno (ya existían)")
    return 0


def cmd_create_user(args: argparse.Namespace) -> int:
    with _session() as s:
        seed_reservoirs(s)
        temporary = _create_user(s, args.email, args.name, Role(args.role), args.reservoirs or [])
        s.commit()
    if temporary is None:
        print(f"Ya existe un usuario con el correo {args.email}.", file=sys.stderr)
        return 1
    print(
        f"Usuario creado: {args.email} ({args.role})\nContraseña temporal (cámbiala al entrar): {temporary}"
    )
    return 0


def cmd_demo_users(_: argparse.Namespace) -> int:
    if get_settings().app_env == "production":
        print("No se crean usuarios de demostración en producción.", file=sys.stderr)
        return 1
    demo = [
        (f"gerencia@{DEMO_DOMAIN}", "Gerencia (demo)", Role.GERENCIA, []),
        (f"ingeniero@{DEMO_DOMAIN}", "Ingeniero (demo)", Role.INGENIERO, ["TULE", "MANUELOTE", "TRES_RIOS"]),
        (f"operador@{DEMO_DOMAIN}", "Operador (demo)", Role.OPERADOR, ["TULE"]),
    ]
    with _session() as s:
        seed_reservoirs(s)
        rows = [
            (email, role.value, _create_user(s, email, name, role, res)) for email, name, role, res in demo
        ]
        s.commit()
    print("Usuarios de demostración (contraseñas temporales, se piden cambiar al entrar):")
    for email, role, temporary in rows:
        print(f"  {role:<10} {email:<45} {temporary or '(ya existía)'}")
    return 0


def cmd_load_synthetic_curves(args: argparse.Namespace) -> int:
    if get_settings().app_env == "production":
        print("Las curvas sintéticas no se cargan en producción.", file=sys.stderr)
        return 1
    folder = Path(args.folder)
    with _session() as s:
        seed_reservoirs(s)
        for r in s.scalars(select(Reservoir)).all():
            path = folder / f"curva_cota_volumen_{r.code.lower()}_sintetica.csv"
            if not path.exists():
                print(f"  {r.code}: no se encontró {path.name}")
                continue
            if s.scalar(select(func.count()).where(ElevationCurve.reservoir_code == r.code)):
                print(f"  {r.code}: ya tiene curvas, se omite")
                continue
            # El CSV sintético trae una columna 'embalse' extra: el lector solo toma cota, área y volumen
            points = parse_curve_file(path.read_bytes(), path.name)
            s.add(
                ElevationCurve(
                    reservoir_code=r.code,
                    version=1,
                    valid_from=date(2005, 1, 1),
                    source_filename=path.name,
                    notes="CURVA SINTÉTICA para desarrollo. Reemplazar por la curva oficial (P-03).",
                    points=[
                        ElevationCurvePoint(
                            elevation=p.elevation, area_km2=p.area_km2, volume_hm3=p.volume_hm3
                        )
                        for p in points
                    ],
                )
            )
            print(f"  {r.code}: {len(points)} puntos cargados (SINTÉTICA)")
        s.commit()
    return 0


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(
        prog="python -m app.cli", description="Administración de la Plataforma Hídrica"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("seed", help="Crear los tres embalses").set_defaults(func=cmd_seed)

    p = sub.add_parser("create-user", help="Crear un usuario con contraseña temporal")
    p.add_argument("--email", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--role", required=True, choices=[r.value for r in Role])
    p.add_argument("--reservoirs", nargs="*", help="Códigos de embalses asignados (TULE MANUELOTE TRES_RIOS)")
    p.set_defaults(func=cmd_create_user)

    sub.add_parser("demo-users", help="Usuarios de demostración (uno por rol)").set_defaults(
        func=cmd_demo_users
    )

    p = sub.add_parser("load-synthetic-curves", help="Cargar curvas SINTÉTICAS (solo desarrollo)")
    p.add_argument("--folder", default=str(SYNTHETIC_DIR))
    p.set_defaults(func=cmd_load_synthetic_curves)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
