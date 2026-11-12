"""Generador del dataset SINTÉTICO de movimiento diario de los embalses.

⚠️ Estos datos NO son mediciones reales de MINAGUAS. Sirven para desarrollar y probar
el sistema mientras llegan los históricos oficiales (PENDIENTES P-03, P-04, P-05).

Modelo (simplificado, físicamente coherente):
  - Curva cota–volumen potencial: V(h) = Vn · ((h − h_fondo) / (h_normal − h_fondo))^p
    y área = dV/dh (1 hm³/m = 1 km²).
  - Aporte diario: estacionalidad bimodal típica del Zulia (lluvias en abr–may y sep–nov),
    variabilidad interanual (ciclos secos/húmedos), ruido autocorrelacionado y crecidas.
  - Balance: ΔV = (entrada − salida − gasto ecológico)·0,0864 − evaporación − alivio.
  - Alivio cuando el volumen supera el nivel normal; racionamiento cerca del volumen muerto.
  - La evaporación y el alivio NO se miden en sitio: quedan solo en el archivo "verdad"
    para validar después los cálculos operativos (M12) y los modelos (M6).

Uso (desde ml/):
    uv run python -m hidrica_ml.synthetic --seed 2026 --end 2026-10-31
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from hidrica_ml.schema import COLUMN_NAMES, M3S_TO_HM3_PER_DAY

ML_DIR = Path(__file__).resolve().parents[2]
CONFIG_PATH = ML_DIR / "config" / "embalses.json"
DEFAULT_OUT = ML_DIR / "data" / "synthetic"
GENERATOR_VERSION = "1.0.0"


@dataclass(frozen=True)
class Reservoir:
    code: str
    name: str
    start: date
    h_normal: float
    h_dead: float
    v_normal: float
    h_bed: float
    exponent: float
    inflow_mean: float
    extraction_mean: float
    eco_flow: float


@dataclass(frozen=True)
class Curve:
    """Curva cota–área–volumen sintética (potencial)."""

    h_bed: float
    h_normal: float
    v_normal: float
    p: float

    def volume(self, h: np.ndarray | float) -> np.ndarray | float:
        rel = np.clip((np.asarray(h) - self.h_bed) / (self.h_normal - self.h_bed), 0, None)
        return self.v_normal * rel**self.p

    def level(self, v: np.ndarray | float) -> np.ndarray | float:
        rel = np.clip(np.asarray(v) / self.v_normal, 0, None)
        return self.h_bed + (self.h_normal - self.h_bed) * rel ** (1 / self.p)

    def area(self, h: np.ndarray | float) -> np.ndarray | float:
        """Área del espejo de agua en km² (= dV/dh en hm³/m)."""
        rel = np.clip((np.asarray(h) - self.h_bed) / (self.h_normal - self.h_bed), 0, None)
        return self.v_normal * self.p / (self.h_normal - self.h_bed) * rel ** (self.p - 1)


def load_reservoirs(path: Path = CONFIG_PATH) -> list[Reservoir]:
    data = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for e in data["embalses"]:
        s = e["sintetico"]
        out.append(
            Reservoir(
                code=e["codigo"],
                name=e["nombre"],
                start=date.fromisoformat(e["inicio_registros"]),
                h_normal=e["cota_normal"],
                h_dead=e["cota_volumen_muerto"],
                v_normal=s["volumen_normal_hm3"],
                h_bed=s["cota_fondo"],
                exponent=s["exponente_curva"],
                inflow_mean=s["caudal_entrada_medio_m3s"],
                extraction_mean=s["extraccion_media_m3s"],
                eco_flow=s["gasto_ecologico_m3s"],
            )
        )
    return out


def curve_for(r: Reservoir) -> Curve:
    return Curve(h_bed=r.h_bed, h_normal=r.h_normal, v_normal=r.v_normal, p=r.exponent)


def _seasonality(doy: np.ndarray) -> np.ndarray:
    """Régimen bimodal: picos en mayo y octubre, secas dic–mar y 'veranillo' jun–ago."""

    def bump(center: float, width: float) -> np.ndarray:
        d = np.minimum(np.abs(doy - center), 365.25 - np.abs(doy - center))
        return np.exp(-0.5 * (d / width) ** 2)

    s = 0.25 + 0.9 * bump(130, 22) + 1.7 * bump(295, 32)
    return s / s.mean()


def simulate_inflow(r: Reservoir, dates: pd.DatetimeIndex, rng: np.random.Generator) -> np.ndarray:
    n = len(dates)
    doy = dates.day_of_year.to_numpy().astype(float)
    t_years = (dates - pd.Timestamp("2005-01-01")).days.to_numpy() / 365.25

    season = _seasonality(doy)
    # Variabilidad interanual: ciclo ~4,3 años + componente lenta aleatoria (años secos/húmedos)
    phase = rng.uniform(0, 2 * np.pi)
    yearly = np.repeat(rng.normal(0, 0.28, int(t_years.max()) + 2), 366)[:n]
    interannual = np.clip(1 + 0.42 * np.sin(2 * np.pi * t_years / 4.3 + phase) + yearly, 0.25, None)

    # Ruido log-normal autocorrelado AR(1)
    eps = np.empty(n)
    eps[0] = 0.0
    shocks = rng.normal(0, 0.35, n)
    for i in range(1, n):
        eps[i] = 0.85 * eps[i - 1] + shocks[i]
    noise = np.exp(eps - eps.var() / 2)

    # Crecidas: eventos más probables en temporada de lluvias, con recesión exponencial
    storm_prob = 0.025 * season
    storms = (rng.random(n) < storm_prob) * rng.gamma(2.0, 2.5, n)
    flood = np.zeros(n)
    for i in range(n):
        flood[i] = (flood[i - 1] * 0.7 if i else 0.0) + storms[i]

    q = season * interannual * noise + flood
    return r.inflow_mean * q / q.mean()


def simulate_reservoir(r: Reservoir, end: date, rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Devuelve (registro con columnas de la plantilla, verdad con variables ocultas)."""
    curve = curve_for(r)
    dates = pd.date_range(r.start, end, freq="D")
    n = len(dates)

    inflow = simulate_inflow(r, dates, rng)
    v_dead = float(curve.volume(r.h_dead))
    useful_cap = r.v_normal - v_dead
    max_spill_m3s = 200.0  # capacidad nominal de compuertas/aliviadero (sintética)

    vol = np.empty(n)
    out_q = np.empty(n)
    eco_q = np.empty(n)
    spill_hm3 = np.empty(n)
    evap_hm3 = np.empty(n)
    rationing = np.zeros(n, dtype=bool)

    v = r.v_normal * 0.75
    doy = dates.day_of_year.to_numpy()
    evap_mm = 4.5 + 1.5 * np.cos(2 * np.pi * (doy - 60) / 365.25)  # mayor evaporación en temporada seca

    for i in range(n):
        useful_frac = (v - v_dead) / useful_cap
        ext = r.extraction_mean * (1 + rng.normal(0, 0.05))
        eco = r.eco_flow * (1 + rng.normal(0, 0.03))
        if useful_frac < 0.12:  # racionamiento progresivo cerca del volumen muerto
            factor = max(useful_frac, 0.0) / 0.12
            ext *= 0.35 + 0.65 * factor
            eco *= factor
            rationing[i] = True

        area = float(curve.area(curve.level(v)))
        evap = area * evap_mm[i] / 1000  # km² · mm → hm³
        v_next = v + (inflow[i] - ext - eco) * M3S_TO_HM3_PER_DAY - evap
        spill = 0.0
        if v_next > r.v_normal:
            spill = min((v_next - r.v_normal) * 0.6, max_spill_m3s * M3S_TO_HM3_PER_DAY)
            v_next -= spill
        v_next = max(v_next, v_dead * 0.98)  # física: la toma no extrae por debajo del muerto

        vol[i], out_q[i], eco_q[i], spill_hm3[i], evap_hm3[i] = v_next, ext, eco, spill, evap
        v = v_next

    level = curve.level(vol)
    gates = np.clip(spill_hm3 / M3S_TO_HM3_PER_DAY / max_spill_m3s * 100, 0, 100)
    obs = np.where(spill_hm3 > 0, "Alivio por aliviadero", np.where(rationing, "Racionamiento de extracción", ""))

    record = pd.DataFrame(
        {
            "embalse": r.code,
            "fecha": dates.strftime("%Y-%m-%d"),
            "hora": "08:00",
            "cota_msnm": np.round(level, 2),
            "volumen_hm3": np.round(vol, 3),
            "caudal_entrada_m3s": np.round(inflow, 3),
            "caudal_salida_m3s": np.round(out_q, 3),
            "gasto_ecologico_m3s": np.round(eco_q, 3),
            "apertura_compuertas_pct": np.round(gates, 1),
            "captacion_m3s": np.round(out_q, 3),
            "observaciones": obs,
        }
    )[list(COLUMN_NAMES)]
    truth = pd.DataFrame(
        {
            "embalse": r.code,
            "fecha": record["fecha"],
            "volumen_exacto_hm3": vol,
            "alivio_hm3": spill_hm3,
            "evaporacion_hm3": evap_hm3,
            "area_km2": curve.area(level),
        }
    )
    return record, truth


