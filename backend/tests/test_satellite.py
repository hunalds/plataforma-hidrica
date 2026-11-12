"""Iteración 3 (M5): cálculos satelitales, geometrías, ingesta, tareas y API.

Las pruebas con red real se activan con RUN_NETWORK_TESTS=1 (no corren por defecto).
"""

from __future__ import annotations

import json
import os
from datetime import date, timedelta

import httpx
import numpy as np
import pytest
from shapely.geometry import box, shape

from app.models.satellite import Job, JobStatus, SatelliteObservation
from app.models.user import Role
from app.services import geo
from app.services.satellite import compute, registry
from app.services.satellite import ingest as sat_ingest
from app.services.satellite.base import AreaOfInterest, Quality, Variable
from app.services.satellite.base import SatelliteObservation as Obs
from app.services.satellite.mock import MockProvider
from app.services.satellite.openmeteo import OpenMeteoSoilProvider, sample_points
from app.services.satellite.water import landsat_reflectance, landsat_valid, s2_reflectance

network = pytest.mark.skipif(
    os.environ.get("RUN_NETWORK_TESTS") != "1", reason="requiere red (RUN_NETWORK_TESTS=1)"
)
ALL = ["MANUELOTE", "TRES_RIOS", "TULE"]


# ---------------------------------------------------------------- cálculos puros


def test_grid_mask_uses_cell_centers_and_falls_back_for_tiny_polygons():
    lats = np.array([10.0, 10.1, 10.2])
    lons = np.array([-72.2, -72.1, -72.0])
    big = box(-72.15, 10.05, -71.95, 10.25)
    m = compute.grid_mask(lats, lons, big, 0.1)
    assert m.tolist() == [[False, False, False], [False, True, True], [False, True, True]]
    tiny = box(-72.11, 10.09, -72.105, 10.095)  # más chico que una celda: sin centros dentro
    assert compute.grid_mask(lats, lons, tiny, 0.1).sum() >= 1


def test_areal_mean_ignores_nan():
    values = np.array([[[1.0, np.nan], [3.0, 5.0]], [[np.nan, np.nan], [np.nan, np.nan]]])
    mask = np.array([[True, True], [True, False]])
    out = compute.areal_mean(values, mask)
    assert out[0] == pytest.approx(2.0) and np.isnan(out[1])


def test_ndwi_water_positive_land_negative():
    assert compute.ndwi(np.array([0.10]), np.array([0.02]))[0] > 0  # agua: refleja más verde que NIR
    assert compute.ndwi(np.array([0.05]), np.array([0.30]))[0] < 0  # vegetación
    assert np.isnan(compute.ndwi(np.array([0.0]), np.array([0.0]))[0])


def test_water_stats_extrapolates_under_clouds():
    index = np.array([[0.5, 0.5, -0.3, -0.3]])
    valid = np.array([[True, False, True, True]])  # una nube sobre agua
    aoi = np.ones_like(valid)
    s = compute.water_stats(index, valid, aoi, aoi_area_km2=40.0)
    assert s["cloud_pct"] == pytest.approx(25.0)
    assert s["water_area_km2"] == pytest.approx(40.0 / 3, abs=1e-3)  # 1 de 3 válidos es agua
    assert compute.water_stats(index, np.zeros_like(valid), aoi, 40.0)["water_area_km2"] is None


@pytest.mark.parametrize(("cloud", "q"), [(0, "buena"), (20, "buena"), (35, "dudosa"), (61, "sin_dato")])
def test_quality_by_cloud(cloud, q):
    assert compute.quality_for_cloud(cloud) == q


def test_landsat_qa_and_scaling():
    qa = np.array([21824, 21826, 22280, 1])  # despejado, nube dilatada, nube, relleno
    assert landsat_valid(qa).tolist() == [True, False, False, False]
    refl = landsat_reflectance(np.array([0, 10000]))
    assert np.isnan(refl[0]) and refl[1] == pytest.approx(0.075)


