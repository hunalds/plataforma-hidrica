"""Métricas de error del backtesting (objetivo 4 de la tesis)."""

from __future__ import annotations

import numpy as np


def mae(y: np.ndarray, p: np.ndarray) -> float:
    return float(np.mean(np.abs(y - p)))


def rmse(y: np.ndarray, p: np.ndarray) -> float:
    return float(np.sqrt(np.mean((y - p) ** 2)))


def mape(y: np.ndarray, p: np.ndarray) -> float:
    """Error porcentual absoluto medio (%). Se excluyen valores reales ~0 para no dividir entre cero."""
    mask = np.abs(y) > 1e-6
    return float(np.mean(np.abs((y[mask] - p[mask]) / y[mask])) * 100) if mask.any() else float("nan")


def r2(y: np.ndarray, p: np.ndarray) -> float:
    ss_res = np.sum((y - p) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    return float(1 - ss_res / ss_tot) if ss_tot > 0 else float("nan")


def coverage(y: np.ndarray, lo: np.ndarray, hi: np.ndarray) -> float:
    """% de valores reales dentro de la banda [p10, p90] (ideal ≈ 80 %)."""
    return float(np.mean((y >= lo) & (y <= hi)) * 100)


def all_metrics(y: np.ndarray, p: np.ndarray, lo: np.ndarray | None = None, hi: np.ndarray | None = None) -> dict:
    out = {"MAE": mae(y, p), "RMSE": rmse(y, p), "MAPE": mape(y, p), "R2": r2(y, p), "n": int(len(y))}
    if lo is not None and hi is not None:
        out["cobertura_80"] = coverage(y, lo, hi)
    return out
