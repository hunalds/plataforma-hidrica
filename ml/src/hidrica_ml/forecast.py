"""Predicción interpretable para el panel: trayectoria de 90 días y respuestas en lenguaje sencillo.

A partir de los cuantiles de ΔV se obtienen la cota y el volumen útil esperados, los días de reserva,
la probabilidad de cruzar cada umbral y si el embalse va a aliviar. Las probabilidades se calculan
suponiendo una distribución normal ajustada a p10–p90 (σ = (p90 − p10) / 2,563).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.stats import norm

from hidrica_ml.data import ReservoirSeries
from hidrica_ml.features import HORIZONS_REPORT, MAX_HORIZON
from hidrica_ml.models import Forecaster

Z90 = 1.2816  # cuantil 90 % de la normal estándar
M3S_TO_HM3_PER_DAY = 0.0864


@dataclass
class Forecast:
    code: str
    origin: pd.Timestamp
    model_kind: str
    days: list[dict]  # trayectoria diaria
    horizons: list[dict]  # resumen a 30 / 60 / 90 días
    probabilities: list[dict]  # P(cruzar umbral) por horizonte
    importance: list[dict] = field(default_factory=list)


def _prob_below(level_p10: float, level_p50: float, level_p90: float, threshold: float) -> float:
    sigma = max((level_p90 - level_p10) / (2 * Z90), 1e-6)
    return float(norm.cdf((threshold - level_p50) / sigma))


def make_forecast(
    model: Forecaster,
    s: ReservoirSeries,
    origin: pd.Timestamp,
    thresholds: dict[str, float | None],
    labels: dict[str, str] | None = None,
) -> Forecast:
    q = model.predict(s, pd.DatetimeIndex([origin]))[0]  # [90, 3] ΔV
    v0 = float(s.df.loc[origin, "volume_hm3"])
    lo_v, hi_v = float(s.curve.volume[0]), float(s.curve.volume[-1])
    vol = np.clip(v0 + q, lo_v, hi_v)
    lvl = s.curve.level_at(vol)
    dead, cap = s.dead_volume, s.useful_capacity

    # Consumo actual (media de los últimos 7 días) para los días de reserva proyectados
    recent = s.df.loc[:origin].tail(7)
    daily_out = float((recent["outflow_m3s"].fillna(0) + recent["eco_flow_m3s"].fillna(0)).mean()) * M3S_TO_HM3_PER_DAY

    days = []
    for i in range(MAX_HORIZON):
        d = origin + pd.Timedelta(days=i + 1)
        days.append(
            {
                "day": d.date().isoformat(),
                "volume_p10": round(float(vol[i, 0]), 3),
                "volume_p50": round(float(vol[i, 1]), 3),
                "volume_p90": round(float(vol[i, 2]), 3),
                "level_p10": round(float(lvl[i, 0]), 3),
                "level_p50": round(float(lvl[i, 1]), 3),
                "level_p90": round(float(lvl[i, 2]), 3),
            }
        )

    horizons = []
    for h in HORIZONS_REPORT:
        useful = max(0.0, float(vol[h - 1, 1]) - dead)
        horizons.append(
            {
                "horizon_days": h,
                "date": days[h - 1]["day"],
                "level_p50": days[h - 1]["level_p50"],
                "level_p10": days[h - 1]["level_p10"],
                "level_p90": days[h - 1]["level_p90"],
                "volume_p50": days[h - 1]["volume_p50"],
                "useful_volume_p50": round(useful, 3),
                "availability_pct_p50": round(useful / cap * 100, 1) if cap > 0 else None,
                "reserve_days_p50": round(useful / daily_out) if daily_out > 0 else None,
                "spill_probability": round(1 - _prob_below(*lvl[h - 1], s.normal_level), 3),
                "will_spill": bool(lvl[h - 1, 1] > s.normal_level),
            }
        )

    probabilities = []
    labels = labels or {}
    for key, value in thresholds.items():
        if value is None:
            continue
        below = key.startswith("low") or key == "dead_level"
        for h in HORIZONS_REPORT:
            p_below = _prob_below(*lvl[h - 1], value)
            probabilities.append(
                {
                    "threshold": key,
                    "label": labels.get(key, key),
                    "level": value,
                    "direction": "bajo" if below else "sobre",
                    "horizon_days": h,
                    "probability": round(p_below if below else 1 - p_below, 3),
                }
            )

    imp = model.importance() or {}
    return Forecast(
        code=s.code,
        origin=origin,
        model_kind=model.kind,
        days=days,
        horizons=horizons,
        probabilities=probabilities,
        importance=[{"feature": k, "weight": round(v, 4)} for k, v in list(imp.items())[:10]],
    )
