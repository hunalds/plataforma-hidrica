"""Cálculos operativos del balance hídrico (M12).

ÚNICO lugar donde viven las fórmulas. Todas están marcadas como **POR VALIDAR** con MINAGUAS
(docs/PENDIENTES.md, P-09 a P-13). Son funciones puras: reciben números y devuelven números,
sin tocar la base de datos, para poder probarlas y auditarlas fácilmente.

Unidades: cotas en m.s.n.m., volúmenes en hm³ (millones de m³), caudales en m³/s (media diaria).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

# 1 m³/s durante un día = 86 400 m³ = 0,0864 hm³
M3S_TO_HM3_PER_DAY = 86_400 / 1_000_000


def flow_to_hm3_per_day(flow_m3s: float | None) -> float:
    return (flow_m3s or 0.0) * M3S_TO_HM3_PER_DAY


# --------------------------------------------------------------------------- P-09 a P-12


def useful_volume(volume_hm3: float, dead_volume_hm3: float) -> float:
    """P-09 · Volumen útil = volumen actual − volumen muerto (nunca negativo)."""
    return max(0.0, volume_hm3 - dead_volume_hm3)


def useful_capacity(normal_volume_hm3: float, dead_volume_hm3: float) -> float:
    """Capacidad útil = volumen al nivel normal − volumen muerto."""
    return max(0.0, normal_volume_hm3 - dead_volume_hm3)


def availability_pct(useful_hm3: float, useful_capacity_hm3: float) -> float | None:
    """P-10 · Disponibilidad (%) = volumen útil / capacidad útil × 100.

    Puede superar 100 % cuando la cota está por encima del nivel normal (embalse aliviando).
    """
    if useful_capacity_hm3 <= 0:
        return None
    return useful_hm3 / useful_capacity_hm3 * 100


def reserve_days(useful_hm3: float, outflow_m3s: float | None, eco_flow_m3s: float | None) -> float | None:
    """P-11 · Días de reserva = volumen útil / (extracción diaria + gasto ecológico).

    Devuelve None si no hay salidas (la reserva no se agota con el consumo actual).
    """
    daily = flow_to_hm3_per_day(outflow_m3s) + flow_to_hm3_per_day(eco_flow_m3s)
    if daily <= 0:
        return None
    return useful_hm3 / daily


def spill_volume(volume_hm3: float, normal_volume_hm3: float) -> float:
    """P-12 · Alivio (hm³): volumen almacenado por encima del nivel normal (cota de aliviadero).

    Interpretación de la entrevista: "cuando la cota supera el nivel normal empieza a aliviar".
    El método oficial (curva del aliviadero) está pendiente de confirmar.
    """
    return max(0.0, volume_hm3 - normal_volume_hm3)


# --------------------------------------------------------------------------- P-13 balance


@dataclass(frozen=True)
class DailyBalance:
    inflow_hm3: float
    outflow_hm3: float
    eco_hm3: float
    net_hm3: float  # entradas − salidas − ecológico
    observed_change_hm3: float | None  # V(hoy) − V(ayer)
    spill_estimate_hm3: float  # alivio estimado del día (solo con cota sobre el nivel normal)
    residual_hm3: float | None  # observado − (neto − alivio): evaporación, filtraciones, errores de medición
    residual_pct_of_volume: float | None


def daily_balance(
    *,
    volume_today_hm3: float | None,
    volume_yesterday_hm3: float | None,
    inflow_m3s: float | None,
    outflow_m3s: float | None,
    eco_flow_m3s: float | None,
    level_m: float,
    normal_level_m: float,
) -> DailyBalance:
    """P-13 · Balance diario = entradas − salidas − gasto ecológico − alivio, comparado con ΔV observado.

    El alivio diario no se mide: se estima como el agua que "falta" en un día en que la cota está
    sobre el nivel normal (neto esperado − cambio observado, si es positivo). En días sin alivio,
    el residuo refleja evaporación, filtraciones y errores de medición.
    """
    inflow = flow_to_hm3_per_day(inflow_m3s)
    outflow = flow_to_hm3_per_day(outflow_m3s)
    eco = flow_to_hm3_per_day(eco_flow_m3s)
    net = inflow - outflow - eco

    observed = None
    if volume_today_hm3 is not None and volume_yesterday_hm3 is not None:
        observed = volume_today_hm3 - volume_yesterday_hm3

    spill = 0.0
    if observed is not None and level_m >= normal_level_m:
        spill = max(0.0, net - observed)

    residual = None if observed is None else observed - (net - spill)
    residual_pct = None
    if residual is not None and volume_today_hm3:
        residual_pct = residual / volume_today_hm3 * 100
    return DailyBalance(inflow, outflow, eco, net, observed, spill, residual, residual_pct)


# --------------------------------------------------------------------------- semáforo


class Light(StrEnum):
    GREEN = "verde"
    YELLOW = "amarillo"
    RED = "rojo"
    GRAY = "gris"  # sin datos


class Direction(StrEnum):
    NORMAL = "normal"
    SCARCITY = "escasez"
    FLOOD = "inundacion_alivio"


@dataclass(frozen=True)
class TrafficLight:
    light: Light
    direction: Direction
    reason: str  # explicación en lenguaje sencillo
    thresholds_defined: bool


def traffic_light(
    level_m: float | None,
    *,
    normal_level: float,
    dead_level: float,
    low_critical: float | None = None,
    low_alert: float | None = None,
    high_alert: float | None = None,
    spill_level: float | None = None,
) -> TrafficLight:
    """Verde = normal; amarillo = alerta; rojo = crítico o alivio (sección 5, M8).

    Si el Ingeniero aún no definió umbrales (P-02), se usan las cotas oficiales: sobre la cota
    normal → rojo (alivio); en o bajo el volumen muerto → rojo (escasez); resto → verde.
    """
    defined = any(v is not None for v in (low_critical, low_alert, high_alert, spill_level))
    if level_m is None:
        return TrafficLight(Light.GRAY, Direction.NORMAL, "Sin datos recientes", defined)

    crit_low = low_critical if low_critical is not None else dead_level
    spill = spill_level if spill_level is not None else normal_level

    if level_m <= crit_low:
        return TrafficLight(Light.RED, Direction.SCARCITY, "Nivel en zona crítica de escasez", defined)
    if level_m > spill:
        return TrafficLight(
            Light.RED, Direction.FLOOD, "El embalse está aliviando (nivel sobre el de alivio)", defined
        )
    if low_alert is not None and level_m <= low_alert:
        return TrafficLight(Light.YELLOW, Direction.SCARCITY, "Nivel bajo: alerta de escasez", defined)
    if high_alert is not None and level_m >= high_alert:
        return TrafficLight(
            Light.YELLOW, Direction.FLOOD, "Nivel alto: vigilancia por posible alivio", defined
        )
    return TrafficLight(Light.GREEN, Direction.NORMAL, "Nivel dentro del rango normal de operación", defined)


# --------------------------------------------------------------------------- resumen operativo


@dataclass(frozen=True)
class OperationalStatus:
    level_m: float
    volume_hm3: float
    dead_volume_hm3: float
    normal_volume_hm3: float
    useful_volume_hm3: float
    useful_capacity_hm3: float
    availability_pct: float | None
    reserve_days: float | None
    spill_hm3: float
    is_spilling: bool


def operational_status(
    *,
    level_m: float,
    volume_hm3: float | None,
    normal_level: float,
    dead_level: float,
    volume_at: Callable[[float], float],
    outflow_m3s: float | None,
    eco_flow_m3s: float | None,
) -> OperationalStatus:
    """Calcula todos los indicadores del día a partir de la cota y la curva (función volume_at)."""
    volume = volume_hm3 if volume_hm3 is not None else volume_at(level_m)
    dead_v = volume_at(dead_level)
    normal_v = volume_at(normal_level)
    useful = useful_volume(volume, dead_v)
    capacity = useful_capacity(normal_v, dead_v)
    return OperationalStatus(
        level_m=level_m,
        volume_hm3=volume,
        dead_volume_hm3=dead_v,
        normal_volume_hm3=normal_v,
        useful_volume_hm3=useful,
        useful_capacity_hm3=capacity,
        availability_pct=availability_pct(useful, capacity),
        reserve_days=reserve_days(useful, outflow_m3s, eco_flow_m3s),
        spill_hm3=spill_volume(volume, normal_v),
        is_spilling=level_m > normal_level,
    )