def test_sentinel2_offset_after_baseline_04():
    dn = np.array([2000])
    assert s2_reflectance(dn, date(2021, 6, 1))[0] == pytest.approx(0.2)
    assert s2_reflectance(dn, date(2023, 6, 1))[0] == pytest.approx(0.1)


def test_sample_points_inside_polygon_and_capped():
    poly = box(-72.5, 10.5, -71.5, 11.5)
    pts = sample_points(poly)
    assert 0 < len(pts) <= 30
    assert all(poly.contains(shape({"type": "Point", "coordinates": [lo, la]})) for la, lo in pts)
    assert len(sample_points(box(-72.101, 10.901, -72.1, 10.902))) == 1  # cae al punto representativo


# ---------------------------------------------------------------- geometrías


def test_osm_snapshot_has_three_plausible_reservoirs():
    snap = geo.load_snapshot()
    assert set(snap) == set(ALL)
    areas = {c: geo.area_km2(shape(f["geometry"])) for c, f in snap.items()}
    assert 25 < areas["TULE"] < 40 and 10 < areas["MANUELOTE"] < 25 and 3 < areas["TRES_RIOS"] < 10
    assert all("OpenStreetMap" in f["properties"]["source"] for f in snap.values())


def test_buffer_km_grows_area_as_expected():
    square = box(-72.1, 10.9, -72.09, 10.91)  # ~1,1 km de lado
    grown = geo.buffer_km(square, 1.0)
    a0, a1 = geo.area_km2(square), geo.area_km2(grown)
    # área + perímetro·r + π·r²
    expected = a0 + 4 * 1.09 * 1.0 + np.pi
    assert a1 == pytest.approx(expected, rel=0.05)


def test_apply_osm_geometries_respects_user_uploads(client, db, auth_headers, reservoirs):
    report = geo.apply_osm_geometries(db)
    db.commit()
    assert len(report) == 3
    ing = auth_headers(Role.INGENIERO, reservoirs=ALL)
    card = client.get("/reservoirs/TULE", headers=ing).json()
    assert card["has_geometry"] and card["has_basin_geometry"]

    # Un polígono cargado por el usuario no se pisa en la siguiente ejecución
    official = {
        "type": "Polygon",
        "coordinates": [[[-72.2, 10.8], [-72.0, 10.8], [-72.0, 11.0], [-72.2, 11.0], [-72.2, 10.8]]],
    }
    client.put("/reservoirs/TULE/geometry", headers=ing, json={"kind": "reservoir", "geojson": official})
    report = geo.apply_osm_geometries(db)
    assert any("se conserva" in line for line in report if line.startswith("TULE"))


# ---------------------------------------------------------------- ingesta con proveedores simulados


class FakeWater(MockProvider):
    name = "fake_water"

    def fetch_both(self, aoi, start, end):
        return [o for v in (Variable.NDWI, Variable.WATER_AREA) for o in self.fetch(aoi, v, start, end)]


@pytest.fixture
def mocked_providers(monkeypatch):
    def fake(name):
        return FakeWater() if name == "planetary_computer" else MockProvider()

    monkeypatch.setattr(registry, "get_provider", fake)


@pytest.fixture
def geometries(db, reservoirs):
    geo.apply_osm_geometries(db)
    db.commit()


def test_ingest_saves_and_is_idempotent(db, geometries, mocked_providers):
    calls = []
    r1 = sat_ingest.run(
        db, "precipitacion", ALL, date(2025, 1, 1), date(2025, 1, 31), lambda f, m: calls.append(f)
    )
    assert r1["guardadas"] == 3 * 31
    assert calls and calls[-1] == pytest.approx(1.0)
    sat_ingest.run(db, "precipitacion", ALL, date(2025, 1, 1), date(2025, 1, 31))
    assert db.query(SatelliteObservation).count() == 93  # sin duplicados


