"""Endpoint de salud: lo usan el frontend, el monitoreo y el despliegue."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from app import __version__
from app.core.logging import get_logger
from app.db import get_engine

router = APIRouter(tags=["salud"])
log = get_logger(__name__)


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    environment: str
    database: Literal["ok", "error"]
    postgis: str | None = None
    detail: str | None = None


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Estado del servicio",
    responses={503: {"model": HealthResponse, "description": "Base de datos no disponible"}},
)
def health(request: Request, engine: Annotated[Engine, Depends(get_engine)]):
    env = request.app.state.settings.app_env
    try:
        with engine.connect() as conn:
            postgis = conn.execute(text("SELECT postgis_lib_version()")).scalar_one()
    except SQLAlchemyError as exc:
        # Se registra solo el tipo de error: el mensaje del driver puede incluir datos de conexión
        log.error("health_db_error", error_type=type(exc.orig or exc).__name__)
        body = HealthResponse(
            status="degraded",
            version=__version__,
            environment=env,
            database="error",
            detail="No se pudo conectar a la base de datos",
        )
        return JSONResponse(status_code=503, content=body.model_dump())
    return HealthResponse(status="ok", version=__version__, environment=env, database="ok", postgis=postgis)
