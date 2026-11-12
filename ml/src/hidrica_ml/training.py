"""Entrenamiento completo de un embalse: backtesting walk-forward + modelo final + artefactos.

Lo usan la CLI (`python -m hidrica_ml.training`) y la API del backend (reentrenamiento bajo demanda).
"""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

from hidrica_ml import __version__
from hidrica_ml.backtest import score, summarize, walk_forward
from hidrica_ml.data import ML_DIR, ReservoirSeries, load_synthetic
from hidrica_ml.features import FEATURE_LABELS
from hidrica_ml.models import MODELS, Forecaster, LSTMModel

DEFAULT_KINDS = ("persistencia", "estacional", "xgboost", "lstm")
MODELS_DIR = ML_DIR / "models"
Progress = Callable[[str], None]


@dataclass
class TrainedModel:
    code: str
    kind: str
    artifact_dir: Path
    params: dict
    metrics: list[dict]  # filas de summarize() de este modelo
    score: float  # MAE medio de volumen a 30/60/90 días (menor es mejor)
    data_from: str
    data_to: str
    n_days: int
    test_years: list[int]
    importance: dict | None
    seconds: float


def default_test_years(s: ReservoirSeries, n: int = 4) -> list[int]:
    """Últimos n años con al menos ~6 meses de orígenes evaluables (origen + 90 días ≤ último dato)."""
    last = s.df["volume_hm3"].last_valid_index()
    last_year = (last - pd.Timedelta(days=90 + 180)).year
    return list(range(last_year - n + 1, last_year + 1))


def factory_for(kind: str, fast: bool = False) -> Callable[[], Forecaster]:
    if kind == "lstm":
        return lambda: LSTMModel(epochs=5 if fast else 25)
    return MODELS[kind]


def train_reservoir(
    s: ReservoirSeries,
    kinds: tuple[str, ...] = DEFAULT_KINDS,
    test_years: list[int] | None = None,
    out_dir: Path = MODELS_DIR,
    version_tag: str | None = None,
    origin_every: int = 7,
    fast: bool = False,
    progress: Progress | None = None,
) -> tuple[list[TrainedModel], pd.DataFrame]:
    """Backtesting de cada modelo y entrenamiento final con todos los datos. Devuelve modelos y resultados."""
    test_years = test_years or default_test_years(s)
    version_tag = version_tag or datetime.now().strftime("%Y%m%d-%H%M%S")
    valid = s.df["volume_hm3"].dropna()
    trained: list[TrainedModel] = []
    all_results = []
    for kind in kinds:
        t0 = time.perf_counter()
        factory = factory_for(kind, fast)
        results = walk_forward(s, factory, test_years, origin_every, progress)
        summary = summarize(results)
        final = factory().fit(s)  # modelo de producción: todos los datos disponibles
        artifact = out_dir / s.code / kind / version_tag
        final.save(artifact)
        results.to_csv(artifact / "backtest.csv", index=False)
        imp = final.importance()
        tm = TrainedModel(
            code=s.code,
            kind=kind,
            artifact_dir=artifact,
            params={**final.params(), "version_hidrica_ml": __version__},
            metrics=summary.to_dict("records"),
            score=score(summary, kind),
            data_from=valid.index.min().date().isoformat(),
            data_to=valid.index.max().date().isoformat(),
            n_days=int(len(valid)),
            test_years=test_years,
            importance=imp,
            seconds=round(time.perf_counter() - t0, 1),
        )
        manifest = {k: (str(v) if isinstance(v, Path) else v) for k, v in tm.__dict__.items()}
        manifest["fuente_datos"] = s.meta.get("fuente", "desconocida")
        (artifact / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        trained.append(tm)
        all_results.append(results)
        if progress:
            progress(f"{s.code} · {kind}: MAE medio {tm.score:.2f} hm³ ({tm.seconds:.0f} s)")
    return trained, pd.concat(all_results, ignore_index=True)


def importance_labels(imp: dict | None) -> list[dict]:
    return [
        {"variable": k, "descripcion": FEATURE_LABELS.get(k, k), "peso": round(v, 4)} for k, v in (imp or {}).items()
    ]


def main() -> None:
    ap = argparse.ArgumentParser(description="Entrena y evalúa los modelos con el dataset SINTÉTICO.")
    ap.add_argument("--reservoirs", nargs="*", default=["TULE", "MANUELOTE", "TRES_RIOS"])
    ap.add_argument("--kinds", nargs="*", default=list(DEFAULT_KINDS))
    ap.add_argument("--fast", action="store_true", help="LSTM con 5 épocas (para pruebas)")
    args = ap.parse_args()
    for code in args.reservoirs:
        s = load_synthetic(code)
        trained, _ = train_reservoir(
            s, tuple(args.kinds), fast=args.fast, progress=lambda m: print("  ", m, flush=True)
        )
        best = min(trained, key=lambda t: t.score)
        print(f"{code}: mejor modelo = {best.kind} (MAE medio {best.score:.2f} hm³)")


if __name__ == "__main__":
    main()
