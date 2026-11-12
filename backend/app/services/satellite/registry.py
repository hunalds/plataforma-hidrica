"""Selección de la fuente satelital según la configuración (SATELLITE_PROVIDER en .env)."""

from __future__ import annotations

from app.services.satellite.base import SatelliteProvider
from app.services.satellite.mock import MockProvider

# Fuentes alternativas previstas (no implementadas): requieren cuenta. Ver docs/evidencias/HU-0.6.
PLANNED_PROVIDERS = {
    "era5_land_cds": "Humedad del suelo · Copernicus CDS (requiere cuenta gratuita)",
    "copernicus": "NDWI / superficie de agua · Sentinel-2 en Copernicus Data Space (requiere cuenta)",
    "gee": "Google Earth Engine (opcional, descartado por ahora: C-10)",
}


def _implemented() -> dict[str, type[SatelliteProvider]]:
    # Importación diferida: las librerías geoespaciales pesadas solo se cargan si se usan
    from app.services.satellite.chirps import ChirpsProvider
    from app.services.satellite.openmeteo import OpenMeteoSoilProvider
    from app.services.satellite.water import PlanetaryComputerWaterProvider

    return {
        "mock": MockProvider,
        "chirps": ChirpsProvider,
        "era5_land_openmeteo": OpenMeteoSoilProvider,
        "planetary_computer": PlanetaryComputerWaterProvider,
    }


class UnknownProviderError(ValueError):
    pass


def get_provider(name: str) -> SatelliteProvider:
    key = name.strip().lower()
    implemented = _implemented()
    if key in implemented:
        return implemented[key]()
    if key in PLANNED_PROVIDERS:
        raise NotImplementedError(f"La fuente {key!r} aún no está implementada: {PLANNED_PROVIDERS[key]}")
    raise UnknownProviderError(f"Fuente satelital desconocida: {name!r}")
