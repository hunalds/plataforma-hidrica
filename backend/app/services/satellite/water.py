"""NDWI y superficie del espejo de agua con Sentinel-2 L2A y Landsat Collection 2 Level-2.

Fuente: Microsoft Planetary Computer (catálogo STAC abierto; las URL se firman sin cuenta).
- Sentinel-2 L2A (2017→, 10 m, ~5 días): bandas B03 (verde) y B08 (NIR); nubes con la capa SCL.
- Landsat 5/7/8/9 C2 L2 (2005→, 30 m, ~8–16 días): bandas green y nir08; nubes con QA_PIXEL.
Por cada fecha se toma la escena con menos nubes sobre el embalse. El área se calcula dentro del
polígono del embalse con un margen de 300 m (para captar crecidas sobre la orilla de OSM).
"""

from __future__ import annotations

import os
from datetime import date, timedelta
from pathlib import Path

import numpy as np
from shapely.geometry import mapping, shape

from app.services.geo import area_km2, buffer_km
from app.services.satellite.base import (
    AreaOfInterest,
    Quality,
    SatelliteObservation,
    SatelliteProvider,
    Variable,
)
from app.services.satellite.compute import ndwi, quality_for_cloud, water_stats

STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
AOI_MARGIN_KM = 0.3
MAX_SCENE_CLOUD = 80  # descarta escenas con más de 80 % de nubes en toda la tesela

# SCL de Sentinel-2: 4 vegetación, 5 suelo, 6 agua, 7 sin clasificar, 11 nieve → válidos
S2_VALID_SCL = {4, 5, 6, 7, 11}
# Línea base 04.00 (desde 2022-01-25): reflectancias con desplazamiento de +1000
S2_OFFSET_DATE = date(2022, 1, 25)


def configure_proj() -> None:
    """Usa la base de PROJ incluida en rasterio.

    En Windows, el instalador de PostgreSQL/PostGIS define PROJ_LIB apuntando a un proj.db antiguo,
    incompatible con el PROJ de rasterio ("DATABASE.LAYOUT.VERSION.MINOR"). Solo afecta a este proceso.
    """
    import rasterio

    bundled = Path(rasterio.__file__).parent / "proj_data"
    if (bundled / "proj.db").exists():
        os.environ["PROJ_DATA"] = str(bundled)
        os.environ["PROJ_LIB"] = str(bundled)


def landsat_valid(qa: np.ndarray) -> np.ndarray:
    """QA_PIXEL de Landsat C2: válido si no es relleno (bit 0), nube dilatada (1), cirro (2), nube (3)
    ni sombra de nube (4)."""
    bad = (1 << 0) | (1 << 1) | (1 << 2) | (1 << 3) | (1 << 4)
    return (qa.astype("uint32") & bad) == 0


def landsat_reflectance(dn: np.ndarray) -> np.ndarray:
    """Escala de Landsat C2 L2: reflectancia = DN · 0,0000275 − 0,2 (0 = sin dato)."""
    out = dn.astype("float64") * 0.0000275 - 0.2
    out[dn == 0] = np.nan
    return out


def s2_reflectance(dn: np.ndarray, acquired: date) -> np.ndarray:
    out = dn.astype("float64")
    if acquired >= S2_OFFSET_DATE:
        out = out - 1000
    out[dn == 0] = np.nan
    return out / 10000


