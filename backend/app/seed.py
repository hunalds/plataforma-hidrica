"""Datos iniciales: los tres embalses con sus cotas de referencia oficiales.

Fuente: entrevista al Director Estadal Zulia de MINAGUAS (2026-11-11), sección 3.2 del documento
de requerimientos. Unidades por confirmar (P-01). Los polígonos NO se cargan aquí: los suben los
autores como GeoJSON (P-07, P-08). La misma información está en ml/config/embalses.json.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.models.reservoir import Reservoir, Threshold

RESERVOIRS = [
    {
        "code": "TULE",
        "name": "Tulé",
        "records_start": date(2005, 1, 1),
        "normal_level": 33.40,
        "dead_level": 26.60,
    },
    {
        "code": "MANUELOTE",
        "name": "Manuelote",
        "records_start": date(2005, 1, 1),
        "normal_level": 48.00,
        "dead_level": 36.10,
    },
    {
        "code": "TRES_RIOS",
        "name": "Tres Ríos",
        "records_start": date(2008, 1, 1),
        "normal_level": 180.00,
        "dead_level": 139.50,
    },
]


def seed_reservoirs(session: Session) -> list[str]:
    """Crea los embalses que falten (no sobrescribe cambios hechos por el Ingeniero). Devuelve los creados."""
    created = []
    for data in RESERVOIRS:
        if session.get(Reservoir, data["code"]) is None:
            r = Reservoir(**data)
            r.thresholds = Threshold()  # umbrales vacíos: los define el Ingeniero (P-02)
            session.add(r)
            created.append(data["code"])
    session.flush()
    return created
