"""Prueba de rendimiento del panel principal (requisito no funcional: < 3 s con datos de un año).

Mide, sobre la base de desarrollo, el tiempo de respuesta de cada endpoint que carga el panel y la
ficha de un embalse (con la autenticación sustituida por un usuario de Gerencia en memoria).
Uso (desde la raíz):  uv run --project backend python scripts/perf/dashboard_perf.py [--runs 5]
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

from app.api import deps
from app.core.config import get_settings
from app.main import create_app
from app.models.user import Role, User

PANEL = ["/reservoirs", "/reservoirs/status", "/map/features", "/dashboard/comparison?days=365", "/alerts?active=true&limit=8"]
FICHA = [
    "/reservoirs/TULE",
    "/reservoirs/TULE/status",
    "/reservoirs/TULE/forecast",
    "/reservoirs/TULE/history?days=365",
    "/reservoirs/TULE/satellite/summary",
    "/reservoirs/TULE/measurements?limit=30",
    "/reservoirs/TULE/balance",
]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()

    app = create_app(get_settings())
    fake = User(id=0, email="perf@local", full_name="Prueba de rendimiento", role=Role.GERENCIA, is_active=True, must_change_password=False, token_version=0, password_hash="-")
    fake.reservoirs = []
    app.dependency_overrides[deps._authenticate] = lambda: fake

    results = {}
    with TestClient(app) as c:
        for group, paths in (("Panel principal", PANEL), ("Ficha de embalse", FICHA)):
            total_med = 0.0
            for p in paths:
                c.get(p)  # calentamiento (carga de modelos, cachés)
                times = []
                for _ in range(args.runs):
                    t0 = time.perf_counter()
                    r = c.get(p)
                    times.append((time.perf_counter() - t0) * 1000)
                med = statistics.median(times)
                total_med += med
                results[p] = {"status": r.status_code, "mediana_ms": round(med, 1), "max_ms": round(max(times), 1)}
                print(f"  {r.status_code}  {med:8.1f} ms (máx {max(times):7.1f})  {p}")
            # El navegador pide estos endpoints en paralelo; la suma es la cota superior (todo en serie)
            ok = "OK" if total_med < 3000 else "SUPERA 3 s"
            print(f"{group}: {total_med:.0f} ms sumando todas las peticiones en serie → {ok}\n")
            results[group] = {"suma_mediana_ms": round(total_med, 1), "cumple_3s": total_med < 3000}
    if args.json:
        args.json.write_text(json.dumps({"fecha": datetime.now().isoformat(timespec="seconds"), **results}, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if all(v.get("cumple_3s", True) for v in results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