class PlanetaryComputerWaterProvider(SatelliteProvider):
    name = "planetary_computer"
    variables = frozenset({Variable.NDWI, Variable.WATER_AREA})

    def __init__(self, collections: tuple[str, ...] = ("sentinel-2-l2a", "landsat-c2-l2")) -> None:
        self.collections = collections

    def check(self) -> bool:
        import httpx

        try:
            return httpx.get(f"{STAC_URL}/collections/sentinel-2-l2a", timeout=30).status_code == 200
        except httpx.HTTPError:
            return False

    def _client(self):
        configure_proj()
        import planetary_computer
        import pystac_client

        return pystac_client.Client.open(STAC_URL, modifier=planetary_computer.sign_inplace)

    def _fetch(
        self, aoi: AreaOfInterest, variable: Variable, start: date, end: date
    ) -> list[SatelliteObservation]:
        # Las dos variables salen de la misma imagen: se calculan juntas y se filtra la pedida
        return [o for o in self.fetch_both(aoi, start, end) if o.variable == variable]

    def fetch_both(self, aoi: AreaOfInterest, start: date, end: date) -> list[SatelliteObservation]:
        geom = buffer_km(shape(aoi.geometry), AOI_MARGIN_KM)
        aoi_area = area_km2(geom)
        catalog = self._client()
        items = catalog.search(
            collections=list(self.collections),
            intersects=mapping(geom),
            datetime=f"{start.isoformat()}/{(end + timedelta(days=1)).isoformat()}",
            query={"eo:cloud_cover": {"lt": MAX_SCENE_CLOUD}},
        ).item_collection()

        # Por fecha, la escena con menos nubes
        best: dict[date, object] = {}
        for it in items:
            d = it.datetime.date()
            if start <= d <= end and (
                d not in best
                or it.properties.get("eo:cloud_cover", 100) < best[d].properties.get("eo:cloud_cover", 100)
            ):
                best[d] = it

        out: list[SatelliteObservation] = []
        for d, it in sorted(best.items()):
            try:
                stats = self._scene_stats(it, geom, d, aoi_area)
            except Exception as exc:  # noqa: BLE001 — una escena dañada no detiene la descarga
                stats = {
                    "cloud_pct": 100.0,
                    "ndwi_mean": None,
                    "water_area_km2": None,
                    "error": type(exc).__name__,
                }
            quality = quality_for_cloud(stats["cloud_pct"])
            meta = {"escena": it.id, "coleccion": it.collection_id, "area_aoi_km2": round(aoi_area, 3)}
            if "error" in stats:
                meta["error"] = stats["error"]
            for var, key in ((Variable.NDWI, "ndwi_mean"), (Variable.WATER_AREA, "water_area_km2")):
                value = stats[key] if quality != "sin_dato" else None
                out.append(
                    SatelliteObservation(
                        day=d,
                        area_code=aoi.code,
                        variable=var,
                        value=value,
                        source=it.collection_id,
                        quality=Quality(quality),
                        cloud_pct=stats["cloud_pct"],
                        meta=meta,
                    )
                )
        return out

    def _scene_stats(self, item, geom, acquired: date, aoi_area: float) -> dict:
        import rasterio
        from rasterio.enums import Resampling
        from rasterio.features import geometry_mask
        from rasterio.warp import transform_geom
        from rasterio.windows import from_bounds

        if item.collection_id == "sentinel-2-l2a":
            green_key, nir_key, mask_key = "B03", "B08", "SCL"
        else:
            green_key, nir_key, mask_key = "green", "nir08", "qa_pixel"

        def read(key: str, ref_shape=None):
            with rasterio.open(item.assets[key].href) as src:
                g = transform_geom("EPSG:4326", src.crs, mapping(geom))
                window = (
                    from_bounds(*shape(g).bounds, transform=src.transform).round_offsets().round_lengths()
                )
                if ref_shape is None:
                    data = src.read(1, window=window, boundless=True, fill_value=0)
                else:
                    data = src.read(
                        1,
                        window=window,
                        out_shape=ref_shape,
                        boundless=True,
                        fill_value=0,
                        resampling=Resampling.nearest,
                    )
                return data, src.window_transform(window), g

        green_dn, transform, g = read(green_key)
        nir_dn, _, _ = read(nir_key, green_dn.shape)
        mask_raw, _, _ = read(
            mask_key, green_dn.shape
        )  # SCL (20 m) se remuestrea a 10 m por vecino más cercano

        aoi_mask = ~geometry_mask([g], out_shape=green_dn.shape, transform=transform)
        if item.collection_id == "sentinel-2-l2a":
            green, nir = s2_reflectance(green_dn, acquired), s2_reflectance(nir_dn, acquired)
            valid = np.isin(mask_raw, list(S2_VALID_SCL))
        else:
            green, nir = landsat_reflectance(green_dn), landsat_reflectance(nir_dn)
            valid = landsat_valid(mask_raw) & (mask_raw != 0)
        return water_stats(ndwi(green, nir), valid, aoi_mask, aoi_area)
