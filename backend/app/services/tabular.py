"""Lectura de tablas desde CSV o Excel (compartida por curvas e ingesta).

- CSV: separador coma o punto y coma (detectado), UTF-8 con o sin BOM.
- Excel: primera hoja visible de un .xlsx.
- Números con punto o coma decimal ("26,5" → 26.5).
- Encabezados normalizados: sin acentos, minúsculas, sin unidades entre paréntesis.
"""

from __future__ import annotations

import csv
import io
import re
import unicodedata
from datetime import date, datetime, time

MAX_BYTES = 10 * 1024 * 1024


class TableReadError(ValueError):
    pass


def normalize_header(h: object) -> str:
    text = unicodedata.normalize("NFKD", str(h or "")).encode("ascii", "ignore").decode().lower().strip()
    text = re.sub(r"\(.*?\)", "", text)  # "Cota (m.s.n.m.)" -> "cota"
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def to_float(value: object) -> float | None:
    """Convierte a número; None si está vacío. Lanza ValueError si no es numérico."""
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("booleano")
    if isinstance(value, int | float):
        return float(value)
    text = str(value).strip().replace(" ", "")
    if not text:
        return None
    if "," in text and "." in text:  # el último separador es el decimal: 1.234,56 o 1,234.56
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")
    return float(text)


_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%y")


def to_date(value: object) -> date | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip().split(" ")[0].split("T")[0]
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"fecha no reconocida: {value!r}")


def to_time(value: object) -> time | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, datetime):
        return value.time().replace(second=0, microsecond=0)
    if isinstance(value, time):
        return value.replace(second=0, microsecond=0)
    text = str(value).strip()
    for fmt in ("%H:%M", "%H:%M:%S", "%I:%M %p"):
        try:
            return datetime.strptime(text, fmt).time()
        except ValueError:
            continue
    raise ValueError(f"hora no reconocida: {value!r}")


def read_rows(content: bytes, filename: str, max_rows: int) -> list[list[object]]:
    """Devuelve todas las filas (incluido el encabezado), descartando filas totalmente vacías."""
    if len(content) > MAX_BYTES:
        raise TableReadError("El archivo supera 10 MB.")
    name = filename.lower()
    if name.endswith((".xlsx", ".xlsm")):
        from openpyxl import load_workbook

        try:
            wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        except Exception as exc:  # noqa: BLE001 — cualquier archivo dañado se reporta igual
            raise TableReadError(
                "No se pudo leer el archivo Excel. Verifica que sea un .xlsx válido."
            ) from exc
        ws = next((s for s in wb.worksheets if s.sheet_state == "visible"), wb.worksheets[0])
        rows = [list(r) for r in ws.iter_rows(values_only=True, max_row=max_rows + 2)]
    elif name.endswith((".csv", ".txt")):
        text = content.decode("utf-8-sig", errors="replace")
        first = text.splitlines()[0] if text else ""
        delimiter = ";" if first.count(";") > first.count(",") else ","
        rows = [list(r) for r in csv.reader(io.StringIO(text), delimiter=delimiter)]
    else:
        raise TableReadError("Formato no soportado. Usa un archivo .csv o .xlsx.")
    rows = [r for r in rows if any(c not in (None, "") for c in r)]
    if not rows:
        raise TableReadError("El archivo está vacío.")
    if len(rows) > max_rows + 1:
        raise TableReadError(f"El archivo supera {max_rows} filas.")
    return rows


def map_columns(headers: list[object], aliases: dict[str, set[str]]) -> dict[str, int]:
    """{campo: índice de columna} según los alias aceptados."""
    normalized = [normalize_header(h) for h in headers]
    index: dict[str, int] = {}
    for field, names in aliases.items():
        for i, h in enumerate(normalized):
            if h in names:
                index[field] = i
                break
    return index
