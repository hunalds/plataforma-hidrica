# HU-0.6 · Verificación de fuentes satelitales y climáticas

**Fecha:** 2026-11-12 · **Red:** el equipo de desarrollo de los autores · **Script:** [`scripts/check_satellite_sources.py`](../../scripts/check_satellite_sources.py) · **Resultado en bruto:** [`conectividad-fuentes-2026-11-12.json`](conectividad-fuentes-2026-11-12.json)

## 1. Conectividad (petición HTTP anónima a cada catálogo)

| Fuente | Uso previsto | ¿Cuenta? | Resultado |
|---|---|---|---|
| CHIRPS · dynamical.org (STAC) | Precipitación diaria | No | ✅ HTTP 200 |
| CHIRPS · servidor UCSB (CHC) | Precipitación (alternativa) | No | ✅ HTTP 200 (lento, ~5 s) |
| Copernicus Data Space · STAC | NDWI / superficie de agua (Sentinel-2) | Sí, para descargar | ✅ HTTP 200 |
| Microsoft Planetary Computer · STAC | NDWI (Sentinel-2 y Landsat) | No | ✅ HTTP 200 |
| Copernicus Climate Data Store | Humedad del suelo (ERA5-Land) | Sí (gratuita) | ✅ HTTP 200 |
| NASA Earthdata CMR | Humedad del suelo (SMAP) | Sí, para descargar | ✅ HTTP 200 |
| ARCO-ERA5 · Google Cloud Storage | Humedad del suelo | No | ✅ HTTP 200 |
| EOX Sentinel-2 Cloudless | Mapa base satelital | No | ✅ HTTP 200 |
| OpenStreetMap | Mapa base de calles | No | ✅ HTTP 200 |
| Google Earth Engine (referencia) | — | Sí | ✅ HTTP 200 |

**Hallazgo:** desde esta red **los dominios de Google también responden**. La restricción que reportan los autores está en **abrir y usar la cuenta o el proyecto** (registro en Earth Engine o Google Cloud desde Venezuela), no en la red. Se mantiene la decisión C-10 de no depender de Google, pero queda constancia de que no es un bloqueo de red.

> Pendiente P-14: repetir esta verificación **desde la red de MINAGUAS**, ya que el servidor institucional puede tener otras restricciones.

## 2. Descarga real de prueba

Área: polígono del **estado Zulia** de Natural Earth (admin-1 `VEN / Zulia`, por medio de `weather-skills-core`). Recuadro derivado: N 11,85 / O −73,37 / S 8,36 / E −70,66. **No se usaron coordenadas inventadas.**

### CHIRPS (skills `chirps-fetch` + `clip-region`)
- Septiembre 2026 completo (30 días), producto *final*. El último día publicado era el 2026-11-05, en versión *preliminar*.
- **Tiempo de descarga: ~9 s.** Malla de 70 × 54 celdas de 0,05°, de las cuales **1.708 quedan dentro del polígono**.
- Precipitación media areal: **127,2 mm** en el mes, con un máximo diario de **12,9 mm** el 2026-09-28. Es coherente con la temporada de lluvias.
- ✅ **Viable** para la ingesta diaria y el backfill desde 2005 (disponible desde 1981).

### ERA5 humedad del suelo (skill `arco-era5-fetch`, capa 0–7 cm)
- 2026-09-01: 24 horas en una malla de 14 × 11 celdas de 0,25°. Media sobre el recuadro: **0,258 m³/m³** (rango horario 0,243–0,265).
- **Tiempo de descarga: ~7 minutos para UN día**, porque el almacén ARCO es horario y global y hay que leer muchos bloques.
- ❌ **No viable** para el backfill (unos 7.000 días ≈ semanas de descarga). Se usará **ERA5-Land diario agregado del Copernicus CDS** (cuenta gratuita), que además tiene más detalle (0,1°), o **SMAP** desde 2015.

## 3. Interfaz en el backend
`backend/app/services/satellite/`:
- `SatelliteProvider`: contrato común con `fetch(aoi, variable, start, end)` y `check()`.
- `Variable`: precipitación, humedad del suelo, superficie de agua y NDWI.
- `Quality`: buena, dudosa o sin dato, más el porcentaje de nubosidad.
- `MockProvider`: datos deterministas para desarrollo.
- `registry.get_provider()`: elige la fuente con `SATELLITE_PROVIDER` del `.env`.

Las fuentes reales se implementan en la Iteración 3. Hay 8 pruebas en `backend/tests/test_satellite_provider.py`.

## 4. Decisión para la Iteración 3

| Variable | Fuente principal | Respaldo |
|---|---|---|
| Precipitación | CHIRPS (dynamical.org) | CHIRPS (UCSB) |
| Humedad del suelo | ERA5-Land diario (Copernicus CDS) | SMAP (NASA, desde 2015) |
| NDWI / superficie de agua | Planetary Computer (sin cuenta, Sentinel-2 + Landsat) | Copernicus Data Space |

**Acción para los autores:** crear las cuentas gratuitas del **Copernicus Climate Data Store** y de **Copernicus Data Space** antes de la Iteración 3.
