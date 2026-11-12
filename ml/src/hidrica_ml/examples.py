"""Archivos de EJEMPLO (sintéticos) para demostrar la importación y el control de calidad (M4).

Se toman del dataset sintético las fechas 2026-10-16 a 2026-10-31. La carga inicial de la base
(`app.cli load-synthetic-measurements`) llega hasta el 2026-10-15, así estos archivos agregan
datos "nuevos" al importarlos, como ocurriría en la operación diaria.

Uso (desde ml/):
    uv run python -m hidrica_ml.examples
"""

from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from hidrica_ml.schema import COLUMN_NAMES

ML_DIR = Path(__file__).resolve().parents[2]
SOURCE = ML_DIR / "data" / "synthetic" / "movimiento_diario_sintetico.csv"
OUT = ML_DIR / "data" / "synthetic" / "ejemplos"
START, END = date(2026, 10, 16), date(2026, 10, 31)

# Errores introducidos a propósito en el archivo "con errores" (fila del archivo → descripción)
INJECTED = [
    ("DUPLICATE", "Fecha repetida (TULE 2026-10-20 aparece dos veces)"),
    ("BAD_DATE", "Fecha imposible: 31/02/2026"),
    ("NOT_NUMERIC", "Cota escrita como texto: 'treinta'"),
    ("MISSING", "Fila sin cota"),
    ("NEGATIVE", "Caudal de salida negativo"),
    ("OUT_OF_RANGE", "Apertura de compuertas 150 %"),
    ("OUT_OF_CURVE", "Cota 5.00 m (fuera de la curva de Tulé, error de tipeo)"),
    ("UNKNOWN_RESERVOIR", "Código de embalse mal escrito: 'TULEE'"),
    ("FUTURE_DATE", "Fecha futura: 2030-01-01"),
    ("SUDDEN_JUMP", "Aviso: salto de +2,5 m en Manuelote el 2026-10-25"),
    ("MISSING_DAYS", "Aviso: faltan los días 2026-10-27 y 2026-10-28 de Tres Ríos"),
]


def _source_rows() -> list[dict[str, str]]:
    with SOURCE.open(encoding="utf-8") as fh:
        return [r for r in csv.DictReader(fh) if START.isoformat() <= r["fecha"] <= END.isoformat()]


def _write_xlsx(path: Path, rows: list[list[object]], title: str) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Movimiento diario"
    ws.append(list(COLUMN_NAMES))
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="0C4A6E")
    for r in rows:
        ws.append(r)
    info = wb.create_sheet("Acerca de")
    info.append(["⚠️ DATOS SINTÉTICOS — no son mediciones de MINAGUAS"])
    info.append([title])
    wb.save(path)


def _as_values(r: dict[str, str]) -> list[object]:
    out: list[object] = []
    for c in COLUMN_NAMES:
        v = r.get(c, "")
        if c in ("embalse", "fecha", "hora", "observaciones"):
            out.append(v or None)
        else:
            out.append(float(v) if v not in ("", None) else None)
    return out


def build() -> dict[str, str]:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = _source_rows()

    # 1) Importación válida (Excel)
    valid = OUT / "importacion_valida_2026-10-16_al_31.xlsx"
    _write_xlsx(valid, [_as_values(r) for r in rows], "Importación válida: 16 al 31 de octubre de 2026, 3 embalses.")

    # 2) Misma información en "formato venezolano": ; como separador, coma decimal y DD/MM/AAAA
    ve = OUT / "importacion_valida_formato_venezolano.csv"
    with ve.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(COLUMN_NAMES)
        for r in rows:
            y, m, d = r["fecha"].split("-")
            vals = [r[c] for c in COLUMN_NAMES]
            vals[COLUMN_NAMES.index("fecha")] = f"{d}/{m}/{y}"
            vals = [
                v.replace(".", ",") if c not in ("embalse", "fecha", "hora", "observaciones") else v
                for c, v in zip(COLUMN_NAMES, vals, strict=True)
            ]
            w.writerow(vals)

    # 3) Archivo con errores introducidos a propósito
    bad = [_as_values(r) for r in rows]
    idx = {(v[0], v[1]): i for i, v in enumerate(bad)}
    col = {c: i for i, c in enumerate(COLUMN_NAMES)}

    def row_of(res: str, day: str) -> list[object]:
        return bad[idx[(res, day)]]

    bad.append(list(row_of("TULE", "2026-10-20")))  # DUPLICATE
    row_of("TULE", "2026-10-21")[col["fecha"]] = "31/02/2026"  # BAD_DATE
    row_of("TULE", "2026-10-22")[col["cota_msnm"]] = "treinta"  # NOT_NUMERIC
    row_of("TULE", "2026-10-23")[col["cota_msnm"]] = None  # MISSING
    row_of("MANUELOTE", "2026-10-18")[col["caudal_salida_m3s"]] = -3.5  # NEGATIVE
    row_of("MANUELOTE", "2026-10-19")[col["apertura_compuertas_pct"]] = 150  # OUT_OF_RANGE
    row_of("TULE", "2026-10-24")[col["cota_msnm"]] = 5.0  # OUT_OF_CURVE
    row_of("TULE", "2026-10-26")[col["embalse"]] = "TULEE"  # UNKNOWN_RESERVOIR
    future = list(row_of("TULE", "2026-10-31"))
    future[col["fecha"]] = "2030-01-01"
    bad.append(future)  # FUTURE_DATE
    jump = row_of("MANUELOTE", "2026-10-25")
    jump[col["cota_msnm"]] = round(float(jump[col["cota_msnm"]]) + 2.5, 2)  # SUDDEN_JUMP (aviso)
    jump[col["volumen_hm3"]] = None  # para que no dispare además VOLUME_MISMATCH
    bad = [v for v in bad if not (v[0] == "TRES_RIOS" and v[1] in ("2026-10-27", "2026-10-28"))]  # MISSING_DAYS
    errors = OUT / "importacion_con_errores.xlsx"
    _write_xlsx(errors, bad, "Archivo con errores introducidos a propósito para demostrar el control de calidad.")

    readme = OUT / "README.md"
    readme.write_text(
        "# ⚠️ Archivos de EJEMPLO sintéticos\n\n"
        "Generados con `uv run python -m hidrica_ml.examples` a partir de `movimiento_diario_sintetico.csv` "
        f"(fechas {START.isoformat()} a {END.isoformat()}). No son mediciones de MINAGUAS.\n\n"
        "| Archivo | Para qué sirve |\n|---|---|\n"
        f"| `{valid.name}` | Importación correcta de 48 filas (3 embalses × 16 días) |\n"
        f"| `{ve.name}` | Los mismos datos con `;`, coma decimal y fechas DD/MM/AAAA "
        "(como los exporta Excel en español) |\n"
        f"| `{errors.name}` | Demostración del control de calidad: |\n"
        + "".join(f"|   | • `{code}`: {desc} |\n" for code, desc in INJECTED)
        + "\nPrimero carga el histórico (hasta el 2026-10-15) con "
        "`uv run python -m app.cli load-synthetic-measurements` "
        "desde `backend/`, y luego importa estos archivos desde la plataforma (menú *Importar datos*).\n",
        encoding="utf-8",
    )
    return {
        "valida": str(valid),
        "venezolano": str(ve),
        "errores": str(errors),
        "inyectados": json.dumps([c for c, _ in INJECTED]),
    }


if __name__ == "__main__":
    for k, v in build().items():
        print(f"{k}: {v}")
