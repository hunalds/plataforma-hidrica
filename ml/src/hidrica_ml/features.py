"""Variables explicativas (features) y objetivos para la predicción a 30/60/90 días.

Regla de oro: las features de la fecha de origen t solo usan datos hasta t (sin mirar el futuro).
El objetivo es el CAMBIO de volumen ΔV(t, h) = V(t+h) − V(t): es más estable que el volumen absoluto
y permite convertir a cota con la curva vigente.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from hidrica_ml.data import ReservoirSeries

HORIZONS_REPORT = (30, 60, 90)  # horizontes del documento de requerimientos
STEPS = tuple(range(5, 91, 5))  # pasos que se modelan (la trayectoria diaria se interpola)
MAX_HORIZON = 90
WET_MONTHS = {4, 5, 9, 10, 11}  # régimen bimodal del Zulia

FEATURE_LABELS = {
    "volume_rel": "Volumen útil actual (% de la capacidad)",
    "volume_hm3": "Volumen actual",
    "dv_1": "Cambio de volumen del último día",
    "dv_7": "Cambio de volumen de la última semana",
    "dv_30": "Cambio de volumen del último mes",
    "inflow_7": "Caudal de entrada (media 7 días)",
    "inflow_30": "Caudal de entrada (media 30 días)",
    "outflow_7": "Extracción + gasto ecológico (media 7 días)",
    "outflow_30": "Extracción + gasto ecológico (media 30 días)",
    "precip_7": "Lluvia de los últimos 7 días",
    "precip_30": "Lluvia de los últimos 30 días",
    "precip_90": "Lluvia de los últimos 90 días",
    "soil": "Humedad del suelo actual",
    "soil_7": "Humedad del suelo (media 7 días)",
    "doy_sin": "Época del año (seno)",
    "doy_cos": "Época del año (coseno)",
    "wet_season": "Temporada de lluvias",
}
FEATURES = list(FEATURE_LABELS)

# Variables que entran a la LSTM en cada día de la ventana (normalizadas)
SEQ_FEATURES = ["volume_rel", "dv_1", "inflow_m3s", "out_total", "precip_mm", "soil_moisture", "doy_sin", "doy_cos"]


def base_frame(s: ReservoirSeries) -> pd.DataFrame:
    """Columnas diarias derivadas que usan tanto XGBoost como la LSTM."""
    df = s.df.copy()
    df["out_total"] = df["outflow_m3s"].fillna(0) + df["eco_flow_m3s"].fillna(0)
    df["volume_rel"] = (df["volume_hm3"] - s.dead_volume) / s.useful_capacity
    df["dv_1"] = df["volume_hm3"].diff(1)
    doy = df.index.dayofyear.to_numpy()
    df["doy_sin"] = np.sin(2 * np.pi * doy / 365.25)
    df["doy_cos"] = np.cos(2 * np.pi * doy / 365.25)
    df["wet_season"] = df.index.month.isin(WET_MONTHS).astype(float)
    return df


def make_features(s: ReservoirSeries) -> pd.DataFrame:
    df = base_frame(s)
    v = df["volume_hm3"]
    has_precip = df["precip_mm"].notna().any()
    has_soil = df["soil_moisture"].notna().any()
    out = pd.DataFrame(
        {
            "volume_rel": df["volume_rel"],
            "volume_hm3": v,
            "dv_1": v.diff(1),
            "dv_7": v.diff(7),
            "dv_30": v.diff(30),
            "inflow_7": df["inflow_m3s"].rolling(7, min_periods=5).mean(),
            "inflow_30": df["inflow_m3s"].rolling(30, min_periods=20).mean(),
            "outflow_7": df["out_total"].rolling(7, min_periods=5).mean(),
            "outflow_30": df["out_total"].rolling(30, min_periods=20).mean(),
            "precip_7": df["precip_mm"].rolling(7, min_periods=5).sum() if has_precip else 0.0,
            "precip_30": df["precip_mm"].rolling(30, min_periods=20).sum() if has_precip else 0.0,
            "precip_90": df["precip_mm"].rolling(90, min_periods=60).sum() if has_precip else 0.0,
            "soil": df["soil_moisture"] if has_soil else 0.0,
            "soil_7": df["soil_moisture"].rolling(7, min_periods=5).mean() if has_soil else 0.0,
            "doy_sin": df["doy_sin"],
            "doy_cos": df["doy_cos"],
            "wet_season": df["wet_season"],
        },
        index=df.index,
    )
    return out[FEATURES]


def make_targets(s: ReservoirSeries, steps: tuple[int, ...] = STEPS) -> pd.DataFrame:
    """ΔV(t, h) para cada paso h (NaN si no hay dato en t+h)."""
    v = s.df["volume_hm3"]
    return pd.DataFrame({h: v.shift(-h) - v for h in steps}, index=s.df.index)


def training_matrix(
    s: ReservoirSeries, end: pd.Timestamp | None = None, steps: tuple[int, ...] = STEPS
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(X, Y) con orígenes cuyo objetivo completo cae antes de `end` (sin fuga de información)."""
    X, Y = make_features(s), make_targets(s, steps)
    ok = X.notna().all(axis=1) & Y.notna().all(axis=1)
    if end is not None:
        ok &= X.index + pd.Timedelta(days=max(steps)) <= end
    return X[ok], Y[ok]
