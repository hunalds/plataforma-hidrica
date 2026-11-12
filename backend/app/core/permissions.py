"""Matriz de roles y permisos (sección 6 del documento de requerimientos).

C = consultar (READ), G = gestionar (MANAGE), — = sin acceso (NONE).
Se aplica en el backend con la dependencia `require(module, access)`; el frontend solo la refleja.
"""

from __future__ import annotations

from enum import IntEnum, StrEnum

from app.models.user import Role


class Access(IntEnum):
    NONE = 0
    READ = 1
    MANAGE = 2


class Module(StrEnum):
    AUDIT = "M1_auditoria"
    USERS = "M2_usuarios"
    RESERVOIRS = "M3_embalses"
    HYDRO_INGEST = "M4_ingesta"
    SATELLITE = "M5_satelite"
    PREDICTION = "M6_prediccion"
    DASHBOARD = "M7_panel"
    MAP = "M8_mapa"
    ALERTS = "M9_alertas"
    REPORTS = "M10_reportes"
    HELP = "M11_ayuda"
    CALCS = "M12_calculos"


N, C, G = Access.NONE, Access.READ, Access.MANAGE

#                       Gerencia  Ingeniero  Operador
_MATRIX: dict[Module, tuple[Access, Access, Access]] = {
    Module.AUDIT:        (C, N, N),
    Module.USERS:        (G, N, N),
    Module.RESERVOIRS:   (C, G, C),
    Module.HYDRO_INGEST: (C, G, G),  # Operador: solo registro manual (se restringe en M4)
    Module.SATELLITE:    (C, G, N),
    Module.PREDICTION:   (C, G, N),
    Module.DASHBOARD:    (C, C, C),
    Module.MAP:          (C, C, C),
    Module.ALERTS:       (C, G, C),
    Module.REPORTS:      (G, G, N),
    Module.HELP:         (C, C, C),
    Module.CALCS:        (C, G, C),
}  # fmt: skip

_ROLE_INDEX = {Role.GERENCIA: 0, Role.INGENIERO: 1, Role.OPERADOR: 2}


def access_for(role: Role, module: Module) -> Access:
    return _MATRIX[module][_ROLE_INDEX[role]]


def can(role: Role, module: Module, needed: Access = Access.READ) -> bool:
    return access_for(role, module) >= needed


def permissions_for(role: Role) -> dict[str, str]:
    """Resumen para el frontend: {"M3_embalses": "MANAGE", ...} (solo módulos con acceso)."""
    return {m.value: access_for(role, m).name for m in Module if access_for(role, m) > Access.NONE}
