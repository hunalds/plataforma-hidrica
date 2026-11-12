"""Verifica la conexión a PostgreSQL/PostGIS con las credenciales del .env.

Uso (desde la raíz del proyecto):
    uv run --project backend python scripts/check_db.py
Sale con código 0 si las dos bases responden y tienen PostGIS.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.split(" #", 1)[0].strip().strip('"').strip("'")
        values[key.strip()] = value
    return values


def check(dbname: str, env: dict[str, str]) -> bool:
    try:
        with psycopg.connect(
            host=env.get("DB_HOST", "localhost"),
            port=int(env.get("DB_PORT", "5432")),
            dbname=dbname,
            user=env.get("DB_USER", "hidrica_app"),
            password=env.get("DB_PASSWORD", ""),
            connect_timeout=5,
        ) as conn:
            pg = conn.execute("SHOW server_version").fetchone()[0]
            gis = conn.execute("SELECT postgis_lib_version()").fetchone()[0]
        print(f"OK  {dbname}: PostgreSQL {pg}, PostGIS {gis}")
        return True
    except Exception as exc:  # noqa: BLE001 — se reporta cualquier fallo de conexión
        print(f"ERR {dbname}: {exc}".strip())
        return False


def main() -> int:
    # La consola de Windows usa cp1252; los mensajes de PostgreSQL pueden traer caracteres inválidos
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    env = {**load_env(ROOT / ".env"), **{k: v for k, v in os.environ.items() if k.startswith("DB_")}}
    dbs = [env.get("DB_NAME", "plataforma_hidrica"), env.get("DB_NAME_TEST", "plataforma_hidrica_test")]
    results = [check(db, env) for db in dbs]
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
