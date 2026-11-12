"""Pruebas del dataset sintético (HU-0.5)."""

from __future__ import annotations

import json
from datetime import date

import numpy as np
import pandas as pd
import pytest

from hidrica_ml.schema import COLUMN_NAMES, M3S_TO_HM3_PER_DAY
from hidrica_ml.synthetic import curve_for, curve_table, generate, load_reservoirs, write_dataset

END = date(2026, 10, 31)


@pytest.fixture(scope="module")
def data() -> tuple[pd.DataFrame, pd.DataFrame]:
    return generate(seed=2026, end=END)


@pytest.fixture(scope="module")
def reservoirs():
    return {r.code: r for r in load_reservoirs()}


def test_columns_match_import_template(data):
    record, _ = data
    assert tuple(record.columns) == COLUMN_NAMES


def test_three_reservoirs_with_official_start_dates(data, reservoirs):
    record, _ = data
    assert set(record["embalse"]) == {"TULE", "MANUELOTE", "TRES_RIOS"}
    starts = record.groupby("embalse")["fecha"].min().to_dict()
    assert starts == {"TULE": "2005-01-01", "MANUELOTE": "2005-01-01", "TRES_RIOS": "2008-01-01"}
    assert set(record.groupby("embalse")["fecha"].max()) == {END.isoformat()}


def test_no_missing_or_duplicate_days(data):
    record, _ = data
    for code, g in record.groupby("embalse"):
        dates = pd.to_datetime(g["fecha"])
        assert dates.is_unique, f"{code}: fechas duplicadas"
        expected = pd.date_range(dates.min(), dates.max(), freq="D")
        assert len(dates) == len(expected), f"{code}: días faltantes"


def test_levels_within_physical_ranges(data, reservoirs):
    record, _ = data
    for code, g in record.groupby("embalse"):
        r = reservoirs[code]
        # nunca por debajo del volumen muerto (la toma no extrae debajo) ni más de 2 m sobre el normal
        assert g["cota_msnm"].min() >= r.h_dead - 0.3, code
        assert g["cota_msnm"].max() <= r.h_normal + 2.0, code


def test_spill_days_exist_and_coincide_with_level_above_normal(data, reservoirs):
    record, truth = data
    for code, g in record.groupby("embalse"):
        t = truth[truth["embalse"] == code]
        spill = t["alivio_hm3"].to_numpy() > 0
        assert spill.sum() > 30, f"{code}: muy pocos días de alivio"
        above = g["cota_msnm"].to_numpy() >= reservoirs[code].h_normal - 0.01
        assert above[spill].mean() > 0.95, f"{code}: alivio sin cota sobre el nivel normal"


def test_dry_periods_exist_for_scarcity_alerts(data, reservoirs):
    record, _ = data
    for code, g in record.groupby("embalse"):
        r = reservoirs[code]
        # al menos un período con la cota en el tercio inferior del rango útil
        low = r.h_dead + (r.h_normal - r.h_dead) / 3
        assert (g["cota_msnm"] < low + (r.h_normal - r.h_dead) * 0.25).any(), code
        assert g["cota_msnm"].std() > 0.5, code


def test_volume_consistent_with_curve(data, reservoirs):
    record, _ = data
    for code, g in record.groupby("embalse"):
        curve = curve_for(reservoirs[code])
        v_from_level = curve.volume(g["cota_msnm"].to_numpy())
        # la cota se reporta al cm: el error relativo debe ser pequeño
        rel = np.abs(v_from_level - g["volumen_hm3"].to_numpy()) / g["volumen_hm3"].to_numpy()
        assert np.median(rel) < 0.002 and rel.max() < 0.01, code


def test_daily_water_balance_closes_with_hidden_terms(data):
    """ΔV = (entrada − salida − ecológico)·0,0864 − evaporación − alivio (base para M12)."""
    record, truth = data
    for code, g in record.groupby("embalse"):
        t = truth[truth["embalse"] == code]
        v = t["volumen_exacto_hm3"].to_numpy()
        flows = (g["caudal_entrada_m3s"] - g["caudal_salida_m3s"] - g["gasto_ecologico_m3s"]).to_numpy()
        expected = flows[1:] * M3S_TO_HM3_PER_DAY - t["evaporacion_hm3"].to_numpy()[1:] - t["alivio_hm3"].to_numpy()[1:]
        residual = np.diff(v) - expected
        # el residuo solo viene del redondeo de los caudales y del piso del volumen muerto
        assert np.quantile(np.abs(residual), 0.99) < 0.01, code


def test_flows_are_non_negative_and_gates_in_range(data):
    record, _ = data
    for col in ("caudal_entrada_m3s", "caudal_salida_m3s", "gasto_ecologico_m3s", "captacion_m3s"):
        assert (record[col] >= 0).all(), col
    assert record["apertura_compuertas_pct"].between(0, 100).all()


def test_generation_is_deterministic():
    a, _ = generate(seed=7, end=date(2010, 12, 31))
    b, _ = generate(seed=7, end=date(2010, 12, 31))
    c, _ = generate(seed=8, end=date(2010, 12, 31))
    pd.testing.assert_frame_equal(a, b)
    assert not a["cota_msnm"].equals(c["cota_msnm"])


def test_curve_table_is_monotonic(reservoirs):
    for r in reservoirs.values():
        t = curve_table(r)
        assert t["volumen_hm3"].is_monotonic_increasing
        assert t["area_km2"].is_monotonic_increasing
        assert t["cota_msnm"].min() <= r.h_dead and t["cota_msnm"].max() >= r.h_normal


def test_written_files_are_marked_synthetic(tmp_path):
    meta = write_dataset(tmp_path, seed=1, end=date(2009, 12, 31))
    assert meta["SINTETICO"] is True
    saved = json.loads((tmp_path / "metadata.json").read_text(encoding="utf-8"))
    assert saved["SINTETICO"] is True and "No son mediciones" in saved["advertencia"]
    names = {p.name for p in tmp_path.iterdir()}
    assert {"movimiento_diario_sintetico.csv", "verdad_sintetica.csv", "metadata.json"} <= names
    assert all("sintetic" in n or n == "metadata.json" for n in names)