def test_ingest_water_saves_both_variables_with_reservoir_scope(db, geometries, mocked_providers):
    sat_ingest.run(db, "agua", ["TULE"], date(2025, 3, 1), date(2025, 3, 10))
    rows = db.query(SatelliteObservation).all()
    assert {r.variable for r in rows} == {"ndwi_medio", "superficie_agua_km2"}
    assert {r.scope.value for r in rows} == {"EMBALSE"}


def test_ingest_requires_geometry(db, reservoirs, mocked_providers):
    with pytest.raises(sat_ingest.MissingGeometryError, match="cuenca o área de influencia"):
        sat_ingest.run(db, "precipitacion", ["TULE"], date(2025, 1, 1), date(2025, 1, 2))


def test_openmeteo_parses_multi_point_daily_response_and_retries_429():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, headers={"Retry-After": "1"})
        assert request.url.params["models"] == "era5_land"
        assert request.url.params["daily"] == "soil_moisture_0_to_7cm_mean"

        def loc(v):
            return {"daily": {"time": ["2025-01-01", "2025-01-02"], "soil_moisture_0_to_7cm_mean": [v, None]}}

        return httpx.Response(200, json=[loc(0.30), loc(0.20)])

    provider = OpenMeteoSoilProvider(client=httpx.Client(transport=httpx.MockTransport(handler)))
    waits = []
    provider.sleep = waits.append
    aoi = AreaOfInterest("TULE", json.loads(json.dumps(box(-72.3, 10.8, -72.1, 11.0).__geo_interface__)))
    obs = provider.fetch(aoi, Variable.SOIL_MOISTURE, date(2025, 1, 1), date(2025, 1, 2))
    assert waits == [1.0]
    assert obs[0].value == pytest.approx(0.25) and obs[0].quality == Quality.GOOD
    assert obs[1].value is None and obs[1].quality == Quality.MISSING


# ---------------------------------------------------------------- API y tareas


def test_engineer_launches_job_and_it_completes(client, db, auth_headers, geometries, mocked_providers):
    ing = auth_headers(Role.INGENIERO, reservoirs=ALL)
    r = client.post(
        "/satellite/jobs",
        headers=ing,
        json={"kind": "humedad_suelo", "date_from": "2025-02-01", "date_to": "2025-02-10"},
    )
    assert r.status_code == 202, r.text
    job = client.get(f"/satellite/jobs/{r.json()['id']}", headers=ing).json()  # BackgroundTasks ya corrió
    assert job["status"] == "TERMINADA" and job["progress"] == 1.0
    assert job["result"]["guardadas"] == 30
    cov = client.get("/satellite/coverage", headers=ing).json()
    assert {(c["reservoir_code"], c["variable"]) for c in cov} == {(c, "humedad_suelo_m3m3") for c in ALL}


def test_job_failure_is_recorded(client, auth_headers, geometries, monkeypatch):
    class Broken(MockProvider):
        def _fetch(self, *a, **k):
            raise RuntimeError("servidor caído")

    monkeypatch.setattr(registry, "get_provider", lambda name: Broken())
    ing = auth_headers(Role.INGENIERO, reservoirs=ALL)
    r = client.post(
        "/satellite/jobs",
        headers=ing,
        json={"kind": "humedad_suelo", "date_from": "2025-02-01", "date_to": "2025-02-02"},
    )
    job = client.get(f"/satellite/jobs/{r.json()['id']}", headers=ing).json()
    assert job["status"] == "FALLIDA" and "servidor caído" in job["message"]


def test_job_validation_and_conflicts(client, db, auth_headers, geometries, mocked_providers):
    ing = auth_headers(Role.INGENIERO, reservoirs=ALL)
    future = (date.today() + timedelta(days=3)).isoformat()
    assert (
        client.post(
            "/satellite/jobs",
            headers=ing,
            json={"kind": "agua", "date_from": "2025-01-01", "date_to": future},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/satellite/jobs",
            headers=ing,
            json={"kind": "nieve", "date_from": "2025-01-01", "date_to": "2025-01-02"},
        ).status_code
        == 422
    )
    db.add(Job(kind="satelite.agua", params={}, status=JobStatus.RUNNING, progress=0.2))
    db.commit()
    r = client.post(
        "/satellite/jobs",
        headers=ing,
        json={"kind": "agua", "date_from": "2025-01-01", "date_to": "2025-01-02"},
    )
    assert r.status_code == 409


