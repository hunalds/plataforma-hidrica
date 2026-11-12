"""Comprueba desde esta red el acceso a las fuentes de datos satelitales y climáticos (HU-0.6).

Solo hace peticiones HTTP anónimas de lectura a los catálogos públicos. No descarga datos
ni usa credenciales. Uso (desde la raíz del proyecto):
    uv run --project backend python scripts/check_satellite_sources.py [--json salida.json]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime

USER_AGENT = "plataforma-hidrica-zulia/0.1 (tesis URBE; verificacion de conectividad)"


@dataclass
class Source:
    key: str
    name: str
    url: str
    use: str
    needs_account: str


SOURCES = [
    Source(
        "chirps_dynamical",
        "CHIRPS · catálogo dynamical.org (STAC)",
        "https://stac.dynamical.org/catalog.json",
        "Precipitación diaria",
        "No",
    ),
    Source(
        "chirps_ucsb",
        "CHIRPS · servidor de la UCSB (CHC)",
        "https://data.chc.ucsb.edu/products/CHIRPS/v3.0/",
        "Precipitación diaria (alternativa)",
        "No",
    ),
    Source(
        "cdse_stac",
        "Copernicus Data Space · STAC (Sentinel-2)",
        "https://stac.dataspace.copernicus.eu/v1/",
        "NDWI / superficie de agua",
        "Sí (para descargar)",
    ),
    Source(
        "planetary_computer",
        "Microsoft Planetary Computer · STAC",
        "https://planetarycomputer.microsoft.com/api/stac/v1/collections/sentinel-2-l2a",
        "NDWI (Sentinel-2 y Landsat)",
        "No",
    ),
    Source(
        "cds_era5_land",
        "Copernicus Climate Data Store (ERA5-Land)",
        "https://cds.climate.copernicus.eu/api/catalogue/v1/collections/reanalysis-era5-land",
        "Humedad del suelo",
        "Sí (gratuita)",
    ),
    Source(
        "nasa_cmr_smap",
        "NASA Earthdata CMR (SMAP)",
        "https://cmr.earthdata.nasa.gov/search/collections.json?short_name=SPL3SMP_E",
        "Humedad del suelo (complemento)",
        "Sí (para descargar)",
    ),
    Source(
        "arco_era5_gcs",
        "ARCO-ERA5 · Google Cloud Storage",
        "https://storage.googleapis.com/gcp-public-data-arco-era5?prefix=ar/&delimiter=/&max-keys=5",
        "Humedad del suelo (servidor de Google)",
        "No",
    ),
    Source(
        "eox_s2cloudless",
        "EOX Sentinel-2 Cloudless (mapa base)",
        "https://tiles.maps.eox.at/wmts/1.0.0/WMTSCapabilities.xml",
        "Mapa base satelital",
        "No",
    ),
    Source(
        "osm_tiles",
        "OpenStreetMap (mapa base)",
        "https://tile.openstreetmap.org/0/0/0.png",
        "Mapa base de calles",
        "No",
    ),
    Source(
        "google_earth_engine",
        "Google Earth Engine (referencia)",
        "https://earthengine.googleapis.com/$discovery/rest?version=v1",
        "Opción descartada (C-10)",
        "Sí",
    ),
]


@dataclass
class Result:
    key: str
    name: str
    use: str
    needs_account: str
    reachable: bool
    http_status: int | None
    ms: float | None
    error: str | None


def probe(src: Source, timeout: float) -> Result:
    if not src.url.startswith("https://"):
        raise ValueError(f"Solo se permiten URLs https: {src.url}")
    req = urllib.request.Request(src.url, headers={"User-Agent": USER_AGENT})  # noqa: S310 — validada arriba
    start = time.perf_counter()
    status, error = None, None
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 — URLs fijas https
            status = resp.status
            resp.read(2048)
    except urllib.error.HTTPError as exc:
        status = exc.code  # el servidor respondió: hay conectividad aunque pida autenticación
    except Exception as exc:  # noqa: BLE001 — se reporta cualquier fallo de red
        error = f"{type(exc).__name__}: {exc}"[:160]
    ms = round((time.perf_counter() - start) * 1000, 0)
    # 2xx/3xx = accesible; 401/403 = accesible pero requiere cuenta o está bloqueado por región
    reachable = status is not None and status < 400
    return Result(src.key, src.name, src.use, src.needs_account, reachable, status, ms, error)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="guardar los resultados en este archivo")
    ap.add_argument("--timeout", type=float, default=15)
    args = ap.parse_args()

    results = [probe(s, args.timeout) for s in SOURCES]
    for r in results:
        mark = "OK " if r.reachable else ("RESP" if r.http_status else "FALLA")
        detail = f"HTTP {r.http_status}" if r.http_status else r.error
        print(f"[{mark:5}] {r.name:48} {detail} ({r.ms:.0f} ms)")
    if args.json:
        payload = {
            "verificado": datetime.now().isoformat(timespec="seconds"),
            "resultados": [asdict(r) for r in results],
        }
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
