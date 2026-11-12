"""Modelos de predicción con una interfaz común.

Todos predicen el CAMBIO de volumen ΔV para cada día 1..90 desde la fecha de origen, con tres
cuantiles (10 %, 50 %, 90 %): la mediana es la predicción y [p10, p90] la banda de incertidumbre (80 %).
Salida de predict(): arreglo [n_orígenes, 90, 3] en hm³.

- PersistenceModel: "el embalse se queda como está" (línea base ingenua).
- SeasonalModel: "cambia como cambió en promedio en esta época del año" (línea base estacional).
- XGBoostModel: un XGBoost de regresión por cuantiles para cada paso de 5 días (estrategia directa).
- LSTMModel: red LSTM (PyTorch) con ventana de 90 días que predice toda la trayectoria de una vez.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from hidrica_ml.data import ReservoirSeries
from hidrica_ml.features import FEATURES, MAX_HORIZON, SEQ_FEATURES, STEPS, base_frame, make_features, training_matrix

QUANTILES = (0.1, 0.5, 0.9)


def steps_to_daily(pred_steps: np.ndarray, steps: tuple[int, ...] = STEPS) -> np.ndarray:
    """[n, len(steps), 3] → [n, 90, 3] interpolando linealmente con ΔV(0) = 0."""
    n = pred_steps.shape[0]
    xs = np.array((0, *steps), dtype=float)
    days = np.arange(1, MAX_HORIZON + 1, dtype=float)
    out = np.empty((n, MAX_HORIZON, 3))
    for i in range(n):
        for q in range(3):
            out[i, :, q] = np.interp(days, xs, np.concatenate(([0.0], pred_steps[i, :, q])))
    return np.sort(out, axis=2)  # garantiza p10 ≤ p50 ≤ p90


def calibration_factors(pred: np.ndarray, actual: np.ndarray, target: float = 0.8) -> np.ndarray:
    """Factor k por horizonte para ensanchar [p10, p90] alrededor de la mediana hasta cubrir `target`.

    Calibración conformal simple sobre datos que el modelo no usó para aprender (validación cronológica).
    pred: [n, H, 3]; actual: [n, H]. Devuelve k: [H] (k > 1 ensancha; k < 1 estrecha).
    """
    grid = np.linspace(0.5, 6.0, 111)
    k = np.ones(pred.shape[1])
    for h in range(pred.shape[1]):
        lo_w = pred[:, h, 1] - pred[:, h, 0]
        hi_w = pred[:, h, 2] - pred[:, h, 1]
        y, mid = actual[:, h], pred[:, h, 1]
        ok = ~np.isnan(y)
        if ok.sum() < 20:
            continue
        k[h] = grid[-1]
        for g in grid:
            cov = np.mean((y[ok] >= mid[ok] - g * lo_w[ok]) & (y[ok] <= mid[ok] + g * hi_w[ok]))
            if cov >= target:
                k[h] = g
                break
    return k


def apply_calibration(pred: np.ndarray, k: np.ndarray) -> np.ndarray:
    out = pred.copy()
    out[:, :, 0] = pred[:, :, 1] - k[None, :] * (pred[:, :, 1] - pred[:, :, 0])
    out[:, :, 2] = pred[:, :, 1] + k[None, :] * (pred[:, :, 2] - pred[:, :, 1])
    return out


class Forecaster(ABC):
    kind: str

    @abstractmethod
    def fit(self, s: ReservoirSeries, end: pd.Timestamp | None = None) -> Forecaster: ...

    @abstractmethod
    def predict(self, s: ReservoirSeries, origins: pd.DatetimeIndex) -> np.ndarray: ...

    def params(self) -> dict[str, Any]:
        return {}

    def importance(self) -> dict[str, float] | None:
        return None

    def save(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        (path / "params.json").write_text(json.dumps({"kind": self.kind, **self._state()}), encoding="utf-8")

    def _state(self) -> dict[str, Any]:
        return {}


# ------------------------------------------------------------------ líneas base


def _empirical_targets(s: ReservoirSeries, end: pd.Timestamp | None) -> pd.DataFrame:
    _, Y = training_matrix(s, end, steps=tuple(range(1, MAX_HORIZON + 1)))
    return Y


class PersistenceModel(Forecaster):
    """ΔV = 0; la banda usa los cuantiles históricos de ΔV de cada horizonte."""

    kind = "persistencia"

    def fit(self, s, end=None):
        Y = _empirical_targets(s, end)
        self.band = np.stack([Y.quantile(q).to_numpy() for q in (0.1, 0.9)], axis=1)  # [90, 2]
        return self

    def predict(self, s, origins):
        out = np.zeros((len(origins), MAX_HORIZON, 3))
        out[:, :, 0] = self.band[:, 0]
        out[:, :, 2] = self.band[:, 1]
        return np.sort(out, axis=2)

    def params(self):
        return {"descripcion": "El volumen se mantiene igual que el día de origen"}

    def save(self, path):
        super().save(path)
        np.save(path / "banda.npy", self.band)

    @classmethod
    def load(cls, path: Path) -> PersistenceModel:
        obj = cls()
        obj.band = np.load(path / "banda.npy")
        return obj


class SeasonalModel(Forecaster):
    """Cuantiles de ΔV de las fechas de entrenamiento a ±15 días del mismo día del año (mediana = media)."""

    kind = "estacional"
    WINDOW = 15

    def fit(self, s, end=None):
        Y = _empirical_targets(s, end)
        doy = Y.index.dayofyear.to_numpy()
        values = Y.to_numpy()
        self.table = np.zeros((366, MAX_HORIZON, 3))
        for d in range(1, 367):
            dist = np.minimum(np.abs(doy - d), 366 - np.abs(doy - d))
            sel = values[dist <= self.WINDOW]
            sel = sel if len(sel) else values
            self.table[d - 1, :, 0] = np.quantile(sel, 0.1, axis=0)
            self.table[d - 1, :, 1] = sel.mean(axis=0)
            self.table[d - 1, :, 2] = np.quantile(sel, 0.9, axis=0)
        return self

    def predict(self, s, origins):
        return np.sort(self.table[origins.dayofyear.to_numpy() - 1], axis=2)

    def params(self):
        return {"ventana_dias": self.WINDOW, "descripcion": "Cambio medio histórico para la misma época del año"}

    def save(self, path):
        super().save(path)
        np.save(path / "tabla.npy", self.table)

    @classmethod
    def load(cls, path: Path) -> SeasonalModel:
        obj = cls()
        obj.table = np.load(path / "tabla.npy")
        return obj


# ------------------------------------------------------------------ XGBoost


class XGBoostModel(Forecaster):
    kind = "xgboost"
    CV_BLOCKS = 3

    def __init__(self, n_estimators: int = 300, max_depth: int = 4, learning_rate: float = 0.05, seed: int = 42):
        self.hp = {
            "n_estimators": n_estimators,
            "max_depth": max_depth,
            "learning_rate": learning_rate,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "min_child_weight": 5,
            "seed": seed,
        }
        self.models: dict[int, Any] = {}
        self.k = np.ones(len(STEPS))

    def params(self):
        return {
            **self.hp,
            "pasos": list(STEPS),
            "cuantiles": list(QUANTILES),
            "estrategia": "directa",
            "calibracion": "conformal con validación cruzada en 3 bloques de años",
            "features": FEATURES,
        }

    def _new(self):
        import xgboost as xgb

        return xgb.XGBRegressor(
            objective="reg:quantileerror",
            quantile_alpha=np.array(QUANTILES),
            tree_method="hist",
            n_jobs=4,
            random_state=self.hp["seed"],
            **{k: v for k, v in self.hp.items() if k != "seed"},
        )

    def _fit_models(self, X: pd.DataFrame, Y: pd.DataFrame) -> dict[int, Any]:
        models = {}
        for h in STEPS:
            m = self._new()
            m.fit(X.to_numpy(), Y[h].to_numpy())
            models[h] = m
        return models

    def _predict_steps(self, models: dict[int, Any], X: pd.DataFrame) -> np.ndarray:
        """[n, pasos, 3] con los cuantiles ordenados."""
        return np.sort(np.stack([models[h].predict(X.to_numpy()) for h in STEPS], axis=1), axis=2)

    def fit(self, s, end=None):
        X, Y = training_matrix(s, end)
        if len(X) < 365:
            raise ValueError(f"Datos insuficientes para entrenar {s.code}: {len(X)} orígenes (mínimo 365).")
        # 1) Calibración por validación cruzada en bloques de años: cada bloque se predice con un modelo
        #    entrenado sin él (dejando 90 días de separación para que no se solapen los objetivos).
        #    Usar varios años captura la diferencia entre años secos y húmedos.
        years = np.array(sorted(set(X.index.year)))
        blocks = [b for b in np.array_split(years, self.CV_BLOCKS) if len(b)]
        oof_pred, oof_true = [], []
        gap = pd.Timedelta(days=max(STEPS))
        for b in blocks:
            test = np.isin(X.index.year, b)
            start, stop = X.index[test].min(), X.index[test].max()
            train = (X.index < start - gap) | (X.index > stop + gap)
            if train.sum() < 365 or test.sum() < 60:
                continue
            tmp = self._fit_models(X[train], Y[train])
            oof_pred.append(self._predict_steps(tmp, X[test]))
            oof_true.append(Y[test].to_numpy())
        if oof_pred:
            self.k = calibration_factors(np.concatenate(oof_pred), np.concatenate(oof_true))
        # 2) Modelo final con todos los datos
        self.models = self._fit_models(X, Y)
        return self

    def predict(self, s, origins):
        X = make_features(s).reindex(origins)
        if X.isna().any().any():
            raise ValueError("Faltan datos para calcular las variables en alguna fecha de origen.")
        return steps_to_daily(apply_calibration(self._predict_steps(self.models, X), self.k))

    def importance(self):
        total: dict[str, float] = dict.fromkeys(FEATURES, 0.0)
        for m in self.models.values():
            scores = m.get_booster().get_score(importance_type="gain")
            for k, v in scores.items():
                name = FEATURES[int(k[1:])] if k.startswith("f") and k[1:].isdigit() else k
                total[name] = total.get(name, 0.0) + v
        norm = sum(total.values()) or 1.0
        return dict(sorted(((k, v / norm) for k, v in total.items()), key=lambda kv: -kv[1]))

    def save(self, path):
        super().save(path)
        for h, m in self.models.items():
            m.save_model(path / f"paso_{h:02d}.json")

    def _state(self):
        return {"hp": self.hp, "k": self.k.tolist()}

    @classmethod
    def load(cls, path: Path) -> XGBoostModel:
        state = json.loads((path / "params.json").read_text(encoding="utf-8"))
        hp = state["hp"]
        obj = cls(hp["n_estimators"], hp["max_depth"], hp["learning_rate"], hp["seed"])
        obj.k = np.array(state.get("k", [1.0] * len(STEPS)))
        for h in STEPS:
            m = obj._new()
            m.load_model(path / f"paso_{h:02d}.json")
            obj.models[h] = m
        return obj


# ------------------------------------------------------------------ LSTM


class LSTMModel(Forecaster):
    kind = "lstm"

    def __init__(
        self, window: int = 90, hidden: int = 64, epochs: int = 25, lr: float = 1e-3, batch: int = 64, seed: int = 42
    ):
        self.hp = {"window": window, "hidden": hidden, "epochs": epochs, "lr": lr, "batch": batch, "seed": seed}
        self.net = None
        self.mean: np.ndarray | None = None
        self.std: np.ndarray | None = None
        self.scale = 1.0
        self.history: list[float] = []
        self.k = np.ones(MAX_HORIZON)

    def params(self):
        return {
            **self.hp,
            "horizonte": MAX_HORIZON,
            "cuantiles": list(QUANTILES),
            "entradas": SEQ_FEATURES,
            "salida": "trayectoria de 90 días",
        }

    def _frame(self, s: ReservoirSeries) -> pd.DataFrame:
        df = base_frame(s)[SEQ_FEATURES].copy()
        df[["precip_mm", "soil_moisture"]] = df[["precip_mm", "soil_moisture"]].fillna(0.0)
        return df

    def _build(self):
        import torch
        from torch import nn

        torch.manual_seed(self.hp["seed"])

        class Net(nn.Module):
            def __init__(self, n_in: int, hidden: int):
                super().__init__()
                self.lstm = nn.LSTM(n_in, hidden, batch_first=True)
                self.head = nn.Sequential(nn.Linear(hidden, hidden), nn.ReLU(), nn.Linear(hidden, MAX_HORIZON * 3))

            def forward(self, x):
                _, (h, _) = self.lstm(x)
                return self.head(h[-1]).view(-1, MAX_HORIZON, 3)

        return Net(len(SEQ_FEATURES), self.hp["hidden"])

    def _windows(self, values: np.ndarray, ends: np.ndarray) -> np.ndarray:
        w = self.hp["window"]
        return np.stack([values[e - w + 1 : e + 1] for e in ends])

    def fit(self, s, end=None):
        import torch

        torch.set_num_threads(4)
        df = self._frame(s)
        v = s.df["volume_hm3"].to_numpy()
        w = self.hp["window"]
        self.scale = float(s.useful_capacity)
        vals = df.to_numpy()
        n = len(df)
        last = n - 1 if end is None else int(np.searchsorted(df.index, end, side="right")) - 1
        ends = []
        for e in range(w - 1, last - MAX_HORIZON + 1):
            if np.isnan(vals[e - w + 1 : e + 1]).any() or np.isnan(v[e : e + MAX_HORIZON + 1]).any():
                continue
            ends.append(e)
        if len(ends) < 365:
            raise ValueError(f"Datos insuficientes para entrenar la LSTM de {s.code}: {len(ends)} ventanas.")
        ends = np.array(ends)
        train_vals = vals[: last + 1]
        self.mean = np.nanmean(train_vals, axis=0)
        self.std = np.nanstd(train_vals, axis=0) + 1e-6
        X = (self._windows(vals, ends) - self.mean) / self.std
        Y = np.stack([(v[e + 1 : e + MAX_HORIZON + 1] - v[e]) / self.scale for e in ends])

        cut = int(len(X) * 0.85)  # validación = último 15 % (cronológico)
        Xt, Yt = torch.tensor(X[:cut], dtype=torch.float32), torch.tensor(Y[:cut], dtype=torch.float32)
        Xv, Yv = torch.tensor(X[cut:], dtype=torch.float32), torch.tensor(Y[cut:], dtype=torch.float32)
        q = torch.tensor(QUANTILES, dtype=torch.float32)

        def pinball(pred, y):
            err = y.unsqueeze(-1) - pred
            return torch.mean(torch.maximum(q * err, (q - 1) * err))

        self.net = self._build()
        opt = torch.optim.Adam(self.net.parameters(), lr=self.hp["lr"])
        gen = torch.Generator().manual_seed(self.hp["seed"])
        best, best_state, patience = float("inf"), None, 0
        self.history = []
        for _ in range(self.hp["epochs"]):
            self.net.train()
            perm = torch.randperm(len(Xt), generator=gen)
            for i in range(0, len(Xt), self.hp["batch"]):
                idx = perm[i : i + self.hp["batch"]]
                opt.zero_grad()
                loss = pinball(self.net(Xt[idx]), Yt[idx])
                loss.backward()
                opt.step()
            self.net.eval()
            with torch.no_grad():
                val = float(pinball(self.net(Xv), Yv))
            self.history.append(round(val, 6))
            if val < best - 1e-6:
                best, patience = val, 0
                best_state = {k: t.clone() for k, t in self.net.state_dict().items()}
            else:
                patience += 1
                if patience >= 4:  # parada temprana
                    break
        if best_state is not None:
            self.net.load_state_dict(best_state)
        # Calibración con la validación cronológica (datos que la red no usó para aprender)
        self.net.eval()
        with torch.no_grad():
            val_pred = np.sort(self.net(Xv).numpy(), axis=2)
        self.k = calibration_factors(val_pred, Yv.numpy())
        return self

    def predict(self, s, origins):
        import torch

        df = self._frame(s)
        vals = df.to_numpy()
        ends = df.index.get_indexer(origins)
        if (ends < self.hp["window"] - 1).any() or (ends < 0).any():
            raise ValueError("No hay 90 días de historia antes de alguna fecha de origen.")
        X = (self._windows(vals, ends) - self.mean) / self.std
        if np.isnan(X).any():
            raise ValueError("Faltan datos en la ventana de 90 días de alguna fecha de origen.")
        self.net.eval()
        with torch.no_grad():
            out = np.sort(self.net(torch.tensor(X, dtype=torch.float32)).numpy(), axis=2) * self.scale
        return np.sort(apply_calibration(out, self.k), axis=2)

    def save(self, path):
        import torch

        super().save(path)
        torch.save(self.net.state_dict(), path / "lstm.pt")

    def _state(self):
        return {
            "hp": self.hp,
            "mean": self.mean.tolist(),
            "std": self.std.tolist(),
            "scale": self.scale,
            "k": self.k.tolist(),
            "historial_validacion": self.history,
        }

    @classmethod
    def load(cls, path: Path) -> LSTMModel:
        import torch

        state = json.loads((path / "params.json").read_text(encoding="utf-8"))
        obj = cls(**state["hp"])
        obj.mean, obj.std, obj.scale = np.array(state["mean"]), np.array(state["std"]), state["scale"]
        obj.history = state.get("historial_validacion", [])
        obj.k = np.array(state.get("k", [1.0] * MAX_HORIZON))
        obj.net = obj._build()
        obj.net.load_state_dict(torch.load(path / "lstm.pt", weights_only=True))
        return obj


MODELS: dict[str, type[Forecaster]] = {
    "persistencia": PersistenceModel,
    "estacional": SeasonalModel,
    "xgboost": XGBoostModel,
    "lstm": LSTMModel,
}


def load_model(path: Path) -> Forecaster:
    kind = json.loads((path / "params.json").read_text(encoding="utf-8"))["kind"]
    cls = MODELS[kind]
    return cls.load(path)  # type: ignore[attr-defined]
