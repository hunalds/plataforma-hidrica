# ⚠️ Dataset SINTÉTICO — no son datos reales

Los archivos de esta carpeta se **generan artificialmente** con [`ml/src/synthetic.py`](../../src/synthetic.py) para desarrollar y probar la plataforma mientras llegan los históricos oficiales de MINAGUAS. **No deben citarse como mediciones de los embalses** ni usarse para conclusiones de la tesis sobre los embalses reales.

## Archivos

| Archivo | Contenido |
|---|---|
| `movimiento_diario_sintetico.csv` | Registro diario con las **mismas columnas que la plantilla de importación** ([`ml/src/schema.py`](../../src/schema.py)). Tulé y Manuelote desde 2005-01-01 y Tres Ríos desde 2008-01-01, hasta 2026-10-31. |
| `verdad_sintetica.csv` | Variables ocultas de la simulación que no se miden en sitio: volumen exacto, **alivio**, **evaporación** y área. Sirve para validar los cálculos de M12 y los modelos de M6. |
| `curva_cota_volumen_<embalse>_sintetica.csv` | Curva cota–área–volumen **inventada** (forma potencial). La reemplazará la curva oficial (P-03). |
| `metadata.json` | Semilla, versión del generador, rango de fechas y la marca `"SINTETICO": true` |

## Cómo se genera

```bash
cd ml
uv run python -m src.synthetic --seed 2026 --end 2026-10-31
```

Con la misma semilla siempre se obtiene el mismo resultado.

## Qué es real y qué es inventado

| Elemento | Origen |
|---|---|
| Cota normal y cota de volumen muerto | **Entrevista a MINAGUAS** (2026-11-11). Unidades por confirmar (P-01). |
| Inicio de los registros (2005 / 2008) | **Entrevista a MINAGUAS** |
| Volumen al nivel normal, cota de fondo, forma de la curva | Inventado (`ml/config/embalses.json`, bloque `sintetico`) |
| Caudales medios, extracción, gasto ecológico | Inventado, en órdenes de magnitud plausibles |
| Régimen de lluvias bimodal (abr–may y sep–nov) | Patrón climático general del Zulia, de forma cualitativa; **no** es una serie observada |
| Evaporación de 3 a 6 mm/día | Supuesto genérico para el trópico |

## Comportamientos incluidos (para probar el sistema)
- **Alivio**: el embalse supera el nivel normal en temporada de lluvias.
- **Años secos**: descensos fuertes, con **racionamiento** de la extracción cerca del volumen muerto (sobre todo en Tulé).
- **Balance hídrico** cerrado: ΔV = (entrada − salida − ecológico)·0,0864 − evaporación − alivio.

Para probar el control de calidad (M4), en la Iteración 2 se generará una variante con errores introducidos a propósito: duplicados, días faltantes, valores fuera de rango y saltos bruscos.
