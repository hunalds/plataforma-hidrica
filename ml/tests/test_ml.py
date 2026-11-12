"""Pruebas del flujo de ML (Iteración 4) con el dataset sintético. Rápidas: pocos años y LSTM corta."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from hidrica_ml import metrics
from hidrica_ml.backtest import origins_for_year, summarize, walk_forward
from hidrica_ml.data import load_synthetic
from hidrica_ml.features import FEATURES, STEPS, make_features, make_targets, training_matrix
from hidrica_ml.forecast import make_forecast
from hidrica_ml.models import (
    LSTMModel,
    PersistenceModel,
    SeasonalModel,
    XGBoostModel,
    apply_calibration,
    calibration_factors,
    load_model,
    steps_to_daily,
)
from hidrica_ml.synthetic_satellite import generate as gen_sat
from hidrica_ml.training import default_test_years, train_reservoir


@pytest.fixture(scope="module")
def tule():
    return load_synthetic("TULE")


@pytest.fixture(scope="module")
def tule_short(tule):
    """Serie recortada a 2016–2022 para que las pruebas sean rápidas."""
    s = load_synthetic("TULE")
    s.df = s.df.loc["2016-01-01":"2022-12-31"]
    return s


# ---------------------------------------------------------------- datos sintéticos satelitales


def test_synthetic_satellite_is_coherent_with_inflow():
    sat = gen_sat()
    mov = pd.read_csv(load_synthetic.__globals__["SYNTH_DIR"] / "movimiento_diario_sintetico.csv")
    d = sat.merge(mov[["embalse", "fecha", "caudal_entrada_m3s"]], on=["embalse", "fecha"])
    for _, g in d.groupby("embalse"):
        rain, q = g["precipitacion_mm"].to_numpy(), g["caudal_entrada_m3s"].to_numpy()
        assert 0.5 < np.corrcoef(rain[:-2], q[2:])[0, 1] < 0.85  # coherente pero no perfecta
        assert 1300 < rain.sum() / (len(g) / 365.25) < 1500
        assert g["humedad_suelo_m3m3"].between(0.15, 0.45).all()


# ---------------------------------------------------------------- features


def test_features_do_not_look_into_the_future(tule):
    X = make_features(tule)
    s2 = load_synthetic("TULE")
    s2.df.loc["2020-06-02":, :] = np.nan  # se "borra" el futuro desde el 2/6
    X2 = make_features(s2)
    pd.testing.assert_series_equal(X.loc["2020-06-01"], X2.loc["2020-06-01"], check_names=False)


def test_targets_and_training_matrix_respect_end(tule):
    Y = make_targets(tule)
    d = pd.Timestamp("2020-01-01")
    v = tule.df["volume_hm3"]
    assert Y.loc[d, 30] == pytest.approx(v[d + pd.Timedelta(days=30)] - v[d])
    X, Y = training_matrix(tule, end=pd.Timestamp("2019-12-31"))
    assert (X.index + pd.Timedelta(days=max(STEPS)) <= pd.Timestamp("2019-12-31")).all()
    assert list(X.columns) == FEATURES and not X.isna().any().any()


# ---------------------------------------------------------------- métricas y utilidades


def test_metrics_basic():
    y, p = np.array([1.0, 2.0, 3.0, 4.0]), np.array([1.0, 2.0, 3.0, 5.0])
    m = metrics.all_metrics(y, p, p - 0.5, p + 0.5)
    assert m["MAE"] == 0.25 and m["RMSE"] == 0.5 and m["MAPE"] == pytest.approx(6.25)
    assert m["R2"] == pytest.approx(0.8) and m["cobertura_80"] == 75.0


def test_steps_to_daily_interpolates_from_zero_and_sorts():
    steps = np.zeros((1, len(STEPS), 3))
    steps[0, 0] = [3, 1, 2]  # desordenado a propósito
    daily = steps_to_daily(steps)
    assert daily.shape == (1, 90, 3)
    assert (np.diff(daily[0], axis=1) >= 0).all()
    assert daily[0, 4].tolist() == [1, 2, 3]  # día 5
    assert daily[0, 0].tolist() == pytest.approx([0.2, 0.4, 0.6])  # día 1: 1/5 del paso


def test_calibration_widens_too_narrow_bands():
    rng = np.random.default_rng(0)
    actual = rng.normal(0, 1, (500, 2))
    narrow = np.stack([np.full((500, 2), -0.3), np.zeros((500, 2)), np.full((500, 2), 0.3)], axis=2)
    k = calibration_factors(narrow, actual)
    cov = np.mean((actual >= apply_calibration(narrow, k)[:, :, 0]) & (actual <= apply_calibration(narrow, k)[:, :, 2]))
    assert (k > 3).all() and cov >= 0.8


# ---------------------------------------------------------------- modelos


@pytest.mark.parametrize("cls", [PersistenceModel, SeasonalModel])
def test_baselines(tule_short, cls, tmp_path):
    m = cls().fit(tule_short, end=pd.Timestamp("2021-12-31"))
    origins = origins_for_year(tule_short, 2022)
    p = m.predict(tule_short, origins)
    assert p.shape == (len(origins), 90, 3) and (np.diff(p, axis=2) >= 0).all()
    m.save(tmp_path / "m")
    np.testing.assert_allclose(load_model(tmp_path / "m").predict(tule_short, origins), p)


def test_xgboost_beats_persistence_and_roundtrips(tule_short, tmp_path):
    res = pd.concat(
        [
            walk_forward(tule_short, f, [2022], origin_every=14)
            for f in (PersistenceModel, lambda: XGBoostModel(n_estimators=80))
        ]
    )
    summ = summarize(res).set_index(["modelo", "horizonte"])
    assert summ.loc[("xgboost", 30), "MAE_hm3"] < summ.loc[("persistencia", 30), "MAE_hm3"]

    m = XGBoostModel(n_estimators=40).fit(tule_short)
    origins = pd.DatetimeIndex(["2022-03-01", "2022-08-01"])
    m.save(tmp_path / "x")
    np.testing.assert_allclose(
        load_model(tmp_path / "x").predict(tule_short, origins), m.predict(tule_short, origins), rtol=1e-5
    )
    imp = m.importance()
    assert set(imp) == set(FEATURES) and sum(imp.values()) == pytest.approx(1.0)


def test_lstm_trains_predicts_and_roundtrips(tule_short, tmp_path):
    m = LSTMModel(epochs=2, hidden=16).fit(tule_short, end=pd.Timestamp("2021-12-31"))
    origins = origins_for_year(tule_short, 2022, every=30)
    p = m.predict(tule_short, origins)
    assert p.shape == (len(origins), 90, 3) and np.isfinite(p).all()
    m.save(tmp_path / "l")
    np.testing.assert_allclose(load_model(tmp_path / "l").predict(tule_short, origins), p, rtol=1e-5)


def test_walk_forward_never_trains_on_test_year(tule_short, monkeypatch):
    seen_ends = []
    original = PersistenceModel.fit

    def spy(self, s, end=None):
        seen_ends.append(end)
        return original(self, s, end)

    monkeypatch.setattr(PersistenceModel, "fit", spy)
    res = walk_forward(tule_short, PersistenceModel, [2021, 2022])
    assert seen_ends == [pd.Timestamp("2020-12-31"), pd.Timestamp("2021-12-31")]
    assert set(res["anio"]) == {2021, 2022} and set(res["horizonte"]) == {30, 60, 90}
    assert (res["cota_real"] > 20).all()  # convertido a cota con la curva


# ---------------------------------------------------------------- entrenamiento y predicción interpretable


def test_train_reservoir_writes_artifacts_and_manifest(tule_short, tmp_path):
    trained, results = train_reservoir(
        tule_short, ("persistencia", "xgboost"), [2022], out_dir=tmp_path, version_tag="v1", origin_every=14
    )
    assert {t.kind for t in trained} == {"persistencia", "xgboost"}
    for t in trained:
        assert (t.artifact_dir / "manifest.json").exists() and (t.artifact_dir / "backtest.csv").exists()
        assert t.score > 0 and len(t.metrics) == 3
    assert default_test_years(tule_short) == [2019, 2020, 2021, 2022]


def test_forecast_is_interpretable(tule_short):
    m = SeasonalModel().fit(tule_short)
    origin = pd.Timestamp("2022-09-01")
    thresholds = {"low_alert": 29.0, "low_critical": 27.5, "spill_level": 33.4}
    f = make_forecast(m, tule_short, origin, thresholds)
    assert len(f.days) == 90 and [h["horizon_days"] for h in f.horizons] == [30, 60, 90]
    for d in f.days:
        assert d["level_p10"] <= d["level_p50"] <= d["level_p90"]
    for h in f.horizons:
        assert 0 <= h["spill_probability"] <= 1 and h["reserve_days_p50"] is None or h["reserve_days_p50"] >= 0
    probs = {(p["threshold"], p["horizon_days"]): p for p in f.probabilities}
    assert probs[("low_alert", 30)]["direction"] == "bajo" and probs[("spill_level", 30)]["direction"] == "sobre"
    assert all(0 <= p["probability"] <= 1 for p in f.probabilities)
