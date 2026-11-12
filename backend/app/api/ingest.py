"""Importación del movimiento diario desde Excel/CSV con vista previa (M4, HU-2.3 y HU-2.4).

Permisos: Ingeniero gestiona; Gerencia consulta los lotes; el Operador NO importa archivos
(la matriz le permite "solo registro manual").
"""

from __future__ import annotations

import io
import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, File, Request, UploadFile
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, api_error, client_ip, require
from app.core.permissions import Access, Module
from app.core.security import utcnow
from app.models.measurement import BatchStatus, ImportBatch, MeasurementSource
from app.models.user import Role, User
from app.services.audit import log_action
from app.services.ingest import PREVIEW_ISSUES_LIMIT, TEMPLATE_COLUMNS, create_preview, save_rows

router = APIRouter(prefix="/ingest", tags=["ingesta"])


def _importer(user: Annotated[User, Depends(require(Module.HYDRO_INGEST, Access.MANAGE))]) -> User:
    if user.role == Role.OPERADOR:
        raise api_error(
            403,
            "FORBIDDEN",
            "El Operador registra mediciones de forma manual; la importación la hace el Ingeniero.",
        )
    return user


Importer = Annotated[User, Depends(_importer)]
Reader = Annotated[User, Depends(require(Module.HYDRO_INGEST, Access.READ))]


class BatchOut(BaseModel):
    id: uuid.UUID
    filename: str
    status: BatchStatus
    created_at: datetime
    confirmed_at: datetime | None
    summary: dict[str, Any]
    issues: list[dict[str, Any]]
    issues_total: int
    sample: list[dict[str, Any]]


class ConfirmIn(BaseModel):
    overwrite: bool = False


class ConfirmOut(BaseModel):
    inserted: int
    updated: int
    skipped: int


def _allowed(user: User) -> set[str] | None:
    return None if user.role == Role.GERENCIA else set(user.reservoir_codes)


def _out(b: ImportBatch, *, full: bool = True) -> BatchOut:
    issues = b.issues if full else []
    return BatchOut(
        id=b.id,
        filename=b.filename,
        status=b.status,
        created_at=b.created_at,
        confirmed_at=b.confirmed_at,
        summary=b.summary,
        issues=issues[:PREVIEW_ISSUES_LIMIT],
        issues_total=len(b.issues),
        sample=[{k: v for k, v in r.items() if not k.startswith("_")} for r in b.rows[:20]] if full else [],
    )


# ------------------------------------------------------------------ plantillas (públicas: sin datos)


@router.get("/template.csv", response_class=PlainTextResponse, summary="Plantilla CSV del movimiento diario")
def template_csv() -> PlainTextResponse:
    header = ",".join(c[0] for c in TEMPLATE_COLUMNS)
    example = "TULE,2026-11-01,08:00,31.25,,6.40,4.10,0.40,0,4.10,Lectura normal"
    return PlainTextResponse(
        f"{header}\n{example}\n",
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="plantilla_movimiento_diario.csv"'},
    )


@router.get("/template.xlsx", summary="Plantilla Excel del movimiento diario (con hoja de instrucciones)")
def template_xlsx() -> StreamingResponse:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    wb = Workbook()
    ws = wb.active
    ws.title = "Movimiento diario"
    ws.append([c[0] for c in TEMPLATE_COLUMNS])
    ws.append(["TULE", "2026-11-01", "08:00", 31.25, None, 6.4, 4.1, 0.4, 0, 4.1, "Lectura normal"])
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="0C4A6E")
    for col, (name, *_rest) in zip(ws.columns, TEMPLATE_COLUMNS, strict=False):
        ws.column_dimensions[col[0].column_letter].width = max(14, len(name) + 2)

    help_ws = wb.create_sheet("Instrucciones")
    help_ws.append(["Columna", "Unidad", "¿Obligatoria?", "Descripción"])
    for cell in help_ws[1]:
        cell.font = Font(bold=True)
    for name, unit, required, desc in TEMPLATE_COLUMNS:
        help_ws.append([name, unit, "Sí" if required else "No", desc])
    help_ws.append([])
    help_ws.append(
        [
            "Notas",
            "",
            "",
            "Una fila por embalse y día. Decimales con punto o coma. No cambies los encabezados.",
        ]
    )
    for letter, width in zip("ABCD", (26, 22, 14, 80), strict=True):
        help_ws.column_dimensions[letter].width = width

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="plantilla_movimiento_diario.xlsx"'},
    )


