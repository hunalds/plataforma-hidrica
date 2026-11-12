"""Informe de backtesting (objetivo 4 de la tesis): ml/reports/backtesting.md con tablas y gráficas."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.reservoir import Reservoir
from app.services.ml_service import active_model, latest_by_kind

KIND_LABELS = {
    "persistencia": "Persistencia (base)",
    "estacional": "Estacional (base)",
    "xgboost": "XGBoost",
    "lstm": "LSTM",
}


def _fmt(v, n=2) -> str:
    return "—" if v is None or (isinstance(v, float) and pd.isna(v)) else f"{v:.{n}f}"


def _plot(code: str, name: str, models, out_dir: Path) -> str | None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    frames = []
    for m in models:
        path = Path(m.artifact_dir) / "backtest.csv"
        if path.exists():
            frames.append(pd.read_csv(path, parse_dates=["origen"]))
    if not frames:
        return None
    df = pd.concat(frames)
    fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
    for ax, h in zip(axes, (30, 90), strict=True):
        g = df[df["horizonte"] == h]
        real = g.drop_duplicates("origen").sort_values("origen")
        target_day = real["origen"] + pd.to_timedelta(h, unit="D")
        ax.plot(target_day, real["cota_real"], color="black", lw=2, label="Real")
        for kind, color in (("estacional", "#94a3b8"), ("xgboost", "#0369a1"), ("lstm", "#b45309")):
            k = g[g["modelo"] == kind].sort_values("origen")
            if len(k):
                td = k["origen"] + pd.to_timedelta(h, unit="D")
                ax.plot(td, k["cota_p50"], color=color, lw=1.4, label=KIND_LABELS[kind])
                if kind != "estacional":
                    ax.fill_between(td, k["cota_p10"], k["cota_p90"], color=color, alpha=0.12)
        ax.set_title(f"{name} · predicción a {h} días (cota, m.s.n.m.)")
        ax.grid(alpha=0.3)
        ax.legend(loc="lower left", fontsize=8)
    fig.tight_layout()
    file = out_dir / f"backtest_{code.lower()}.png"
    fig.savefig(file, dpi=110)
    plt.close(fig)
    return file.name


def write_report(session: Session, settings: Settings) -> Path:
    out_dir = Path(settings.ml_reports_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Informe de backtesting de los modelos de predicción",
        "",
        f"Generado: {datetime.now():%Y-%m-%d %H:%M} · Plataforma Hídrica Zulia · objetivo 4 de la tesis.",
        "",
        "> ⚠️ **Datos de desarrollo SINTÉTICOS.** La hidrología y (por defecto) la lluvia y la humedad del suelo",
        "> son sintéticas y coherentes entre sí (C-24). Estas métricas validan el **método**; las cifras finales de",
        "> la tesis se obtienen reentrenando con los históricos de MINAGUAS y las fuentes satelitales reales.",
        "",
        "## Método",
        "",
        "- **Validación con origen móvil (walk-forward):** para cada año de prueba se entrena con los datos hasta",
        "  el 31/12 del año anterior y se predice desde orígenes semanales dentro del año; nunca se usa información futura.",
        "- **Horizontes:** 30, 60 y 90 días. Se predice el cambio de volumen y se convierte a cota con la curva.",
        "- **Métricas:** MAE, RMSE, MAPE y R² del volumen (hm³), MAE de la cota (m) y cobertura de la banda p10–p90",
        "  (ideal ≈ 80 %).",
        "- **Líneas base:** persistencia (el embalse no cambia) y estacional (cambio medio de la misma época del año).",
        "- **Selección:** el sistema usa el modelo de menor MAE medio de volumen a 30/60/90 días; el Ingeniero puede fijar otro.",
        "",
    ]
    for r in session.query(Reservoir).order_by(Reservoir.name):
        models = sorted(latest_by_kind(session, r.code), key=lambda m: m.score)
        if not models:
            continue
        best = active_model(session, r.code)
        lines += [f"## {r.name}", ""]
        m0 = models[0]
        lines += [
            f"Datos: {m0.data_from} a {m0.data_to} ({m0.n_days} días) · fuente: {m0.data_source} · años de prueba: "
            f"{', '.join(map(str, m0.test_years))}. Modelo activo: **{KIND_LABELS.get(best.kind, best.kind)}**"
            f"{' (fijado manualmente)' if best.pinned else ''}.",
            "",
            "| Modelo | Horizonte | MAE (hm³) | RMSE (hm³) | MAPE (%) | R² | MAE cota (m) | Cobertura p10–p90 (%) |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for m in models:
            for row in sorted(m.metrics, key=lambda x: x["horizonte"]):
                lines.append(
                    f"| {KIND_LABELS.get(m.kind, m.kind)} | {row['horizonte']} d | {_fmt(row['MAE_hm3'])} | {_fmt(row['RMSE_hm3'])} | "
                    f"{_fmt(row['MAPE_%'], 1)} | {_fmt(row['R2'])} | {_fmt(row['MAE_cota_m'])} | {_fmt(row['cobertura_80_%'], 0)} |"
                )
        base = next((m for m in models if m.kind == "persistencia"), None)
        if base and best and best.kind != "persistencia":
            gain = (1 - best.score / base.score) * 100
            lines += [
                "",
                f"Mejora del modelo activo frente a la persistencia: **{gain:.0f} %** menos error medio.",
            ]
        xgb = next((m for m in models if m.kind == "xgboost"), None)
        if xgb and xgb.importance:
            from hidrica_ml.features import FEATURE_LABELS

            top = sorted(xgb.importance.items(), key=lambda kv: -kv[1])[:5]  # JSONB no conserva el orden
            lines += [
                "",
                "Variables más importantes (XGBoost, ganancia): "
                + "; ".join(f"{FEATURE_LABELS.get(k, k)} ({v:.0%})" for k, v in top)
                + ".",
            ]
        img = _plot(r.code, r.name, models, out_dir)
        if img:
            lines += ["", f"![Predicho contra real · {r.name}]({img})"]
        lines.append("")
    path = out_dir / "backtesting.md"
    path.write_bytes("\n".join(lines).encode("utf-8"))
    return path
