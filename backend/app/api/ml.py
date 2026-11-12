"""Predicción con Machine Learning (M6): entrenamiento, registro de modelos y proyección por embalse.

Permisos: M6 → Gerencia consulta, Ingeniero gestiona (entrena, fija modelos), Operador sin acceso.
La proyección por embalse se lee con M7 (panel), que tienen todos los roles.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select

from app.api.deps import AppSettings, DbSession, api_error, client_ip, require
from app.api.reservoirs import get_visible_reservoir
from app.api.satellite import JobOut, _job_out
from app.core.permissions import Access, Module
from app.models.ml import MLModel
from app.models.reservoir import Reservoir
from app.models.satellite import Job
from app.models.user import User
from app.services import ml_service
from app.services.audit import log_action
from app.services.jobs import create_job, run_job

router = APIRouter(tags=["predicción"])

MLReader = Annotated[User, Depends(require(Module.PREDICTION, Access.READ))]
MLManager = Annotated[User, Depends(require(Module.PREDICTION, Access.MANAGE))]
PanelReader = Annotated[User, Depends(require(Module.DASHBOARD, Access.READ))]

KINDS = ("persistencia", "estacional", "xgboost", "lstm")


class TrainIn(BaseModel):
    reservoir_codes: list[str] | None = None
    kinds: list[str] = Field(default=list(KINDS))
    test_years: list[int] | None = Field(default=None, description="Por defecto, los 4 últimos años")

    @field_validator("kinds")
    @classmethod
    def _kinds(cls, v: list[str]) -> list[str]:
        bad = set(v) - set(KINDS)
        if bad or not v:
            raise ValueError(f"Modelos válidos: {', '.join(KINDS)}")
        return v


class ModelOut(BaseModel):
    id: int
    reservoir_code: str
    kind: str
    version_tag: str
    data_from: str
    data_to: str
    n_days: int
    data_source: str
    test_years: list[int]
    params: dict[str, Any]
    metrics: list[dict[str, Any]]
    importance: dict[str, float] | None
    score: float
    train_seconds: float
    pinned: bool
    active: bool
    created_at: datetime


def _model_out(m: MLModel, active_id: int | None) -> ModelOut:
    return ModelOut.model_validate(
        {**{c: getattr(m, c) for c in ModelOut.model_fields if c != "active"}, "active": m.id == active_id}
    )


@router.post(
    "/ml/train", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED, summary="Reentrenar los modelos"
)
def train(
    body: TrainIn,
    request: Request,
    background: BackgroundTasks,
    session: DbSession,
    settings: AppSettings,
    user: MLManager,
) -> JobOut:
    codes = body.reservoir_codes or [
        c for (c,) in session.execute(select(Reservoir.code).order_by(Reservoir.code))
    ]
    for c in codes:
        try:
            ml_service.build_series(session, c, settings)
        except ml_service.MLDataError as exc:
            raise api_error(422, "NOT_ENOUGH_DATA", str(exc)) from None
    running = session.scalars(
        select(Job).where(Job.kind == "ml.train", Job.status.in_(["PENDIENTE", "EN_CURSO"]))
    ).first()
    if running:
        raise api_error(409, "JOB_RUNNING", "Ya hay un entrenamiento en curso. Espera a que termine.")
    params = {
        "tipo": "entrenamiento",
        "embalses": codes,
        "modelos": body.kinds,
        "anios_prueba": body.test_years,
        "desde": "",
        "hasta": "",
    }
    job = create_job(session, "ml.train", params, user.id)
    log_action(
        session,
        "ml.train",
        actor=user,
        entity="job",
        entity_id=str(job.id),
        new=params,
        ip=client_ip(request),
    )
    session.commit()

    def work(s, progress):
        return ml_service.train_and_register(
            s, settings, codes, tuple(body.kinds), body.test_years, user.id, progress
        )

    background.add_task(run_job, request.app.state.session_factory, job.id, work)
    return _job_out(job)


@router.get("/ml/jobs", response_model=list[JobOut], summary="Últimos entrenamientos")
def train_jobs(session: DbSession, _: MLReader) -> list[JobOut]:
    jobs = session.scalars(
        select(Job).where(Job.kind == "ml.train").order_by(Job.created_at.desc()).limit(10)
    ).all()
    return [_job_out(j) for j in jobs]


@router.get("/ml/models", response_model=list[ModelOut], summary="Modelos registrados")
def list_models(session: DbSession, _: MLReader, reservoir: str | None = None) -> list[ModelOut]:
    stmt = select(MLModel).order_by(MLModel.reservoir_code, MLModel.created_at.desc())
    if reservoir:
        stmt = stmt.where(MLModel.reservoir_code == reservoir.upper())
    models = session.scalars(stmt).all()
    active = {}
    for code in {m.reservoir_code for m in models}:
        a = ml_service.active_model(session, code)
        active[code] = a.id if a else None
    return [_model_out(m, active.get(m.reservoir_code)) for m in models]


def _get_model(session, model_id: int) -> MLModel:
    m = session.get(MLModel, model_id)
    if m is None:
        raise api_error(404, "NOT_FOUND", "Modelo no encontrado.")
    return m


@router.post(
    "/ml/models/{model_id}/pin", response_model=ModelOut, summary="Fijar este modelo para su embalse"
)
def pin(model_id: int, request: Request, session: DbSession, user: MLManager) -> ModelOut:
    m = _get_model(session, model_id)
    for other in session.scalars(
        select(MLModel).where(MLModel.reservoir_code == m.reservoir_code, MLModel.pinned.is_(True))
    ):
        other.pinned = False
    m.pinned = True
    log_action(
        session,
        "ml.pin",
        actor=user,
        entity="ml_model",
        entity_id=m.id,
        new={"embalse": m.reservoir_code, "modelo": m.kind, "version": m.version_tag},
        ip=client_ip(request),
    )
    session.commit()
    return _model_out(m, m.id)


@router.post(
    "/ml/models/{model_id}/unpin", response_model=ModelOut, summary="Volver a la selección automática"
)
def unpin(model_id: int, request: Request, session: DbSession, user: MLManager) -> ModelOut:
    m = _get_model(session, model_id)
    m.pinned = False
    log_action(
        session,
        "ml.unpin",
        actor=user,
        entity="ml_model",
        entity_id=m.id,
        new={"embalse": m.reservoir_code},
        ip=client_ip(request),
    )
    session.commit()
    a = ml_service.active_model(session, m.reservoir_code)
    return _model_out(m, a.id if a else None)


@router.get("/reservoirs/{code}/forecast", summary="Proyección a 90 días con banda de incertidumbre")
def forecast(code: str, session: DbSession, settings: AppSettings, user: PanelReader) -> dict[str, Any]:
    r = get_visible_reservoir(session, user, code)
    try:
        return ml_service.forecast(session, settings, r.code)
    except ml_service.MLDataError as exc:
        raise api_error(404, "NO_FORECAST", str(exc)) from None
