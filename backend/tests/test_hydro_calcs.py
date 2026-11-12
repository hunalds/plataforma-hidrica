"""Pruebas unitarias de los cálculos operativos (M12, HU-2.2).

Incluye una validación contra la "verdad" del dataset sintético: el alivio estimado por el balance
debe parecerse al alivio real de la simulación (que en campo no se mide).
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from app.services import hydro_calcs as hc

ROOT = Path(__file__).resolve().parents[2]


def test_conversion_m3s_to_hm3_per_day():
    assert hc.flow_to_hm3_per_day(1) == pytest.approx(0.0864)
    assert hc.flow_to_hm3_per_day(None) == 0


def test_useful_volume_and_capacity_never_negative():
    assert hc.useful_volume(120, 26.6) == pytest.approx(93.4)
    assert hc.useful_volume(20, 26.6) == 0
    assert hc.useful_capacity(152.5, 26.6) == pytest.approx(125.9)


def test_availability_can_exceed_100_when_spilling():
    assert hc.availability_pct(62.95, 125.9) == pytest.approx(50)
    assert hc.availability_pct(130, 125.9) > 100
    assert hc.availability_pct(10, 0) is None


def test_reserve_days():
    # 86,4 hm³ útiles con 9 + 1 m³/s de salida = 0,864 hm³/día → 100 días
    assert hc.reserve_days(86.4, 9, 1) == pytest.approx(100)
    assert hc.reserve_days(86.4, 0, None) is None


def test_spill_volume_only_above_normal():
    assert hc.spill_volume(160, 152.5) == pytest.approx(7.5)
    assert hc.spill_volume(140, 152.5) == 0


def test_daily_balance_without_spill():
    b = hc.daily_balance(
        volume_today_hm3=100.5,
        volume_yesterday_hm3=100.0,
        inflow_m3s=10,
        outflow_m3s=3,
        eco_flow_m3s=1,
        level_m=30,
        normal_level_m=33.4,
    )
    assert b.net_hm3 == pytest.approx(6 * 0.0864)
    assert b.observed_change_hm3 == pytest.approx(0.5)
    assert b.spill_estimate_hm3 == 0
    assert b.residual_hm3 == pytest.approx(0.5 - 0.5184)


def test_daily_balance_estimates_spill_when_above_normal():
    b = hc.daily_balance(
        volume_today_hm3=153.0,
        volume_yesterday_hm3=153.0,
        inflow_m3s=50,
        outflow_m3s=4,
        eco_flow_m3s=0.5,
        level_m=33.5,
        normal_level_m=33.4,
    )
    assert b.spill_estimate_hm3 == pytest.approx(45.5 * 0.0864)
    assert b.residual_hm3 == pytest.approx(0)


def test_daily_balance_without_previous_volume():
    b = hc.daily_balance(
        volume_today_hm3=100,
        volume_yesterday_hm3=None,
        inflow_m3s=1,
        outflow_m3s=1,
        eco_flow_m3s=0,
        level_m=30,
        normal_level_m=33.4,
    )
    assert b.observed_change_hm3 is None and b.residual_hm3 is None


TULE = {"normal_level": 33.4, "dead_level": 26.6}
THRESH = {"low_critical": 27.5, "low_alert": 29.0, "high_alert": 33.0, "spill_level": 33.4}


@pytest.mark.parametrize(
    ("level", "light", "direction"),
    [
        (27.0, hc.Light.RED, hc.Direction.SCARCITY),
        (28.5, hc.Light.YELLOW, hc.Direction.SCARCITY),
        (31.0, hc.Light.GREEN, hc.Direction.NORMAL),
        (33.2, hc.Light.YELLOW, hc.Direction.FLOOD),
        (33.5, hc.Light.RED, hc.Direction.FLOOD),
        (None, hc.Light.GRAY, hc.Direction.NORMAL),
    ],
)
def test_traffic_light_with_thresholds(level, light, direction):
    t = hc.traffic_light(level, **TULE, **THRESH)
    assert (t.light, t.direction) == (light, direction)
    assert t.thresholds_defined is True


def test_traffic_light_fallback_without_thresholds():
    assert hc.traffic_light(33.5, **TULE).light == hc.Light.RED
    assert hc.traffic_light(26.5, **TULE).direction == hc.Direction.SCARCITY
    t = hc.traffic_light(30, **TULE)
    assert t.light == hc.Light.GREEN and t.thresholds_defined is False


def test_operational_status_with_linear_curve():
    # Curva lineal de prueba: V = 10·(h − 20)
    def vol(h: float) -> float:
        return 10 * (h - 20)

    s = hc.operational_status(
        level_m=30, volume_hm3=None, volume_at=vol, outflow_m3s=4, eco_flow_m3s=0.5, **TULE
    )
    assert (
        s.volume_hm3 == 100
        and s.dead_volume_hm3 == pytest.approx(66)
        and s.normal_volume_hm3 == pytest.approx(134)
    )
    assert s.useful_volume_hm3 == pytest.approx(34)
    assert s.availability_pct == pytest.approx(50)
    assert s.reserve_days == pytest.approx(34 / (4.5 * 0.0864))
    assert s.spill_hm3 == 0 and s.is_spilling is False


def test_spill_estimate_matches_synthetic_truth():
    """Con el dataset sintético, el alivio estimado por el balance se acerca al alivio simulado."""
    data_dir = ROOT / "ml" / "data" / "synthetic"
    rec = list(csv.DictReader((data_dir / "movimiento_diario_sintetico.csv").open(encoding="utf-8")))
    truth = list(csv.DictReader((data_dir / "verdad_sintetica.csv").open(encoding="utf-8")))
    rows = [(r, t) for r, t in zip(rec, truth, strict=True) if r["embalse"] == "TULE"]

    estimated, real = 0.0, 0.0
    prev_v = None
    for cur, t in rows:
        v = float(t["volumen_exacto_hm3"])
        if prev_v is not None:
            b = hc.daily_balance(
                volume_today_hm3=v,
                volume_yesterday_hm3=prev_v,
                inflow_m3s=float(cur["caudal_entrada_m3s"]),
                outflow_m3s=float(cur["caudal_salida_m3s"]),
                eco_flow_m3s=float(cur["gasto_ecologico_m3s"]),
                level_m=float(cur["cota_msnm"]),
                normal_level_m=33.4,
            )
            estimated += b.spill_estimate_hm3
            real += float(t["alivio_hm3"])
        prev_v = v
    assert real > 0
    # La evaporación de los días con alivio se confunde con alivio: se acepta ±15 %
    assert estimated == pytest.approx(real, rel=0.15)
