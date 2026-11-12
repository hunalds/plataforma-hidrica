"""Cálculos puros sobre mallas e imágenes (sin red), para probarlos con datos sintéticos."""

from __future__ import annotations

import numpy as np
import shapely
from shapely.geometry import box
from shapely.geometry.base import BaseGeometry


def grid_mask(lats: np.ndarray, lons: np.ndarray, geom: BaseGeometry, cell_deg: float) -> np.ndarray:
    """Máscara (lat, lon) de las celdas de la malla que pertenecen al polígono.

    Se usan los centros de celda dentro del polígono. Si el polígono es más chico que una celda
    (p. ej. un embalse pequeño en una malla de 0,25°), se toman las celdas cuya caja lo intersecta.
    """
    lon2d, lat2d = np.meshgrid(lons, lats)
    inside = shapely.contains_xy(geom, lon2d, lat2d)
    if inside.any():
        return inside
    half = cell_deg / 2
    boxes = np.array(
        [[box(lo - half, la - half, lo + half, la + half) for lo in lons] for la in lats],
        dtype=object,
    )
    return shapely.intersects(boxes, geom)


def areal_mean(values: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Promedio espacial por tiempo de un arreglo (t, lat, lon) dentro de la máscara (ignora NaN)."""
    sel = values[:, mask]
    with np.errstate(invalid="ignore"):
        counts = np.sum(~np.isnan(sel), axis=1)
        sums = np.nansum(sel, axis=1)
    out = np.full(values.shape[0], np.nan)
    ok = counts > 0
    out[ok] = sums[ok] / counts[ok]
    return out


def ndwi(green: np.ndarray, nir: np.ndarray) -> np.ndarray:
    """Índice de agua de McFeeters (1996): (Verde − NIR) / (Verde + NIR). Agua > 0."""
    green = green.astype("float64")
    nir = nir.astype("float64")
    with np.errstate(divide="ignore", invalid="ignore"):
        out = (green - nir) / (green + nir)
    out[~np.isfinite(out)] = np.nan
    return out


def water_stats(
    index: np.ndarray, valid: np.ndarray, aoi: np.ndarray, aoi_area_km2: float, threshold: float = 0.0
) -> dict[str, float | None]:
    """Estadísticas de agua dentro del área de interés.

    - cloud_pct: % del área sin dato válido (nubes, sombras, bandas faltantes).
    - ndwi_mean: NDWI medio de los píxeles válidos.
    - water_area_km2: fracción de agua entre los píxeles válidos × área de interés
      (se extrapola a la parte nublada asumiendo la misma proporción).
    """
    in_aoi = aoi.sum()
    if in_aoi == 0:
        return {"cloud_pct": 100.0, "ndwi_mean": None, "water_area_km2": None}
    good = aoi & valid & ~np.isnan(index)
    cloud_pct = float(100 * (1 - good.sum() / in_aoi))
    if good.sum() == 0:
        return {"cloud_pct": cloud_pct, "ndwi_mean": None, "water_area_km2": None}
    vals = index[good]
    water_frac = float(np.mean(vals > threshold))
    return {
        "cloud_pct": round(cloud_pct, 2),
        "ndwi_mean": round(float(np.mean(vals)), 4),
        "water_area_km2": round(water_frac * aoi_area_km2, 4),
    }


def quality_for_cloud(cloud_pct: float) -> str:
    """Bandera de calidad según el porcentaje del área sin dato válido."""
    if cloud_pct > 60:
        return "sin_dato"
    if cloud_pct > 20:
        return "dudosa"
    return "buena"
