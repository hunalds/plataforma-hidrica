"""Punto de entrada de la API de la Plataforma Hídrica Zulia.

Ejecutar en desarrollo (desde backend/):
    uv run uvicorn app.main:app --reload
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import sessionmaker

from app import __version__
from app.api import audit, auth, health, reservoirs, users
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging, get_logger
from app.core.rate_limit import SlidingWindowLimiter
from app.db import build_engine
from app.services.email import build_email_sender


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, json=settings.app_env == "production")
    log = get_logger("app")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        log.info("app_start", env=settings.app_env, db=settings.effective_db_name)
        yield
        app.state.engine.dispose()
        log.info("app_stop")

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description=(
            "API para la predicción de disponibilidad hídrica de los embalses Tulé, Manuelote y Tres Ríos."
        ),
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.engine = build_engine(settings)
    app.state.session_factory = sessionmaker(app.state.engine, expire_on_commit=False)
    app.state.login_limiter = SlidingWindowLimiter(settings.login_rate_limit_per_minute, 60)
    app.state.email_sender = build_email_sender(settings)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def access_log(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        log.info(
            "request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            ms=round((time.perf_counter() - start) * 1000, 1),
        )
        return response

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(users.router)
    app.include_router(audit.router)
    app.include_router(reservoirs.router)
    return app


app = create_app()
