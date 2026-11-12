"""Iteración 4 (M6): entrenamiento y registro de modelos, selección, fijado manual y proyección."""

from __future__ import annotations

import pytest

from app.cli import main as cli
from app.models.ml import MLModel
from app.models.user import Role
from app.services import ml_service

ALL = ["MANUELOTE", "TRES_RIOS", "TULE"]


@pytest.fixture
def ml_data(app, reservoirs, tmp_path, settings, monkeypatch):
    """Curvas + histórico + satélite sintéticos en la base de pruebas; artefactos en carpeta temporal."""
    assert cli(["load-synthetic-curves"]) == 0
    assert cli(["load-synthetic-measurements", "--until", "2026-10-15"]) == 0
    assert cli(["load-synthetic-satellite"]) == 0
    monkeypatch.setattr(app.state.settings, "ml_models_dir", tmp_path / "models")
    monkeypatch.setattr(app.state.settings, "ml_reports_dir", tmp_path / "reports")
    return app.state.settings


def test_build_series_from_database(db, ml_data):
    s = ml_service.build_series(db, "TULE", ml_data)
    assert s.df["volume_hm3"].notna().sum() > 7000
    assert s.df["precip_mm"].notna().sum() > 7000 and s.df["soil_moisture"].notna().sum() > 7000
    assert "sintetico" in s.meta["fuente"]


def test_train_select_pin_and_forecast(client, db, auth_headers, ml_data):
    summary = ml_service.train_and_register(
        db, ml_data, ["TULE"], ("persistencia", "estacional", "xgboost"), [2025], None, fast=True
    )
    assert summary["TULE"]["modelo_activo"] in {"estacional", "xgboost"}

    ing = auth_headers(Role.INGENIERO, reservoirs=ALL)
    models = client.get("/ml/models?reservoir=TULE", headers=ing).json()
    assert {m["kind"] for m in models} == {"persistencia", "estacional", "xgboost"}
    active = [m for m in models if m["active"]]
    assert len(active) == 1 and active[0]["score"] == min(m["score"] for m in models)
    assert all(len(m["metrics"]) == 3 for m in models)

    # Proyección interpretable
    f = client.get("/reservoirs/TULE/forecast", headers=ing).json()
    assert f["origin"] == "2026-10-15" and len(f["days"]) == 90
    assert [h["horizon_days"] for h in f["horizons"]] == [30, 60, 90]
    assert f["model"]["kind"] == active[0]["kind"]
    assert any(p["threshold"] == "dead_level" for p in f["probabilities"])

    # El Ingeniero fija la persistencia: pasa a ser la activa aunque tenga más error
    persist = next(m for m in models if m["kind"] == "persistencia")
    assert client.post(f"/ml/models/{persist['id']}/pin", headers=ing).json()["active"] is True
    assert client.get("/reservoirs/TULE/forecast", headers=ing).json()["model"]["kind"] == "persistencia"
    client.post(f"/ml/models/{persist['id']}/unpin", headers=ing)
    assert client.get("/reservoirs/TULE/forecast", headers=ing).json()["model"]["kind"] == active[0]["kind"]

    # Informe de backtesting
    from app.services.ml_report import write_report

    report = write_report(db, ml_data)
    text = report.read_text(encoding="utf-8")
    assert "Tulé" in text and "SINTÉTICOS" in text and (report.parent / "backtest_tule.png").exists()


def test_permissions_and_errors(client, auth_headers, ml_data):
    op = auth_headers(Role.OPERADOR, reservoirs=["TULE"])
    ger = auth_headers(Role.GERENCIA)
    assert client.get("/ml/models", headers=op).status_code == 403
    assert client.post("/ml/train", headers=ger, json={}).status_code == 403
    r = client.get(
        "/reservoirs/TULE/forecast", headers=op
    )  # el panel sí es para todos, pero aún no hay modelo
    assert r.status_code == 404 and "no hay modelos" in r.json()["detail"]["message"].lower()
    ing = auth_headers(Role.INGENIERO, reservoirs=ALL)
    assert client.post("/ml/train", headers=ing, json={"kinds": ["magia"]}).status_code == 422


def test_train_job_runs_in_background(client, db, auth_headers, ml_data, monkeypatch):
    calls = {}

    def fake(session, settings, codes, kinds, test_years, user_id, progress=None, fast=False):
        calls["args"] = (codes, kinds, test_years)
        progress(0.5, "mitad")
        return {"TULE": {"modelo_activo": "xgboost", "mae_medio_hm3": 1.0}}

    monkeypatch.setattr(ml_service, "train_and_register", fake)
    ing = auth_headers(Role.INGENIERO, reservoirs=ALL)
    r = client.post(
        "/ml/train",
        headers=ing,
        json={"reservoir_codes": ["TULE"], "kinds": ["xgboost"], "test_years": [2025]},
    )
    assert r.status_code == 202
    jobs = client.get("/ml/jobs", headers=ing).json()
    assert jobs[0]["status"] == "TERMINADA" and jobs[0]["result"]["TULE"]["modelo_activo"] == "xgboost"
    assert calls["args"] == (["TULE"], ("xgboost",), [2025])


def test_not_enough_data(client, auth_headers, reservoirs):
    ing = auth_headers(Role.INGENIERO, reservoirs=ALL)
    r = client.post("/ml/train", headers=ing, json={})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "NOT_ENOUGH_DATA"


def test_model_row_is_json_safe(db, ml_data):
    ml_service.train_and_register(db, ml_data, ["TULE"], ("persistencia",), [2025], None)
    m = db.query(MLModel).one()
    assert m.metrics[0]["horizonte"] == 30 and isinstance(m.score, float)
