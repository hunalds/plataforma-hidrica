"""Ingesta del movimiento diario de embalses (M4): lectura, control de calidad y guardado.

Flujo de importación (HU-2.3, HU-2.4):
    archivo → parse_measurement_file() → validate() → vista previa (ImportBatch)
            → confirm_batch() → daily_measurements
El registro manual del Operador (HU-2.5) usa el mismo validate(), así las reglas son idénticas.

Severidades:
    error  → la fila NO se guarda (dato imposible o ambiguo)
    aviso  → la fila se guarda, marcada en quality_flags para revisión (dato raro pero posible)
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import date, time, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.security import utcnow
from app.models.measurement import DailyMeasurement, ImportBatch, MeasurementSource, VolumeSource
from app.models.reservoir import ElevationCurve, Reservoir
from app.services.curves import CurveInterpolator, CurveRangeError, interpolator_for
from app.services.tabular import TableReadError, map_columns, read_rows, to_date, to_float, to_time

MAX_ROWS = 50_000  # ~45 años de datos diarios de 3 embalses
VOLUME_MISMATCH_PCT = 5.0  # aviso si el volumen reportado difiere de la curva en más de este %
MAX_ABOVE_NORMAL_M = 3.0  # aviso si la cota supera el nivel normal en más de 3 m
PREVIEW_ISSUES_LIMIT = 500

# Columnas de la plantilla (mismas que ml/src/schema.py; ver test_ingest_template_matches_ml_schema)
TEMPLATE_COLUMNS: list[tuple[str, str, bool, str]] = [
    ("embalse", "", True, "Código del embalse: TULE, MANUELOTE o TRES_RIOS"),
    ("fecha", "AAAA-MM-DD o DD/MM/AAAA", True, "Fecha de la medición"),
    ("hora", "HH:MM", False, "Hora de la lectura del limnímetro"),
    ("cota_msnm", "m.s.n.m.", True, "Nivel del agua (cota)"),
    ("volumen_hm3", "hm³", False, "Volumen almacenado; si falta se calcula con la curva vigente"),
    ("caudal_entrada_m3s", "m³/s", False, "Caudal de entrada (aporte de los ríos)"),
    ("caudal_salida_m3s", "m³/s", False, "Salida/extracción hacia las plantas potabilizadoras"),
    ("gasto_ecologico_m3s", "m³/s", False, "Caudal liberado al río aguas abajo"),
    ("apertura_compuertas_pct", "%", False, "Apertura de compuertas (0 a 100)"),
    ("captacion_m3s", "m³/s", False, "Captación"),
    ("observaciones", "", False, "Notas del operador"),
]

_ALIASES: dict[str, set[str]] = {
    "reservoir": {"embalse", "codigo_embalse", "presa"},
    "day": {"fecha", "dia", "date"},
    "time": {"hora", "hora_lectura"},
    "level_m": {"cota_msnm", "cota", "nivel", "cota_m"},
    "volume_hm3": {"volumen_hm3", "volumen", "vol_hm3"},
    "inflow_m3s": {"caudal_entrada_m3s", "caudal_entrada", "entrada", "aporte"},
    "outflow_m3s": {"caudal_salida_m3s", "caudal_salida", "salida", "extraccion", "extraccion_m3s"},
    "eco_flow_m3s": {"gasto_ecologico_m3s", "gasto_ecologico", "caudal_ecologico"},
    "gate_opening_pct": {"apertura_compuertas_pct", "apertura_compuertas", "compuertas", "apertura"},
    "intake_m3s": {"captacion_m3s", "captacion"},
    "notes": {"observaciones", "notas", "comentarios"},
}

# Variantes de nombre que se aceptan para el código del embalse
_RESERVOIR_NAMES = {
    "tule": "TULE",
    "manuelote": "MANUELOTE",
    "tres_rios": "TRES_RIOS",
    "tresrios": "TRES_RIOS",
}

FLOW_FIELDS = ("inflow_m3s", "outflow_m3s", "eco_flow_m3s", "intake_m3s")
FIELD_LABELS = {
    "reservoir": "embalse",
    "day": "fecha",
    "time": "hora",
    "level_m": "cota",
    "volume_hm3": "volumen",
    "inflow_m3s": "caudal de entrada",
    "outflow_m3s": "caudal de salida",
    "eco_flow_m3s": "gasto ecológico",
    "gate_opening_pct": "apertura de compuertas",
    "intake_m3s": "captación",
}


@dataclass
class Issue:
    severity: str  # "error" | "aviso"
    code: str
    message: str
    row: int | None = None  # fila del archivo (1 = encabezados)
    reservoir: str | None = None
    day: str | None = None
    field: str | None = None


@dataclass
class RawRow:
    """Fila ya convertida a tipos Python (aún sin validar reglas de negocio)."""

    row: int | None
    reservoir: str
    day: date
    time: time | None = None
    level_m: float | None = None
    volume_hm3: float | None = None
    inflow_m3s: float | None = None
    outflow_m3s: float | None = None
    eco_flow_m3s: float | None = None
    gate_opening_pct: float | None = None
    intake_m3s: float | None = None
    notes: str | None = None


@dataclass
class ValidationResult:
    rows: list[dict[str, Any]]  # filas válidas normalizadas, listas para guardar
    issues: list[Issue]
    summary: dict[str, Any] = field(default_factory=dict)

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "error"]


def _normalize_reservoir(value: object) -> str:
    text = str(value or "").strip()
    from app.services.tabular import normalize_header

    key = normalize_header(text)
    return _RESERVOIR_NAMES.get(key, text.upper())


# --------------------------------------------------------------------------- lectura


def parse_measurement_file(content: bytes, filename: str) -> tuple[list[RawRow], list[Issue]]:
    """Convierte el archivo en filas tipadas. Los problemas de formato son errores por fila."""
    try:
        table = read_rows(content, filename, MAX_ROWS)
    except TableReadError as exc:
        return [], [Issue("error", "FILE", str(exc))]
    index = map_columns(table[0], _ALIASES)
    missing = [f for f in ("reservoir", "day", "level_m") if f not in index]
    if missing:
        names = ", ".join(FIELD_LABELS[m] for m in missing)
        return [], [
            Issue(
                "error", "MISSING_COLUMNS", f"Faltan columnas obligatorias: {names}. Descarga la plantilla."
            )
        ]

    rows: list[RawRow] = []
    issues: list[Issue] = []
    for n, values in enumerate(table[1:], start=2):

        def cell(name: str, values: list[object] = values) -> object:
            i = index.get(name)
            return values[i] if i is not None and i < len(values) else None

        reservoir = _normalize_reservoir(cell("reservoir"))
        try:
            day = to_date(cell("day"))
        except ValueError:
            issues.append(
                Issue("error", "BAD_DATE", f"Fecha no válida: {cell('day')!r}.", n, reservoir, field="day")
            )
            continue
        if day is None:
            issues.append(Issue("error", "MISSING", "Falta la fecha.", n, reservoir, field="day"))
            continue
        raw = RawRow(row=n, reservoir=reservoir, day=day)
        ok = True
        try:
            raw.time = to_time(cell("time"))
        except ValueError:
            issues.append(
                Issue(
                    "aviso",
                    "BAD_TIME",
                    f"Hora no válida ({cell('time')!r}); se ignora.",
                    n,
                    reservoir,
                    day.isoformat(),
                    "time",
                )
            )
        for name in ("level_m", "volume_hm3", *FLOW_FIELDS, "gate_opening_pct"):
            try:
                setattr(raw, name, to_float(cell(name)))
            except ValueError:
                issues.append(
                    Issue(
                        "error",
                        "NOT_NUMERIC",
                        f"El valor de {FIELD_LABELS[name]} no es numérico: {cell(name)!r}.",
                        n,
                        reservoir,
                        day.isoformat(),
                        name,
                    )
                )
                ok = False
        notes = cell("notes")
        raw.notes = str(notes).strip()[:2000] if notes not in (None, "") else None
        if ok:
            rows.append(raw)
    return rows, issues


# --------------------------------------------------------------------------- validación


class CurveBook:
    """Versiones de curva de un embalse; elige la vigente para cada fecha."""

    def __init__(self, curves: list[ElevationCurve]) -> None:
        self.curves = sorted(curves, key=lambda c: (c.valid_from, c.version))
        self._cache: dict[int, CurveInterpolator] = {}

    def for_day(self, day: date) -> tuple[int, CurveInterpolator] | None:
        chosen = None
        for c in self.curves:
            if c.valid_from <= day:
                chosen = c
        if chosen is None:
            return None
        if chosen.id not in self._cache:
            self._cache[chosen.id] = interpolator_for(chosen)
        return chosen.version, self._cache[chosen.id]


def validate(
    session: Session,
    raw_rows: list[RawRow],
    *,
    allowed_codes: set[str] | None,
    today: date | None = None,
) -> ValidationResult:
    """Aplica las reglas de calidad. `allowed_codes` = embalses que el usuario puede cargar (None = todos)."""
    today = today or date.today()
    issues: list[Issue] = []
    reservoirs = {r.code: r for r in session.scalars(select(Reservoir)).all()}

    by_res: dict[str, list[RawRow]] = defaultdict(list)
    for r in raw_rows:
        if r.reservoir not in reservoirs:
            issues.append(
                Issue(
                    "error",
                    "UNKNOWN_RESERVOIR",
                    f"Embalse desconocido: {r.reservoir!r}.",
                    r.row,
                    r.reservoir,
                    r.day.isoformat(),
                    "reservoir",
                )
            )
        elif allowed_codes is not None and r.reservoir not in allowed_codes:
            issues.append(
                Issue(
                    "error",
                    "NOT_ASSIGNED",
                    f"No tienes asignado el embalse {r.reservoir}.",
                    r.row,
                    r.reservoir,
                    r.day.isoformat(),
                    "reservoir",
                )
            )
        else:
            by_res[r.reservoir].append(r)

    valid: list[dict[str, Any]] = []
    per_res_summary: dict[str, Any] = {}
    for code, rows in by_res.items():
        res = reservoirs[code]
        book = CurveBook(
            list(session.scalars(select(ElevationCurve).where(ElevationCurve.reservoir_code == code)).all())
        )
        days = [r.day for r in rows]
        lo, hi = min(days), max(days)
        existing = {
            d: lvl
            for d, lvl in session.execute(
                select(DailyMeasurement.day, DailyMeasurement.level_m).where(
                    DailyMeasurement.reservoir_code == code,
                    DailyMeasurement.day >= lo - timedelta(days=1),
                    DailyMeasurement.day <= hi,
                )
            ).all()
        }

        seen: dict[date, int | None] = {}
        accepted: dict[date, dict[str, Any]] = {}
        for r in sorted(rows, key=lambda x: (x.day, x.row or 0)):
            d = r.day.isoformat()

            def err(code_: str, msg: str, field_: str | None = None, r: RawRow = r, d: str = d) -> None:
                issues.append(Issue("error", code_, msg, r.row, r.reservoir, d, field_))

            row_errors_before = len(issues)
            if r.day in seen:
                err(
                    "DUPLICATE", f"Fecha repetida en el archivo (ya aparece en la fila {seen[r.day]}).", "day"
                )
                continue
            seen[r.day] = r.row
            if r.day > today:
                err("FUTURE_DATE", "La fecha es posterior a hoy.", "day")
            if r.level_m is None:
                err("MISSING", "Falta la cota.", "level_m")
            for name in (*FLOW_FIELDS, "volume_hm3"):
                v = getattr(r, name)
                if v is not None and v < 0:
                    err("NEGATIVE", f"El {FIELD_LABELS[name]} no puede ser negativo.", name)
            if r.gate_opening_pct is not None and not 0 <= r.gate_opening_pct <= 100:
                err(
                    "OUT_OF_RANGE",
                    "La apertura de compuertas debe estar entre 0 y 100 %.",
                    "gate_opening_pct",
                )

            volume, volume_source, curve_version = r.volume_hm3, None, None
            flags: list[str] = []
            if r.level_m is not None:
                curve = book.for_day(r.day)
                if curve is not None:
                    version, interp = curve
                    try:
                        curve_v = interp.volume_at(r.level_m)
                    except CurveRangeError:
                        err(
                            "OUT_OF_CURVE",
                            f"Cota {r.level_m} fuera del rango de la curva vigente (v{version}). "
                            "Verifica el dato.",
                            "level_m",
                        )
                        curve_v = None
                    if curve_v is not None:
                        if volume is None:
                            volume, volume_source, curve_version = curve_v, VolumeSource.CURVE, version
                        elif curve_v > 0 and abs(volume - curve_v) / curve_v * 100 > VOLUME_MISMATCH_PCT:
                            flags.append("VOLUME_MISMATCH")
                            issues.append(
                                Issue(
                                    "aviso",
                                    "VOLUME_MISMATCH",
                                    f"El volumen reportado ({volume}) difiere más de "
                                    f"{VOLUME_MISMATCH_PCT:.0f} % "
                                    f"del calculado con la curva ({curve_v:.2f}).",
                                    r.row,
                                    code,
                                    d,
                                    "volume_hm3",
                                )
                            )
                elif volume is None:
                    flags.append("NO_CURVE")
                    issues.append(
                        Issue(
                            "aviso",
                            "NO_CURVE",
                            "No hay curva vigente: el volumen no se pudo calcular.",
                            r.row,
                            code,
                            d,
                            "volume_hm3",
                        )
                    )
                if volume is not None and volume_source is None:
                    volume_source = VolumeSource.REPORTED

                if r.level_m < res.dead_level:
                    flags.append("BELOW_DEAD")
                    issues.append(
                        Issue(
                            "aviso",
                            "BELOW_DEAD",
                            f"Cota por debajo del volumen muerto ({res.dead_level}).",
                            r.row,
                            code,
                            d,
                            "level_m",
                        )
                    )
                if r.level_m > res.normal_level + MAX_ABOVE_NORMAL_M:
                    flags.append("FAR_ABOVE_NORMAL")
                    issues.append(
                        Issue(
                            "aviso",
                            "FAR_ABOVE_NORMAL",
                            f"Cota más de {MAX_ABOVE_NORMAL_M:.0f} m sobre el nivel normal "
                            f"({res.normal_level}).",
                            r.row,
                            code,
                            d,
                            "level_m",
                        )
                    )
                prev_level = accepted.get(r.day - timedelta(days=1), {}).get(
                    "level_m", existing.get(r.day - timedelta(days=1))
                )
                if prev_level is not None and abs(r.level_m - prev_level) > res.qc_max_daily_change_m:
                    flags.append("SUDDEN_JUMP")
                    issues.append(
                        Issue(
                            "aviso",
                            "SUDDEN_JUMP",
                            f"Salto brusco: la cota cambió {r.level_m - prev_level:+.2f} m respecto al día "
                            f"anterior (límite {res.qc_max_daily_change_m} m).",
                            r.row,
                            code,
                            d,
                            "level_m",
                        )
                    )

            if r.day in existing:
                flags.append("EXISTS")
                issues.append(
                    Issue(
                        "aviso",
                        "EXISTS",
                        "Ya existe un registro para esta fecha (se reemplaza solo si eliges sobrescribir).",
                        r.row,
                        code,
                        d,
                        "day",
                    )
                )

            if len([i for i in issues[row_errors_before:] if i.severity == "error"]) == 0:
                accepted[r.day] = {
                    "reservoir_code": code,
                    "day": r.day.isoformat(),
                    "reading_time": r.time.isoformat(timespec="minutes") if r.time else None,
                    "level_m": r.level_m,
                    "volume_hm3": round(volume, 4) if volume is not None else None,
                    "volume_source": volume_source.value if volume_source else None,
                    "curve_version": curve_version,
                    "inflow_m3s": r.inflow_m3s,
                    "outflow_m3s": r.outflow_m3s,
                    "eco_flow_m3s": r.eco_flow_m3s,
                    "gate_opening_pct": r.gate_opening_pct,
                    "intake_m3s": r.intake_m3s,
                    "notes": r.notes,
                    "quality_flags": [f for f in flags if f != "EXISTS"] or None,
                    "_exists": r.day in existing,
                }

        # Días faltantes dentro del rango del archivo (considerando lo que ya está en la base)
        covered = set(accepted) | set(existing)
        gaps = [
            lo + timedelta(days=i) for i in range((hi - lo).days + 1) if lo + timedelta(days=i) not in covered
        ]
        for start, end in _ranges(gaps)[:50]:
            text = start.isoformat() if start == end else f"{start.isoformat()} a {end.isoformat()}"
            n = (end - start).days + 1
            issues.append(
                Issue("aviso", "MISSING_DAYS", f"Faltan {n} día(s): {text}.", None, code, start.isoformat())
            )
        valid.extend(accepted.values())
        per_res_summary[code] = {
            "desde": lo.isoformat(),
            "hasta": hi.isoformat(),
            "filas_validas": len(accepted),
            "nuevas": sum(1 for v in accepted.values() if not v["_exists"]),
            "existentes": sum(1 for v in accepted.values() if v["_exists"]),
            "dias_faltantes": len(gaps),
        }

    errors = [i for i in issues if i.severity == "error"]
    summary = {
        "filas_leidas": len(raw_rows),
        "filas_validas": len(valid),
        "filas_con_error": len({(i.row, i.reservoir, i.day) for i in errors if i.row is not None}),
        "errores": len(errors),
        "avisos": len(issues) - len(errors),
        "por_embalse": per_res_summary,
    }
    return ValidationResult(valid, issues, summary)


def _ranges(days: list[date]) -> list[tuple[date, date]]:
    out: list[tuple[date, date]] = []
    for d in sorted(days):
        if out and d - out[-1][1] == timedelta(days=1):
            out[-1] = (out[-1][0], d)
        else:
            out.append((d, d))
    return out


# --------------------------------------------------------------------------- guardado


def issues_to_json(issues: list[Issue]) -> list[dict[str, Any]]:
    return [asdict(i) for i in issues]


def create_preview(
    session: Session, content: bytes, filename: str, *, allowed_codes: set[str] | None, user_id: int | None
) -> ImportBatch:
    raw, parse_issues = parse_measurement_file(content, filename)
    result = validate(session, raw, allowed_codes=allowed_codes)
    issues = parse_issues + result.issues
    errors = sum(1 for i in issues if i.severity == "error")
    summary = {
        **result.summary,
        "filas_leidas": len(raw)
        + sum(1 for i in parse_issues if i.row is not None and i.severity == "error"),
        "errores": errors,
        "avisos": len(issues) - errors,
    }
    summary["filas_con_error"] = len(
        {(i.row, i.reservoir, i.day) for i in issues if i.severity == "error" and i.row is not None}
    )
    # Vistas previas viejas no confirmadas: se descartan para no acumular datos
    old = session.scalars(
        select(ImportBatch).where(
            ImportBatch.status == "PREVIEW", ImportBatch.created_at < utcnow() - timedelta(days=1)
        )
    )
    for b in old:
        b.status = "DISCARDED"
        b.rows = []
    batch = ImportBatch(
        filename=filename[:255],
        summary=summary,
        issues=issues_to_json(issues),
        rows=result.rows,
        created_by=user_id,
    )
    session.add(batch)
    session.flush()
    return batch


@dataclass(frozen=True)
class SaveResult:
    inserted: int
    updated: int
    skipped: int


def save_rows(
    session: Session,
    rows: list[dict[str, Any]],
    *,
    overwrite: bool,
    source: MeasurementSource,
    user_id: int | None,
    batch_id: Any = None,
) -> SaveResult:
    """Guarda filas validadas. Con overwrite=False, las fechas existentes se omiten."""
    inserted = updated = skipped = 0
    to_write = []
    for r in rows:
        exists = r.get("_exists", False)
        if exists and not overwrite:
            skipped += 1
            continue
        updated += int(exists)
        inserted += int(not exists)
        values = {k: v for k, v in r.items() if not k.startswith("_")}
        values["day"] = date.fromisoformat(values["day"]) if isinstance(values["day"], str) else values["day"]
        if values.get("reading_time"):
            values["reading_time"] = time.fromisoformat(values["reading_time"])
        values.update(source=source, created_by=user_id, import_batch_id=batch_id)
        to_write.append(values)

    for chunk_start in range(0, len(to_write), 2000):
        chunk = to_write[chunk_start : chunk_start + 2000]
        stmt = insert(DailyMeasurement).values(chunk)
        update_cols = {c: stmt.excluded[c] for c in chunk[0] if c not in ("reservoir_code", "day")}
        update_cols["updated_at"] = utcnow()
        stmt = stmt.on_conflict_do_update(index_elements=["reservoir_code", "day"], set_=update_cols)
        session.execute(stmt)
    return SaveResult(inserted, updated, skipped)
