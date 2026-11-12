"""Registro de modelos de predicción (M6)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class MLModel(Base):
    """Un modelo entrenado para un embalse, con sus datos, hiperparámetros y métricas de backtesting."""

    __tablename__ = "ml_models"

    id: Mapped[int] = mapped_column(primary_key=True)
    reservoir_code: Mapped[str] = mapped_column(ForeignKey("reservoirs.code", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(30))  # persistencia | estacional | xgboost | lstm
    version_tag: Mapped[str] = mapped_column(String(40))  # AAAAMMDD-HHMMSS del entrenamiento
    data_from: Mapped[str] = mapped_column(String(10))
    data_to: Mapped[str] = mapped_column(String(10))
    n_days: Mapped[int] = mapped_column(Integer)
    data_source: Mapped[str] = mapped_column(
        String(60)
    )  # p. ej. "hidrologia: base de datos · satelite: sintetico"
    test_years: Mapped[list[int]] = mapped_column(JSONB)
    params: Mapped[dict[str, Any]] = mapped_column(JSONB)
    metrics: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)  # por horizonte (30/60/90)
    importance: Mapped[dict[str, float] | None] = mapped_column(JSONB)
    score: Mapped[float] = mapped_column(Float)  # MAE medio de volumen (hm³) a 30/60/90 días
    artifact_dir: Mapped[str] = mapped_column(String(500))
    train_seconds: Mapped[float] = mapped_column(Float)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)  # fijado manualmente por el Ingeniero
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
