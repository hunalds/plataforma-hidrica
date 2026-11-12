"""Serie diaria de un embalse lista para modelar (independiente de la base de datos).

El backend la arma desde PostgreSQL; los notebooks y las pruebas, desde los CSV sintéticos.
Columnas (índice = fecha diaria continua):
    volume_hm3, level_m, inflow_m3s, outflow_m3s, eco_flow_m3s, precip_mm, soil_moisture
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

ML_DIR = Path(__file__).resolve().parents[2]
SYNTH_DIR = ML_DIR / "data" / "synthetic"

COLUMNS = ["volume_hm3", "level_m", "inflow_m3s", "outflow_m3s", "eco_flow_m3s", "precip_mm", "soil_moisture"]
MAX_FILL_DAYS = 3  # huecos cortos se rellenan; los largos quedan como NaN y esas fechas no se usan


@dataclass
class Curve:
    """Curva cota–volumen tabulada (interpolación lineal en ambos sentidos)."""

    elevation: np.ndarray
    volume: np.ndarray

    def volume_at(self, level: np.ndarray | float) -> np.ndarray:
        return np.interp(level, self.elevation, self.volume)

    def level_at(self, volume: np.ndarray | float) -> np.ndarray:
        return np.interp(volume, self.volume, self.elevation)


@dataclass
class ReservoirSeries:
    code: str
    df: pd.DataFrame
    curve: Curve
    normal_level: float
    dead_level: float
    meta: dict = field(default_factory=dict)

    @property
    def dead_volume(self) -> float:
        return float(self.curve.volume_at(self.dead_level))

    @property
    def normal_volume(self) -> float:
        return float(self.curve.volume_at(self.normal_level))

    @property
    def useful_capacity(self) -> float:
        return self.normal_volume - self.dead_volume


def regularize(df: pd.DataFrame) -> pd.DataFrame:
    """Índice diario continuo, columnas estándar y relleno solo de huecos cortos."""
    df = df.copy()
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    full = pd.date_range(df.index.min(), df.index.max(), freq="D")
    df = df.reindex(full)
    for c in COLUMNS:
        if c not in df:
            df[c] = np.nan
    df = df[COLUMNS].astype("float64")
    return df.interpolate(limit=MAX_FILL_DAYS, limit_area="inside")


def load_synthetic(code: str, synth_dir: Path = SYNTH_DIR) -> ReservoirSeries:
    """Serie SINTÉTICA desde los CSV de ml/data/synthetic (para notebooks y pruebas)."""
    mov = pd.read_csv(synth_dir / "movimiento_diario_sintetico.csv")
    mov = mov[mov["embalse"] == code].set_index("fecha")
    sat_path = synth_dir / "satelite_sintetico.csv"
    sat = pd.read_csv(sat_path) if sat_path.exists() else pd.DataFrame(columns=["embalse", "fecha"])
    sat = sat[sat["embalse"] == code].set_index("fecha")
    df = pd.DataFrame(
        {
            "volume_hm3": mov["volumen_hm3"],
            "level_m": mov["cota_msnm"],
            "inflow_m3s": mov["caudal_entrada_m3s"],
            "outflow_m3s": mov["caudal_salida_m3s"],
            "eco_flow_m3s": mov["gasto_ecologico_m3s"],
            "precip_mm": sat.get("precipitacion_mm"),
            "soil_moisture": sat.get("humedad_suelo_m3m3"),
        }
    )
    curve_df = pd.read_csv(synth_dir / f"curva_cota_volumen_{code.lower()}_sintetica.csv")
    config = json.loads((ML_DIR / "config" / "embalses.json").read_text(encoding="utf-8"))
    ref = next(e for e in config["embalses"] if e["codigo"] == code)
    return ReservoirSeries(
        code=code,
        df=regularize(df),
        curve=Curve(curve_df["cota_msnm"].to_numpy(), curve_df["volumen_hm3"].to_numpy()),
        normal_level=ref["cota_normal"],
        dead_level=ref["cota_volumen_muerto"],
        meta={"fuente": "SINTETICO"},
    )
