"""Selección de la fuente satelital según la configuración (SATELLITE_PROVIDER en .env)."""

from __future__ import annotations

from app.services.satellite.base import SatelliteProvider
from app.services.satellite.mock import MockProvider

# Fuentes previstas. Las reales se implementan en la Iteración 3 (M5), según la verificación
# de conectividad de HU-0.6 (docs/evidencias/conectividad-fuentes-*.json).
PLANNED_PROVIDERS = {
    "chirps": "Precipitación diaria · dynamical.org / UCSB (sin cuenta)",
    "era5_land": "Humedad del suelo · Copernicus CDS (cuenta gratuita)",
    "copernicus": "NDWI / superficie de agua · Sentinel-2 en Copernicus Data Space",
    "planetary_computer": "NDWI / superficie de agua · Sentinel-2 y Landsat en Planetary Computer",
    "gee": "Google Earth Engine (opcional, descartado por ahora: C-10)",
}

_IMPLEMENTED: dict[str, type[SatelliteProvider]] = {"mock": MockProvider}


class UnknownProviderError(ValueError):
    pass


def get_provider(name: str) -> SatelliteProvider:
    key = name.strip().lower()
    if key in _IMPLEMENTED:
        return _IMPLEMENTED[key]()
    if key in PLANNED_PROVIDERS:
        raise NotImplementedError(
            f"La fuente {key!r} está prevista para la Iteración 3: {PLANNED_PROVIDERS[key]}"
        )
    raise UnknownProviderError(f"Fuente satelital desconocida: {name!r}")