# ------------------------------------------------------------------ vista previa y confirmación


@router.post(
    "/preview",
    response_model=BatchOut,
    status_code=201,
    summary="Validar un archivo y mostrar la vista previa",
)
async def preview(
    request: Request,
    session: DbSession,
    user: Importer,
    file: Annotated[UploadFile, File(description="Archivo .xlsx o .csv con el formato de la plantilla")],
) -> BatchOut:
    content = await file.read()
    batch = create_preview(
        session, content, file.filename or "archivo", allowed_codes=_allowed(user), user_id=user.id
    )
    log_action(
        session,
        "ingest.preview",
        actor=user,
        entity="import_batch",
        entity_id=str(batch.id),
        new={
            "archivo": batch.filename,
            "validas": batch.summary["filas_validas"],
            "errores": batch.summary["errores"],
        },
        ip=client_ip(request),
    )
    session.commit()
    return _out(batch)


@router.get("/batches", response_model=list[BatchOut], summary="Últimas importaciones")
def list_batches(session: DbSession, _: Reader) -> list[BatchOut]:
    batches = session.scalars(select(ImportBatch).order_by(ImportBatch.created_at.desc()).limit(20)).all()
    return [_out(b, full=False) for b in batches]


def _get_batch(session, batch_id: uuid.UUID) -> ImportBatch:
    batch = session.get(ImportBatch, batch_id)
    if batch is None:
        raise api_error(404, "NOT_FOUND", "Importación no encontrada.")
    return batch


@router.get("/batches/{batch_id}", response_model=BatchOut, summary="Ver una importación")
def get_batch(batch_id: uuid.UUID, session: DbSession, _: Reader) -> BatchOut:
    return _out(_get_batch(session, batch_id))


@router.post(
    "/batches/{batch_id}/confirm", response_model=ConfirmOut, summary="Confirmar y guardar las filas válidas"
)
def confirm(
    batch_id: uuid.UUID,
    body: ConfirmIn,
    request: Request,
    background: BackgroundTasks,
    session: DbSession,
    user: Importer,
) -> ConfirmOut:
    batch = _get_batch(session, batch_id)
    if batch.status != BatchStatus.PREVIEW:
        raise api_error(409, "NOT_PREVIEW", "Esta importación ya fue confirmada o descartada.")
    if batch.created_by != user.id:
        raise api_error(403, "FORBIDDEN", "Solo quien cargó el archivo puede confirmarlo.")
    if not batch.rows:
        raise api_error(
            422, "NO_VALID_ROWS", "No hay filas válidas para guardar. Corrige el archivo y vuelve a cargarlo."
        )
    codes = sorted({r["reservoir_code"] for r in batch.rows})
    result = save_rows(
        session,
        batch.rows,
        overwrite=body.overwrite,
        source=MeasurementSource.IMPORT,
        user_id=user.id,
        batch_id=batch.id,
    )
    batch.status = BatchStatus.CONFIRMED
    batch.confirmed_at = utcnow()
    batch.rows = []  # ya están en daily_measurements
    log_action(
        session,
        "ingest.confirm",
        actor=user,
        entity="import_batch",
        entity_id=str(batch.id),
        new={
            "insertadas": result.inserted,
            "actualizadas": result.updated,
            "omitidas": result.skipped,
            "sobrescribir": body.overwrite,
        },
        ip=client_ip(request),
    )
    session.commit()
    from app.api.alerts import schedule_evaluation

    schedule_evaluation(background, request, codes)
    return ConfirmOut(inserted=result.inserted, updated=result.updated, skipped=result.skipped)


@router.post("/batches/{batch_id}/discard", response_model=BatchOut, summary="Descartar una vista previa")
def discard(batch_id: uuid.UUID, session: DbSession, user: CurrentUser) -> BatchOut:
    batch = _get_batch(session, batch_id)
    if batch.created_by != user.id:
        raise api_error(403, "FORBIDDEN", "Solo quien cargó el archivo puede descartarlo.")
    if batch.status == BatchStatus.PREVIEW:
        batch.status = BatchStatus.DISCARDED
        batch.rows = []
        session.commit()
    return _out(batch, full=False)
