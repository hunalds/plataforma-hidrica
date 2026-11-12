"""Precipitación diaria CHIRPS v3 (UCSB Climate Hazards Center) desde el catálogo abierto de dynamical.org.

- Malla de 0,05° (~5,5 km), 1981 a la fecha, sin cuenta. Producto final + preliminar para los días recientes
  (misma lógica que la skill `chirps-fetch` de weather-skills).
- Se lee una sola vez el recuadro que cubre todas las áreas pedidas y se promedia por polígono.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np

from app.services.satellite.base import (
    AreaOfInterest,
    Quality,
    SatelliteObservation,
    SatelliteProvider,
    Variable,
)
from app.services.satellite.compute import areal_mean, grid_mask

FINAL_ID = "ucsb-chc-chirps-analysis-final"
PRELIM_ID = "ucsb-chc-chirps-analysis-preliminary"
STAGING_CATALOG = "https://stac-staging.dynamical.org/catalog.json"
CELL_DEG = 0.05


def _open(dataset_id: str):
    import dynamical_catalog

    if dataset_id not in dynamical_catalog.list():
        # Mientras CHIRPS no se promueva al catálogo principal (ver skill chirps-fetch)
        import os

        os.environ["DYNAMICAL_STAC_CATALOG_URL"] = STAGING_CATALOG
        dynamical_catalog.clear_cache()
    return dynamical_catalog.open(dataset_id, chunks=None)


class ChirpsProvider(SatelliteProvider):
    name = "chirps"
    variables = frozenset({Variable.PRECIPITATION})

    def check(self) -> bool:
        try:
            _open(FINAL_ID)
            return True
        except Exception:  # noqa: BLE001
            return False

    def _fetch(
        self, aoi: AreaOfInterest, variable: Variable, start: date, end: date
    ) -> list[SatelliteObservation]:
        return self.fetch_many([aoi], variable, start, end)

    def fetch_many(
        self, aois: list[AreaOfInterest], variable: Variable, start: date, end: date
    ) -> list[SatelliteObservation]:
        from shapely.geometry import shape
        from shapely.ops import unary_union

        geoms = {a.code: shape(a.geometry) for a in aois}
        minx, miny, maxx, maxy = unary_union(list(geoms.values())).bounds
        pad = CELL_DEG
        out: list[SatelliteObservation] = []
        final_until: date | None = None

        for dataset_id, product in ((FINAL_ID, "final"), (PRELIM_ID, "preliminar")):
            if product == "preliminar" and final_until is not None and final_until >= end:
                break
            ds = _open(dataset_id)
            lo = start if final_until is None else max(start, final_until + timedelta(days=1))
            sub = ds["precipitation_surface" if "precipitation_surface" in ds else list(ds.data_vars)[0]].sel(
                time=slice(lo.isoformat(), end.isoformat()),
                latitude=slice(miny - pad, maxy + pad)
                if ds.latitude[0] < ds.latitude[-1]
                else slice(maxy + pad, miny - pad),
                longitude=slice(minx - pad, maxx + pad),
            )
            if sub.sizes.get("time", 0) == 0:
                continue
            values = np.asarray(sub.values, dtype="float64")
            # dynamical.org publica tasas en mm/s (kg m-2 s-1): se convierten a mm/día
            units = str(sub.attrs.get("units", "")).lower()
            if "s-1" in units or "/s" in units:
                values = values * 86400
            times = [np.datetime64(t, "D").astype(date) for t in sub.time.values]
            lats, lons = np.asarray(sub.latitude.values), np.asarray(sub.longitude.values)
            for a in aois:
                mask = grid_mask(lats, lons, geoms[a.code], CELL_DEG)
                series = areal_mean(values, mask)
                for d, v in zip(times, series, strict=True):
                    ok = not np.isnan(v)
                    out.append(
                        SatelliteObservation(
                            day=d,
                            area_code=a.code,
                            variable=Variable.PRECIPITATION,
                            value=round(float(v), 3) if ok else None,
                            source=self.name,
                            quality=(Quality.GOOD if product == "final" else Quality.DOUBTFUL)
                            if ok
                            else Quality.MISSING,
                            meta={"producto": product, "celdas": int(mask.sum())},
                        )
                    )
            if times:
                final_until = times[-1]
        return out
