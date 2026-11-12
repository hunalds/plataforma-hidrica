"""Columnas de la plantilla de importación del movimiento diario de embalses (módulo M4).

El dataset sintético y los datos reales de MINAGUAS deben usar estas mismas columnas,
así el sistema reemplaza unos por otros sin cambiar código. Ver docs/PENDIENTES.md (P-05, P-19).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Column:
    name: str
    unit: str
    required: bool
    description: str


TEMPLATE_COLUMNS: tuple[Column, ...] = (
    Column("embalse", "", True, "Código del embalse: TULE, MANUELOTE o TRES_RIOS"),
    Column("fecha", "AAAA-MM-DD", True, "Fecha de la medición"),
    Column("hora", "HH:MM", True, "Hora de la lectura del limnímetro"),
    Column("cota_msnm", "m.s.n.m.", True, "Nivel del agua (cota) leído en la regla o limnímetro"),
    Column("volumen_hm3", "hm³", False, "Volumen almacenado; si falta, se calcula con la curva vigente"),
    Column("caudal_entrada_m3s", "m³/s", False, "Caudal de entrada (aporte de los ríos)"),
    Column("caudal_salida_m3s", "m³/s", False, "Caudal de salida/extracción hacia las plantas potabilizadoras"),
    Column("gasto_ecologico_m3s", "m³/s", False, "Caudal liberado al río aguas abajo"),
    Column("apertura_compuertas_pct", "%", False, "Apertura de compuertas"),
    Column("captacion_m3s", "m³/s", False, "Captación registrada (diferencia con la salida por confirmar, P-19)"),
    Column("observaciones", "", False, "Notas del operador"),
)

COLUMN_NAMES: tuple[str, ...] = tuple(c.name for c in TEMPLATE_COLUMNS)
REQUIRED_COLUMNS: tuple[str, ...] = tuple(c.name for c in TEMPLATE_COLUMNS if c.required)

# Conversión de caudal medio diario (m³/s) a volumen diario (hm³)
M3S_TO_HM3_PER_DAY = 86_400 / 1_000_000
