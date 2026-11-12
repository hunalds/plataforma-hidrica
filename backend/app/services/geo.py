"""Geometrías de los embalses (M3/M5): polígonos de OpenStreetMap y áreas de influencia provisionales.

- Los polígonos de los espejos de agua vienen de OpenStreetMap (© colaboradores de OSM, licencia ODbL),
  consultados por identificador en Nominatim. Quedan marcados como provisionales hasta recibir los
  oficiales de MINAGUAS (P-07). Se versiona una copia en app/data/geo/ para no depender de la red.
- Las cuencas oficiales no están disponibles (P-08). Mientras tanto se usa un ÁREA DE INFLUENCIA:
  el polígono del embalse con un margen (buffer) configurable, por defecto 20 km. Es una aproximación
  para agregar la precipitación y la humedad del suelo, no una delimitación hidrológica.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from pyproj import Geod, Transformer
from shapely.geometry import MultiPolygon, Polygon, mapping, shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform

GEO_DIR = Path(__file__).resolve().parents[1] / "data" / "geo"
OSM_SNAPSHOT = GEO_DIR / "embalses_osm.geojson"
DEFAULT_INFLUENCE_KM = 20.0

# Identificadores OSM verificados el 2026-11-12 (búsqueda Overpass en el estado Zulia)
OSM_IDS = {"TULE": "R3429312", "MANUELOTE": "R3429313", "TRES_RIOS": "W255993485"}
OSM_ATTRIBUTION = "© colaboradores de OpenStreetMap (ODbL)"

_geod = Geod(ellps="WGS84")


def area_km2(geom: BaseGeometry) -> float:
    """Área geodésica en km² (exacta sobre el elipsoide, sin proyectar)."""
    area, _ = _geod.geometry_area_perimeter(geom)
    return abs(area) / 1e6


def _local_utm(geom: BaseGeometry) -> tuple[Transformer, Transformer]:
    lon, lat = geom.centroid.x, geom.centroid.y
    zone = int((lon + 180) // 6) + 1
    epsg = (32600 if lat >= 0 else 32700) + zone
    fwd = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
    back = Transformer.from_crs(f"EPSG:{epsg}", "EPSG:4326", always_xy=True)
    return fwd, back


def buffer_km(geom: BaseGeometry, km: float) -> BaseGeometry:
    """Margen en km calculado en la proyección UTM local (WGS84 → UTM → WGS84)."""
    fwd, back = _local_utm(geom)
    projected = transform(fwd.transform, geom).buffer(km * 1000, resolution=16)
    return transform(back.transform, projected)


def as_multipolygon(geom: BaseGeometry) -> MultiPolygon:
    if isinstance(geom, MultiPolygon):
        return geom
    if isinstance(geom, Polygon):
        return MultiPolygon([geom])
    raise ValueError(f"Se esperaba un polígono y llegó {geom.geom_type}")


def load_snapshot(path: Path = OSM_SNAPSHOT) -> dict[str, dict[str, Any]]:
    """{código: Feature GeoJSON} desde la copia versionada de OSM."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return {f["properties"]["code"]: f for f in data["features"]}


def build_snapshot(nominatim_geojson: dict[str, Any], retrieved: date) -> dict[str, Any]:
    """Normaliza la respuesta de Nominatim: asigna el código del embalse y la atribución."""
    by_osm = {
        f"{f['properties']['osm_type'][0].upper()}{f['properties']['osm_id']}": f
        for f in nominatim_geojson["features"]
    }
    features = []
    for code, osm_id in OSM_IDS.items():
        f = by_osm[osm_id]
        geom = shape(f["geometry"])
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "code": code,
                    "name": f["properties"].get("name"),
                    "osm_id": osm_id,
                    "source": f"OpenStreetMap ({OSM_ATTRIBUTION}), consultado {retrieved.isoformat()}",
                    "area_km2": round(area_km2(geom), 3),
                    "provisional": True,
                },
                "geometry": mapping(geom),
            }
        )
    return {"type": "FeatureCollection", "features": features}


def apply_osm_geometries(
    session, *, influence_km: float = DEFAULT_INFLUENCE_KM, force: bool = False
) -> list[str]:
    """Carga en la base los polígonos OSM (si faltan) y el área de influencia provisional.

    No reemplaza geometrías cargadas por un usuario (oficiales) salvo con force=True.
    Devuelve una línea de resumen por embalse.
    """
    import json as _json

    from sqlalchemy import func

    from app.models.reservoir import Reservoir

    report = []
    snapshot = load_snapshot()
    for r in session.query(Reservoir).order_by(Reservoir.code):
        feature = snapshot.get(r.code)
        if feature is None:
            report.append(f"{r.code}: sin polígono en la copia de OSM")
            continue
        geom = shape(feature["geometry"])
        if r.geom is None or force:
            r.geom = func.ST_Multi(func.ST_SetSRID(func.ST_GeomFromGeoJSON(_json.dumps(mapping(geom))), 4326))
            r.geom_source = f"{feature['properties']['source']} · PROVISIONAL"
            msg = f"{r.code}: espejo de agua OSM ({feature['properties']['area_km2']} km²)"
        else:
            msg = f"{r.code}: se conserva el polígono existente ({r.geom_source or 'sin origen'})"
        if r.basin_geom is None or force or (r.basin_source or "").startswith("Área de influencia"):
            influence = as_multipolygon(buffer_km(geom, influence_km))
            r.basin_geom = func.ST_SetSRID(func.ST_GeomFromGeoJSON(_json.dumps(mapping(influence))), 4326)
            r.basin_source = (
                f"Área de influencia PROVISIONAL: espejo OSM + {influence_km:g} km "
                f"({area_km2(influence):.0f} km²). Reemplazar por la cuenca oficial (P-08)."
            )
            msg += f" · área de influencia {influence_km:g} km"
        report.append(msg)
    session.flush()
    return report
