"""Tareas en segundo plano lanzadas a mano desde la API (sin Celery ni Redis, ver C-08).

La API crea el registro Job y agenda la función con BackgroundTasks de FastAPI; la tarea usa su
propia sesión de base de datos y actualiza el avance para que el frontend lo muestre.
"""

from __future__ import annotations

import traceback
import uuid
from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from app.core.logging import get_logger
from app.core.security import utcnow
from app.models.satellite import Job, JobStatus

log = get_logger(__name__)

Work = Callable[[Session, Callable[[float, str], None]], dict[str, Any]]


def create_job(session: Session, kind: str, params: dict[str, Any], user_id: int | None) -> Job:
    job = Job(kind=kind, params=params, status=JobStatus.PENDING, progress=0.0, created_by=user_id)
    session.add(job)
    session.flush()
    return job


def run_job(factory: sessionmaker[Session], job_id: uuid.UUID, work: Work) -> None:
    """Ejecuta la tarea registrando inicio, avance, resultado o error."""
    with factory() as status_session, factory() as work_session:
        job = status_session.get(Job, job_id)
        if job is None:
            return
        job.status = JobStatus.RUNNING
        job.started_at = utcnow()
        status_session.commit()

        def progress(fraction: float, message: str) -> None:
            job.progress = round(min(max(fraction, 0.0), 1.0), 4)
            job.message = message[:500]
            status_session.commit()

        try:
            result = work(work_session, progress)
            job.status = JobStatus.DONE
            job.progress = 1.0
            job.result = result
            job.message = "Terminada"
        except Exception as exc:  # noqa: BLE001 — cualquier fallo queda registrado en la tarea
            work_session.rollback()
            job.status = JobStatus.FAILED
            job.message = f"{type(exc).__name__}: {exc}"[:500]
            log.error("job_failed", job=str(job_id), kind=job.kind, error=traceback.format_exc(limit=5))
        job.finished_at = utcnow()
        status_session.commit()
