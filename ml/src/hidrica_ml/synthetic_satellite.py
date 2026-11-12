"""Lluvia y humedad del suelo SINTÉTICAS, coherentes con el histórico sintético de los embalses.

¿Por qué? Los datos satelitales reales (CHIRPS, ERA5-Land) son reales, pero el histórico de los embalses
todavía es sintético. Un modelo entrenado con lluvia real y cotas inventadas no encontraría ninguna
relación verdadera, y sus métricas no significarían nada. Para desarrollar y validar el flujo de ML se
generan variables satelitales que SÍ explican los caudales simulados:

    lluvia(t)          ← escorrentía que llega al embalse 1–3 días después (inversión del caudal)
    humedad_suelo(t)   ← balance de un "cubo" de suelo alimentado por la lluvia

Cuando lleguen los datos de MINAGUAS se entrena con las fuentes reales (`chirps`, `era5_land_openmeteo`)
cambiando una sola opción (ML_SATELLITE_SOURCE). Ver docs/CAMBIOS-PROMPT.md (C-24).

Uso (desde ml/):
    uv run python -m hidrica_ml.synthetic_satellite
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ML_DIR = Path(__file__).resolve().parents[2]
SYNTH_DIR = ML_DIR / "data" / "synthetic"
SOURCE_CSV = SYNTH_DIR / "movimiento_diario_sintetico.csv"
OUT_CSV = SYNTH_DIR / "satelite_sintetico.csv"

LAG_DAYS = 2  # la escorrentía tarda ~2 días en llegar al embalse
TARGET_ANNUAL_MM = 1400.0  # orden de magnitud de la lluvia anual en las cuencas (CHIRPS real ~1.200–1.600 mm)


def rain_from_inflow(inflow: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Lluvia diaria (mm) que explica el caudal de entrada `LAG_DAYS` días después."""
    n = len(inflow)
    base = pd.Series(inflow).rolling(60, min_periods=1, center=True).quantile(0.2).to_numpy()  # flujo base
    quick = np.clip(np.roll(inflow, -LAG_DAYS) - base, 0, None)  # escorrentía rápida futura
    quick[-LAG_DAYS:] = 0
    rain = quick * rng.lognormal(0.0, 0.8, n)  # ruido multiplicativo (la lluvia satelital no es exacta)
    showers = rng.random(n) < 0.08  # chubascos pequeños que el suelo absorbe (no llegan al embalse)
    rain[showers] += rng.gamma(1.2, 3.0, int(showers.sum()))
    rain = np.where(rain < 1.0, 0.0, rain)  # días secos
    scale = TARGET_ANNUAL_MM / (rain.sum() / (n / 365.25))
    return rain * scale


def soil_from_rain(rain: np.ndarray, *, low: float = 0.15, high: float = 0.45) -> np.ndarray:
    """Humedad volumétrica (m³/m³) de un balance de cubo: se llena con lluvia y se seca exponencialmente."""
    s = np.empty(len(rain))
    level = 0.5
    for i, p in enumerate(rain):
        level = level * 0.96 + (1 - level) * min(p / 60.0, 1.0)
        s[i] = level
    return low + (high - low) * s


def generate(seed: int = 2027) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    df = pd.read_csv(SOURCE_CSV)
    out = []
    for code, g in df.groupby("embalse", sort=True):
        g = g.sort_values("fecha")
        rain = rain_from_inflow(g["caudal_entrada_m3s"].to_numpy(dtype=float), rng)
        out.append(
            pd.DataFrame(
                {
                    "embalse": code,
                    "fecha": g["fecha"].to_numpy(),
                    "precipitacion_mm": np.round(rain, 2),
                    "humedad_suelo_m3m3": np.round(soil_from_rain(rain), 4),
                }
            )
        )
    return pd.concat(out, ignore_index=True)


def main() -> None:
    ap = argparse.ArgumentParser(description="Genera lluvia y humedad del suelo SINTÉTICAS coherentes.")
    ap.add_argument("--seed", type=int, default=2027)
    ap.add_argument("--out", type=Path, default=OUT_CSV)
    args = ap.parse_args()
    df = generate(args.seed)
    df.to_csv(args.out, index=False, encoding="utf-8")
    print(f"{len(df)} filas SINTETICAS -> {args.out}")


if __name__ == "__main__":
    main()