def test_job_requires_geometries(client, auth_headers, reservoirs):
    ing = auth_headers(Role.INGENIERO, reservoirs=ALL)
    r = client.post(
        "/satellite/jobs",
        headers=ing,
        json={"kind": "agua", "date_from": "2025-01-01", "date_to": "2025-01-02"},
    )
    assert r.status_code == 422 and r.json()["detail"]["code"] == "MISSING_GEOMETRY"


def test_permissions_follow_matrix(client, auth_headers, geometries, mocked_providers):
    ger = auth_headers(Role.GERENCIA)
    op = auth_headers(Role.OPERADOR, reservoirs=["TULE"])
    body = {"kind": "precipitacion", "date_from": "2025-01-01", "date_to": "2025-01-02"}
    assert client.post("/satellite/jobs", headers=ger, json=body).status_code == 403  # Gerencia consulta
    assert client.get("/satellite/jobs", headers=ger).status_code == 200
    assert client.get("/satellite/sources", headers=op).status_code == 403  # Operador sin M5
    # …pero el panel (M7) sí le muestra los indicadores de su embalse
    assert client.get("/reservoirs/TULE/satellite/summary", headers=op).status_code == 200
    assert client.get("/reservoirs/MANUELOTE/satellite/summary", headers=op).status_code == 404


def test_summary_and_series(client, db, auth_headers, geometries, mocked_providers):
    sat_ingest.run(db, "precipitacion", ["TULE"], date(2024, 1, 1), date(2025, 3, 31))
    sat_ingest.run(db, "humedad_suelo", ["TULE"], date(2025, 3, 1), date(2025, 3, 31))
    sat_ingest.run(db, "agua", ["TULE"], date(2025, 3, 1), date(2025, 3, 31))
    h = auth_headers(Role.GERENCIA)
    s = client.get("/reservoirs/TULE/satellite/summary", headers=h).json()
    assert s["precipitation_last_day"] == "2025-03-31"
    assert s["precipitation_30d_mm"] >= s["precipitation_7d_mm"] >= 0
    assert s["precipitation_30d_normal_mm"] is not None  # hay un año previo (2024)
    assert s["soil_moisture"] is not None and s["water_area_km2"] is not None
    assert 25 < s["water_area_reference_km2"] < 40
    assert "PROVISIONAL" in s["geometry_source"] and "influencia" in s["basin_source"]

    series = client.get(
        "/reservoirs/TULE/satellite/series?variable=superficie_agua_km2&date_from=2025-03-01&date_to=2025-03-31&only_good=true",
        headers=h,
    ).json()
    assert series and all(p["quality"] == "buena" for p in series)


# ---------------------------------------------------------------- red real (opcional)


@network
def test_live_chirps_and_openmeteo_on_tule():
    snap = geo.load_snapshot()
    basin = AreaOfInterest("TULE", geo.buffer_km(shape(snap["TULE"]["geometry"]), 20).__geo_interface__)
    rain = registry.get_provider("chirps").fetch(
        basin, Variable.PRECIPITATION, date(2026, 9, 1), date(2026, 9, 3)
    )
    assert len(rain) == 3 and all(o.value is not None and o.value >= 0 for o in rain)
    soil = registry.get_provider("era5_land_openmeteo").fetch(
        basin, Variable.SOIL_MOISTURE, date(2026, 9, 1), date(2026, 9, 2)
    )
    assert all(0.05 < o.value < 0.6 for o in soil)


def test_observation_unit():
    assert Obs(date(2025, 1, 1), "X", Variable.PRECIPITATION, 1.0, "s").unit == "mm/día"
