"""Backtesting con origen móvil (walk-forward) — objetivo 4 de la tesis.

Para cada año de prueba Y:
    1. se entrena con todos los datos hasta el 31/12 de Y−1 (incluidos los objetivos: no hay fuga),
    2. se predice desde orígenes repartidos a lo largo de Y (cada `origin_every` días),
    3. se compara con lo que realmente pasó 30, 60 y 90 días después.
Así se simula exactamente el uso operativo: el modelo nunca ve el futuro que está prediciendo.
"""

from __future__ import annotations

import time
from collections.abc import Callable

import numpy as np
import pandas as pd

from hidrica_ml.data import ReservoirSeries
from hidrica_ml.features import HORIZONS_REPORT, MAX_HORIZON, make_features
from hidrica_ml.metrics import all_metrics
from hidrica_ml.models import Forecaster

Progress = Callable[[str], None]


def origins_for_year(s: ReservoirSeries, year: int, every: int = 7) -> pd.DatetimeIndex:
    """Orígenes del año con variables completas y con dato real a 90 días."""
    X = make_features(s)
    v = s.df["volume_hm3"]
    days = pd.date_range(f"{year}-01-01", f"{year}-12-31", freq=f"{every}D")
    ok = []
    for d in days:
        if d not in X.index or X.loc[d].isna().any():
            continue
        target_day = d + pd.Timedelta(days=MAX_HORIZON)
        if target_day > v.index[-1] or pd.isna(v.get(target_day)):
            continue
        ok.append(d)
    return pd.DatetimeIndex(ok)


def walk_forward(
    s: ReservoirSeries,
    factory: Callable[[], Forecaster],
    test_years: list[int],
    origin_every: int = 7,
    progress: Progress | None = None,
) -> pd.DataFrame:
    """Una fila por (año, origen, horizonte) con real, p10, p50, p90 en volumen y cota."""
    rows = []
    v = s.df["volume_hm3"]
    for year in test_years:
        origins = origins_for_year(s, year, origin_every)
        if len(origins) == 0:
            continue
        t0 = time.perf_counter()
        model = factory().fit(s, end=pd.Timestamp(f"{year - 1}-12-31"))
        pred = model.predict(s, origins)  # [n, 90, 3]
        if progress:
            progress(f"{s.code} · {model.kind} · {year}: {len(origins)} orígenes ({time.perf_counter() - t0:.0f} s)")
        v0 = v.reindex(origins).to_numpy()
        for h in HORIZONS_REPORT:
            actual = v.reindex(origins + pd.Timedelta(days=h)).to_numpy()
            q = pred[:, h - 1, :] + v0[:, None]
            for i, o in enumerate(origins):
                rows.append(
                    {
                        "embalse": s.code,
                        "modelo": model.kind,
                        "anio": year,
                        "origen": o,
                        "horizonte": h,
                        "v_origen": v0[i],
                        "v_real": actual[i],
                        "v_p10": q[i, 0],
                        "v_p50": q[i, 1],
                        "v_p90": q[i, 2],
                    }
                )
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    for col in ("real", "p10", "p50", "p90"):
        df[f"cota_{col}"] = s.curve.level_at(np.clip(df[f"v_{col}"].to_numpy(), s.curve.volume[0], s.curve.volume[-1]))
    return df


def summarize(results: pd.DataFrame) -> pd.DataFrame:
    """Métricas por embalse, modelo y horizonte, en volumen (hm³) y en cota (m)."""
    out = []
    for (code, kind, h), g in results.groupby(["embalse", "modelo", "horizonte"]):
        mv = all_metrics(g["v_real"].to_numpy(), g["v_p50"].to_numpy(), g["v_p10"].to_numpy(), g["v_p90"].to_numpy())
        mc = all_metrics(
            g["cota_real"].to_numpy(), g["cota_p50"].to_numpy(), g["cota_p10"].to_numpy(), g["cota_p90"].to_numpy()
        )
        out.append(
            {
                "embalse": code,
                "modelo": kind,
                "horizonte": h,
                "n": mv["n"],
                "MAE_hm3": mv["MAE"],
                "RMSE_hm3": mv["RMSE"],
                "MAPE_%": mv["MAPE"],
                "R2": mv["R2"],
                "MAE_cota_m": mc["MAE"],
                "RMSE_cota_m": mc["RMSE"],
                "cobertura_80_%": mv["cobertura_80"],
            }
        )
    return pd.DataFrame(out)


def score(summary: pd.DataFrame, kind: str) -> float:
    """Puntaje para elegir el mejor modelo: MAE medio de volumen en 30, 60 y 90 días (menor es mejor)."""
    g = summary[summary["modelo"] == kind]
    return float(g["MAE_hm3"].mean()) if len(g) else float("inf")
