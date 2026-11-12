"""Puente entre la base de datos y hidrica_ml (M6): series, entrenamiento, registro y predicción."""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.measurement import DailyMeasurement
from app.models.ml import MLModel
from app.models.reservoir import ElevationCurve, Reservoir
from app.models.satellite import SatelliteObservation

SAT_SOURCES = {
    "sintetico": {"precip_mm": "sintetico", "soil_moisture": "sintetico"},
    "real": {"precip_mm": "chirps", "soil_moisture": "era5_land_openmeteo"},
}
SAT_VARIABLES = {"precip_mm": "precipitacion_mm", "soil_moisture": "humedad_suelo_m3m3"}
THRESHOLD_LABELS = {
    "low_critical": "Nivel bajo crítico",
    "low_alert": "Nivel bajo de alerta",
    "high_alert": "Nivel alto de alerta",
    "spill_level": "Nivel de alivio / inundación",
    "dead_level": "Volumen muerto",
}


class MLDataError(ValueError):
    pass


def build_series(session: Session, code: str, settings: Settings):
    """ReservoirSeries de hidrica_ml a partir de PostgreSQL (mediciones + satélite + curva vigente)."""
    from hidrica_ml.data import Curve, ReservoirSeries, regularize

    r = session.get(Reservoir, code)
    if r is None:
        raise MLDataError(f"Embalse desconocido: {code}")
    curve = session.scalars(
        select(ElevationCurve)
        .where(ElevationCurve.reservoir_code == code)
        .order_by(ElevationCurve.valid_from.desc(), ElevationCurve.version.desc())
        .limit(1)
    ).first()
    if curve is None or len(curve.points) < 2:
        raise MLDataError(f"{r.name} no tiene curva cota–volumen: no se puede modelar el volumen.")
    rows = session.execute(
        select(
            DailyMeasurement.day,
            DailyMeasurement.volume_hm3,
            DailyMeasurement.level_m,
            DailyMeasurement.inflow_m3s,
            DailyMeasurement.outflow_m3s,
            DailyMeasurement.eco_flow_m3s,
        )
        .where(DailyMeasurement.reservoir_code == code)
        .order_by(DailyMeasurement.day)
    ).all()
    if len(rows) < 3 * 365:
        raise MLDataError(f"{r.name} tiene {len(rows)} días de mediciones; se necesitan al menos 3 años.")
    df = pd.DataFrame(
        rows, columns=["day", "volume_hm3", "level_m", "inflow_m3s", "outflow_m3s", "eco_flow_m3s"]
    ).set_index("day")
    c = Curve(np.array([p.elevation for p in curve.points]), np.array([p.volume_hm3 for p in curve.points]))
    missing_v = df["volume_hm3"].isna()
    df.loc[missing_v, "volume_hm3"] = c.volume_at(df.loc[missing_v, "level_m"].to_numpy())

    sources = SAT_SOURCES[settings.ml_satellite_source]
    for col, variable in SAT_VARIABLES.items():
        obs = session.execute(
            select(SatelliteObservation.day, SatelliteObservation.value).where(
                SatelliteObservation.reservoir_code == code,
                SatelliteObservation.variable == variable,
                SatelliteObservation.source == sources[col],
            )
        ).all()
        df[col] = pd.Series({d: v for d, v in obs}, dtype="float64").reindex(df.index)
    return ReservoirSeries(
        code=code,
        df=regularize(df),
        curve=c,
        normal_level=r.normal_level,
        dead_level=r.dead_level,
        meta={"fuente": f"hidrologia: base de datos · satelite: {settings.ml_satellite_source}"},
    )


# ------------------------------------------------------------------ registro


def latest_by_kind(session: Session, code: str) -> list[MLModel]:
    models = session.scalars(
        select(MLModel).where(MLModel.reservoir_code == code).order_by(MLModel.created_at.desc())
    ).all()
    seen: dict[str, MLModel] = {}
    for m in models:
        seen.setdefault(m.kind, m)
    return list(seen.values())


def active_model(session: Session, code: str) -> MLModel | None:
    """Modelo fijado por el Ingeniero o, si no hay, el de menor error entre los más recientes de cada tipo."""
    pinned = session.scalars(
        select(MLModel).where(MLModel.reservoir_code == code, MLModel.pinned.is_(True))
    ).first()
    if pinned:
        return pinned
    candidates = latest_by_kind(session, code)
    return min(candidates, key=lambda m: m.score) if candidates else None


