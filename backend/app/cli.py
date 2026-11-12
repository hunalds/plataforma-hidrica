"""Comandos de administración (desde backend/):

    uv run python -m app.cli seed                       # crea los 3 embalses (si faltan)
    uv run python -m app.cli create-user --email ... --name ... --role GERENCIA
    uv run python -m app.cli demo-users                 # usuarios de prueba, uno por rol (solo desarrollo)
    uv run python -m app.cli load-synthetic-curves      # curvas SINTÉTICAS (solo desarrollo)
    uv run python -m app.cli load-synthetic-measurements  # histórico SINTÉTICO hasta 2026-10-15
    uv run python -m app.cli load-geometries            # polígonos OSM + área de influencia provisional
    uv run python -m app.cli load-synthetic-satellite   # lluvia y humedad SINTÉTICAS coherentes (para ML)
    uv run python -m app.cli train-models               # backtesting + entrenamiento (puede tardar)
    uv run python -m app.cli satellite --kind precipitacion --from 2005-01-01 --to 2026-11-10

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


def _create_user(
    session, email: str, name: str, role: Role, reservoirs: list[str], password: str | None = None
) -> str | None:
    if session.scalar(select(User).where(User.email == email.lower())):
        return None
    temporary = password or generate_temporary_password()
    user = User(
        email=email.lower(),
        full_name=name,
        role=role,
        password_hash=hash_password(temporary),
        must_change_password=password is None,  # con --password (pruebas E2E) no se fuerza el cambio
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
    if args.password and get_settings().app_env == "production":
        print("--password no se permite en producción.", file=sys.stderr)
        return 1
    with _session() as s:
        seed_reservoirs(s)
        temporary = _create_user(
            s, args.email, args.name, Role(args.role), args.reservoirs or [], args.password
        )
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


def cmd_load_synthetic_measurements(args: argparse.Namespace) -> int:
    """Importa el histórico sintético usando el MISMO flujo de validación que la importación web."""
    if get_settings().app_env == "production":
        print("Los datos sintéticos no se cargan en producción.", file=sys.stderr)
        return 1
    from app.models.measurement import MeasurementSource
    from app.services.ingest import parse_measurement_file, save_rows, validate

    path = Path(args.file)
    if not path.exists():
        print(
            f"No se encontró {path}. Genera el dataset con: cd ml; uv run python -m hidrica_ml.synthetic",
            file=sys.stderr,
        )
        return 1
    until = date.fromisoformat(args.until)
    raw, parse_issues = parse_measurement_file(path.read_bytes(), path.name)
    raw = [r for r in raw if r.day <= until]
    with _session() as s:
        seed_reservoirs(s)
        s.commit()
        result = validate(s, raw, allowed_codes=None)
        saved = save_rows(
            s, result.rows, overwrite=args.overwrite, source=MeasurementSource.IMPORT, user_id=None
        )
        log_action(
            s,
            "ingest.synthetic",
            actor_email="cli",
            entity="daily_measurements",
            new={
                "archivo": path.name,
                "hasta": until.isoformat(),
                "insertadas": saved.inserted,
                "actualizadas": saved.updated,
            },
        )
        s.commit()
    errors = [i for i in parse_issues + result.issues if i.severity == "error"]
    warnings = len(result.issues) - len([i for i in result.issues if i.severity == "error"])
    print(
        f"Filas leídas: {len(raw)} (hasta {until}) · insertadas: {saved.inserted} "
        f"· actualizadas: {saved.updated} "
        f"· omitidas: {saved.skipped} · errores: {len(errors)} · avisos: {warnings}"
    )
    for i in errors[:10]:
        print(f"  ERROR fila {i.row}: {i.message}")
    return 0 if not errors else 2


def cmd_load_geometries(args: argparse.Namespace) -> int:
    from app.services.geo import apply_osm_geometries

    with _session() as s:
        seed_reservoirs(s)
        report = apply_osm_geometries(s, influence_km=args.influence_km, force=args.force)
        log_action(
            s,
            "reservoir.geometry",
            actor_email="cli",
            entity="reservoir",
            new={"fuente": "OSM", "area_influencia_km": args.influence_km},
        )
        s.commit()
    print("\n".join(report))
    return 0


def cmd_satellite(args: argparse.Namespace) -> int:
    """Descarga satelital desde la terminal (útil para el histórico, que tarda)."""
    from app.services.satellite import ingest as sat_ingest

    start, end = date.fromisoformat(args.date_from), date.fromisoformat(args.date_to)

    def progress(fraction: float, message: str) -> None:
        print(f"  [{fraction:6.1%}] {message}", flush=True)

    with _session() as s:
        codes = args.reservoirs or [c for (c,) in s.execute(select(Reservoir.code).order_by(Reservoir.code))]
        try:
            result = sat_ingest.run(s, args.kind, codes, start, end, progress)
        except sat_ingest.MissingGeometryError as exc:
            print(str(exc), "Ejecuta primero: python -m app.cli load-geometries", file=sys.stderr)
            return 1
        log_action(s, "satellite.cli", actor_email="cli", entity="satellite", new=result)
        s.commit()
    print(f"Listo: {result['guardadas']} observaciones guardadas ({result['con_valor']} con valor).")
    return 0


def cmd_load_synthetic_satellite(args: argparse.Namespace) -> int:
    """Carga lluvia y humedad del suelo SINTÉTICAS (fuente "sintetico") para entrenar con datos coherentes."""
    import csv as _csv

    from app.models.satellite import Scope
    from app.services.satellite import ingest as sat_ingest
    from app.services.satellite.base import Quality, SatelliteObservation, Variable

    if get_settings().app_env == "production":
        print("Los datos sintéticos no se cargan en producción.", file=sys.stderr)
        return 1
    path = Path(args.file)
    if not path.exists():
        print(
            f"No se encontró {path}. Genéralo con: cd ml; uv run python -m hidrica_ml.synthetic_satellite",
            file=sys.stderr,
        )
        return 1
    obs = []
    with path.open(encoding="utf-8") as fh:
        for row in _csv.DictReader(fh):
            d = date.fromisoformat(row["fecha"])
            for var, col in (
                (Variable.PRECIPITATION, "precipitacion_mm"),
                (Variable.SOIL_MOISTURE, "humedad_suelo_m3m3"),
            ):
                obs.append(
                    SatelliteObservation(
                        day=d,
                        area_code=row["embalse"],
                        variable=var,
                        value=float(row[col]),
                        source="sintetico",
                        quality=Quality.GOOD,
                        meta={"SINTETICO": True},
                    )
                )
    with _session() as s:
        seed_reservoirs(s)
        n = sat_ingest.save(s, obs, Scope.BASIN)
        log_action(
            s,
            "satellite.synthetic",
            actor_email="cli",
            entity="satellite",
            new={"archivo": path.name, "observaciones": n},
        )
        s.commit()
    print(f"Observaciones SINTÉTICAS guardadas: {n}")
    return 0


def cmd_train_models(args: argparse.Namespace) -> int:
    from app.services import ml_service

    settings = get_settings()

    def progress(fraction: float, message: str) -> None:
        print(f"  [{fraction:6.1%}] {message}", flush=True)

    with _session() as s:
        codes = args.reservoirs or [c for (c,) in s.execute(select(Reservoir.code).order_by(Reservoir.code))]
        try:
            summary = ml_service.train_and_register(
                s, settings, codes, tuple(args.kinds), args.test_years, None, progress, fast=args.fast
            )
        except ml_service.MLDataError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        log_action(s, "ml.train", actor_email="cli", entity="ml_model", new={"resumen": summary})
        s.commit()
    for code, info in summary.items():
        print(f"{code}: modelo activo = {info['modelo_activo']} (MAE medio {info['mae_medio_hm3']} hm³)")
    if args.report:
        from app.services.ml_report import write_report

        with _session() as s:
            print("Informe:", write_report(s, settings))
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
    p.add_argument("--password", help="Contraseña fija sin cambio obligatorio (solo desarrollo/pruebas E2E)")
    p.set_defaults(func=cmd_create_user)

    sub.add_parser("demo-users", help="Usuarios de demostración (uno por rol)").set_defaults(
        func=cmd_demo_users
    )

    p = sub.add_parser("load-synthetic-curves", help="Cargar curvas SINTÉTICAS (solo desarrollo)")
    p.add_argument("--folder", default=str(SYNTHETIC_DIR))
    p.set_defaults(func=cmd_load_synthetic_curves)

    p = sub.add_parser("load-synthetic-measurements", help="Cargar el histórico SINTÉTICO (solo desarrollo)")
    p.add_argument("--file", default=str(SYNTHETIC_DIR / "movimiento_diario_sintetico.csv"))
    p.add_argument(
        "--until", default="2026-10-15", help="Fecha final (los ejemplos de importación cubren lo posterior)"
    )
    p.add_argument("--overwrite", action="store_true", help="Reemplazar días que ya existan")
    p.set_defaults(func=cmd_load_synthetic_measurements)

    p = sub.add_parser("load-geometries", help="Cargar polígonos OSM y áreas de influencia provisionales")
    p.add_argument("--influence-km", type=float, default=20.0)
    p.add_argument("--force", action="store_true", help="Reemplazar también polígonos cargados por usuarios")
    p.set_defaults(func=cmd_load_geometries)

    p = sub.add_parser("satellite", help="Descargar datos satelitales")
    p.add_argument("--kind", required=True, choices=["precipitacion", "humedad_suelo", "agua"])
    p.add_argument("--from", dest="date_from", required=True)
    p.add_argument("--to", dest="date_to", required=True)
    p.add_argument("--reservoirs", nargs="*")
    p.set_defaults(func=cmd_satellite)

    p = sub.add_parser(
        "load-synthetic-satellite", help="Cargar lluvia y humedad SINTÉTICAS (solo desarrollo)"
    )
    p.add_argument("--file", default=str(SYNTHETIC_DIR / "satelite_sintetico.csv"))
    p.set_defaults(func=cmd_load_synthetic_satellite)

    p = sub.add_parser("train-models", help="Backtesting y entrenamiento de los modelos de predicción")
    p.add_argument("--reservoirs", nargs="*")
    p.add_argument("--kinds", nargs="*", default=["persistencia", "estacional", "xgboost", "lstm"])
    p.add_argument("--test-years", nargs="*", type=int)
    p.add_argument("--fast", action="store_true", help="LSTM con pocas épocas (pruebas)")
    p.add_argument("--report", action="store_true", help="Generar ml/reports/backtesting.md al terminar")
    p.set_defaults(func=cmd_train_models)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
