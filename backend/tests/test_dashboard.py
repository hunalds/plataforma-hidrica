"""Iteración 5 (M7 panel, M8 mapa): historia con rango histórico, comparativo y capas del mapa."""

from __future__ import annotations

import pytest

from app.cli import main as cli
from app.models.user import Role
from app.services import geo

ALL = ["MANUELOTE", "TRES_RIOS", "TULE"]


@pytest.fixture
def data(app, db, reservoirs):
    assert cli(["load-synthetic-curves"]) == 0
    assert cli(["load-synthetic-measurements", "--until", "2026-10-15"]) == 0
    assert cli(["load-synthetic-satellite"]) == 0
    geo.apply_osm_geometries(db)
    db.commit()


def test_history_has_climatology_band(client, auth_headers, data):
    h = auth_headers(Role.OPERADOR, reservoirs=["TULE"])
    r = client.get("/reservoirs/TULE/history?days=365", headers=h).json()
    assert len(r["points"]) == 365 and r["points"][-1]["day"] == "2026-10-15"
    p = r["points"][100]
    assert p["hist_min"] <= p["hist_mean"] <= p["hist_max"]
    assert r["years"].startswith("2005")


def test_comparison_respects_visibility(client, auth_headers, data):
    op = auth_headers(Role.OPERADOR, reservoirs=["TULE"])
    assert [s["reservoir_code"] for s in client.get("/dashboard/comparison?days=60", headers=op).json()] == [
        "TULE"
    ]
    ger = auth_headers(Role.GERENCIA, email="jefe@hidrica-zulia.com")
    comp = client.get("/dashboard/comparison?days=60", headers=ger).json()
    assert len(comp) == 3 and all(len(c["availability"]) == 60 for c in comp)
    assert all(0 <= v <= 150 for c in comp for _, v in c["availability"])


def test_map_features_with_status_and_indicators(client, auth_headers, data):
    ger = auth_headers(Role.GERENCIA)
    m = client.get("/map/features?source=sintetico", headers=ger).json()
    res = {f["properties"]["code"]: f for f in m["reservoirs"]["features"]}
    assert set(res) == set(ALL)
    tule = res["TULE"]["properties"]
    assert tule["light"] in {"verde", "amarillo", "rojo"} and tule["availability_pct"] is not None
    assert tule["precip_30d_mm"] is not None and tule["soil_moisture"] is not None
    assert res["TULE"]["geometry"]["type"] in {"Polygon", "MultiPolygon"}
    assert len(m["basins"]["features"]) == 3 and "OpenStreetMap" in m["attribution"]


def test_map_without_geometries_is_empty_but_ok(client, auth_headers, reservoirs):
    r = client.get("/map/features", headers=auth_headers(Role.OPERADOR, reservoirs=["TULE"]))
    assert r.status_code == 200 and r.json()["reservoirs"]["features"] == []