def train_and_register(
    session: Session,
    settings: Settings,
    codes: list[str],
    kinds: tuple[str, ...],
    test_years: list[int] | None,
    user_id: int | None,
    progress: Callable[[float, str], None] | None = None,
    fast: bool = False,
) -> dict[str, Any]:
    from hidrica_ml.training import train_reservoir

    summary: dict[str, Any] = {}
    total = len(codes) * len(kinds)
    done = 0

    def tick(message: str) -> None:
        if progress:
            progress(min(done / max(total, 1), 0.99), message)

    for code in codes:
        s = build_series(session, code, settings)
        for kind in kinds:
            trained, _ = train_reservoir(
                s, (kind,), test_years, out_dir=Path(settings.ml_models_dir), fast=fast, progress=tick
            )
            t = trained[0]
            session.add(
                MLModel(
                    reservoir_code=code,
                    kind=t.kind,
                    version_tag=t.artifact_dir.name,
                    data_from=t.data_from,
                    data_to=t.data_to,
                    n_days=t.n_days,
                    data_source=s.meta["fuente"],
                    test_years=t.test_years,
                    params=_jsonable(t.params),
                    metrics=_jsonable(t.metrics),
                    importance=_jsonable(t.importance),
                    score=t.score,
                    artifact_dir=str(t.artifact_dir),
                    train_seconds=t.seconds,
                    created_by=user_id,
                )
            )
            session.commit()
            done += 1
            tick(f"{code} · {kind}: MAE medio {t.score:.2f} hm³")
        best = active_model(session, code)
        summary[code] = {
            "modelo_activo": best.kind if best else None,
            "mae_medio_hm3": round(best.score, 3) if best else None,
        }
    _forecaster_cache.clear()
    return summary


def _jsonable(value: Any) -> Any:
    """Convierte numpy/NaN a tipos JSON (NaN → None)."""
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(v) for v in value]
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


# ------------------------------------------------------------------ predicción

_forecaster_cache: dict[str, Any] = {}
_cache_lock = threading.Lock()


def load_forecaster(model: MLModel):
    from hidrica_ml.models import load_model

    with _cache_lock:
        if model.artifact_dir not in _forecaster_cache:
            path = Path(model.artifact_dir)
            if not path.exists():
                raise MLDataError(
                    "No se encuentran los archivos del modelo en el servidor. Reentrena el embalse."
                )
            _forecaster_cache[model.artifact_dir] = load_model(path)
        return _forecaster_cache[model.artifact_dir]


def forecast(session: Session, settings: Settings, code: str) -> dict[str, Any]:
    from hidrica_ml.forecast import make_forecast
    from hidrica_ml.training import importance_labels

    model = active_model(session, code)
    if model is None:
        raise MLDataError("Aún no hay modelos entrenados para este embalse.")
    s = build_series(session, code, settings)
    forecaster = load_forecaster(model)
    origin = _last_valid_origin(s, forecaster)
    r = session.get(Reservoir, code)
    th = {
        k: getattr(r.thresholds, k) if r.thresholds else None
        for k in ("low_critical", "low_alert", "high_alert", "spill_level")
    }
    th["dead_level"] = r.dead_level
    f = make_forecast(forecaster, s, origin, th, THRESHOLD_LABELS)
    return {
        "reservoir_code": code,
        "origin": origin.date().isoformat(),
        "model": {
            "id": model.id,
            "kind": model.kind,
            "version": model.version_tag,
            "pinned": model.pinned,
            "score_mae_hm3": round(model.score, 3),
            "data_source": model.data_source,
            "trained_at": model.created_at.isoformat(),
        },
        "days": f.days,
        "horizons": f.horizons,
        "probabilities": f.probabilities,
        "importance": importance_labels({i["feature"]: i["weight"] for i in f.importance}),
        "thresholds": {k: v for k, v in th.items() if v is not None},
        "normal_level": r.normal_level,
    }


def _last_valid_origin(s, forecaster) -> pd.Timestamp:
    """Último día con datos suficientes para predecir (se prueban hasta 30 días hacia atrás)."""
    last = s.df["volume_hm3"].last_valid_index()
    for back in range(0, 31):
        d = last - pd.Timedelta(days=back)
        try:
            forecaster.predict(s, pd.DatetimeIndex([d]))
            return d
        except ValueError:
            continue
    raise MLDataError("Faltan datos recientes (cota, caudales o lluvia) para calcular la predicción.")
