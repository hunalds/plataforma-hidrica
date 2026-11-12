"""Curvas cota–área–volumen (M3): lectura desde CSV/Excel, validación e interpolación lineal.

Formato aceptado (encabezados sin importar mayúsculas, acentos ni unidades entre paréntesis):
    cota | cota_msnm | elevacion        → cota (m.s.n.m.)
    volumen | volumen_hm3               → volumen (hm³)
    area | area_km2  (opcional)         → área del espejo de agua (km²)
Separador de CSV: coma o punto y coma. Decimales con punto o con coma (si el separador es ';').
"""

from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.reservoir import ElevationCurve
from app.services.tabular import TableReadError, map_columns, read_rows, to_float

MAX_ROWS = 20_000

_ALIASES = {
    "elevation": {"cota", "cota_msnm", "elevacion", "nivel", "cota_m"},
    "volume_hm3": {"volumen", "volumen_hm3", "vol", "volumen_hm"},
    "area_km2": {"area", "area_km2", "superficie", "superficie_km2"},
}

TEMPLATE_CSV = "cota_msnm,area_km2,volumen_hm3\n26.60,10.5,25.0\n27.00,11.2,29.4\n"


@dataclass(frozen=True)
class CurvePoint:
    elevation: float
    volume_hm3: float
    area_km2: float | None = None


class CurveFileError(ValueError):
    """Error de formato con detalle por fila: [(fila, mensaje)]."""

    def __init__(self, message: str, rows: list[tuple[int, str]] | None = None) -> None:
        super().__init__(message)
        self.rows = rows or []


def parse_curve_file(content: bytes, filename: str) -> list[CurvePoint]:
    try:
        rows = read_rows(content, filename, MAX_ROWS)
    except TableReadError as exc:
        raise CurveFileError(str(exc)) from None
    index = map_columns(rows[0], _ALIASES)
    missing = [f for f in ("elevation", "volume_hm3") if f not in index]
    if missing:
        names = {"elevation": "cota", "volume_hm3": "volumen"}
        raise CurveFileError(
            "Faltan columnas obligatorias: "
            + ", ".join(names[m] for m in missing)
            + ". Descarga la plantilla."
        )

    errors: list[tuple[int, str]] = []
    points: list[CurvePoint] = []
    for n, row in enumerate(rows[1:], start=2):  # fila 1 = encabezados

        def cell(field: str, row: list[object] = row) -> object:
            i = index.get(field)
            return row[i] if i is not None and i < len(row) else None

        try:
            h = to_float(cell("elevation"))
            v = to_float(cell("volume_hm3"))
            a = to_float(cell("area_km2"))
        except ValueError:
            errors.append((n, "Valor no numérico."))
            continue
        if h is None or v is None:
            errors.append((n, "Faltan la cota o el volumen."))
            continue
        if v < 0 or (a is not None and a < 0):
            errors.append((n, "El volumen y el área no pueden ser negativos."))
            continue
        points.append(CurvePoint(h, v, a))

    points.sort(key=lambda p: p.elevation)
    for prev, cur in zip(points, points[1:], strict=False):
        if cur.elevation == prev.elevation:
            errors.append((0, f"Cota repetida: {cur.elevation}."))
        elif cur.volume_hm3 < prev.volume_hm3:
            errors.append((0, f"El volumen disminuye entre las cotas {prev.elevation} y {cur.elevation}."))
    if len(points) < 2 and not errors:
        errors.append((0, "La curva necesita al menos 2 puntos."))
    if errors:
        raise CurveFileError(f"Se encontraron {len(errors)} error(es) en el archivo.", errors[:100])
    return points


class CurveRangeError(ValueError):
    pass


class CurveInterpolator:
    """Interpolación lineal por tramos sobre puntos ordenados por cota (y volumen no decreciente)."""

    def __init__(self, points: list[CurvePoint]) -> None:
        self.h = [p.elevation for p in points]
        self.v = [p.volume_hm3 for p in points]
        self.a = [p.area_km2 for p in points]

    @staticmethod
    def _interp(x: float, xs: list[float], ys: list[float], what: str) -> float:
        if x < xs[0] or x > xs[-1]:
            raise CurveRangeError(f"{what} fuera del rango de la curva ({xs[0]} – {xs[-1]}).")
        i = bisect_left(xs, x)
        if xs[i] == x:
            return ys[i]
        x0, x1, y0, y1 = xs[i - 1], xs[i], ys[i - 1], ys[i]
        return y0 + (y1 - y0) * (x - x0) / (x1 - x0)

    def volume_at(self, elevation: float) -> float:
        return self._interp(elevation, self.h, self.v, "Cota")

    def area_at(self, elevation: float) -> float | None:
        if any(a is None for a in self.a):
            return None
        return self._interp(elevation, self.h, self.a, "Cota")  # type: ignore[arg-type]

    def elevation_at(self, volume: float) -> float:
        # Con tramos de volumen constante se toma la primera cota que alcanza ese volumen
        return self._interp(volume, self.v, self.h, "Volumen")


def current_curve(session: Session, reservoir_code: str, on: date | None = None) -> ElevationCurve | None:
    """Versión vigente en la fecha `on` (la de valid_from más reciente <= on; empate: mayor versión)."""
    on = on or date.today()
    return session.scalars(
        select(ElevationCurve)
        .where(ElevationCurve.reservoir_code == reservoir_code, ElevationCurve.valid_from <= on)
        .order_by(ElevationCurve.valid_from.desc(), ElevationCurve.version.desc())
        .limit(1)
    ).first()


def interpolator_for(curve: ElevationCurve) -> CurveInterpolator:
    return CurveInterpolator([CurvePoint(p.elevation, p.volume_hm3, p.area_km2) for p in curve.points])