def curve_table(r: Reservoir, step: float = 0.10) -> pd.DataFrame:
    curve = curve_for(r)
    top = r.h_normal + 3.0
    h = np.round(np.arange(r.h_bed, top + step / 2, step), 2)
    return pd.DataFrame(
        {
            "embalse": r.code,
            "cota_msnm": h,
            "area_km2": np.round(curve.area(h), 4),
            "volumen_hm3": np.round(curve.volume(h), 4),
        }
    )


def generate(seed: int = 2026, end: date = date(2026, 10, 31)) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    records, truths = [], []
    for r in load_reservoirs():
        rec, tru = simulate_reservoir(r, end, rng)
        records.append(rec)
        truths.append(tru)
    return pd.concat(records, ignore_index=True), pd.concat(truths, ignore_index=True)


def write_dataset(out_dir: Path, seed: int, end: date) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    record, truth = generate(seed, end)
    record.to_csv(out_dir / "movimiento_diario_sintetico.csv", index=False, encoding="utf-8")
    truth.round(4).to_csv(out_dir / "verdad_sintetica.csv", index=False, encoding="utf-8")
    for r in load_reservoirs():
        curve_table(r).to_csv(out_dir / f"curva_cota_volumen_{r.code.lower()}_sintetica.csv", index=False)
    meta = {
        "SINTETICO": True,
        "advertencia": "Datos generados artificialmente. No son mediciones de MINAGUAS.",
        "generador": "ml/src/synthetic.py",
        "version_generador": GENERATOR_VERSION,
        "semilla": seed,
        "fecha_fin": end.isoformat(),
        "filas": int(len(record)),
        "embalses": {
            code: {"desde": g["fecha"].min(), "hasta": g["fecha"].max(), "filas": int(len(g))}
            for code, g in record.groupby("embalse")
        },
    }
    (out_dir / "metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


def main() -> None:
    ap = argparse.ArgumentParser(description="Genera el dataset SINTÉTICO de embalses.")
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--end", type=date.fromisoformat, default=date(2026, 10, 31))
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()
    meta = write_dataset(args.out, args.seed, args.end)
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
