# CLAUDE.md — Plataforma Hídrica Zulia

Tesis de Ingeniería en Informática (URBE, Maracaibo). Autores: Hunaldo Hernández y Angie Rubistein. Tutores: Miguel Vílchez y Maribel Ordóñez.

Plataforma web con Machine Learning y datos satelitales que predice la disponibilidad hídrica de los embalses **Tulé, Manuelote y Tres Ríos** (estado Zulia) para MINAGUAS. El sistema complementa al software que ya usa la institución, no lo reemplaza.

## Forma de trabajar (obligatoria)
- **XP por iteraciones.** Antes de cada iteración o historia se muestra un plan corto (historias, archivos, pruebas) y se **espera la aprobación** del usuario.
- Se escriben las pruebas primero cuando es posible: `pytest` en el backend y `vitest` en el frontend. Cada historia cierra con sus pruebas en verde.
- **Un commit por historia**, con un mensaje descriptivo en español.
- **No inventar datos reales, coordenadas ni fórmulas oficiales.** Lo que no esté confirmado se deja configurable y se anota en `docs/PENDIENTES.md`.
- **Toda desviación del prompt original** se registra en `docs/CAMBIOS-PROMPT.md`.
- La interfaz va en español de Venezuela. El código (identificadores) va en inglés; los comentarios y la documentación, en español.
- Este archivo se actualiza al cerrar cada iteración.

## Stack vigente
| Capa | Tecnología |
|---|---|
| Backend | Python **3.12** (con `uv`), FastAPI, Pydantic v2, SQLAlchemy 2, Alembic |
| Base de datos | **PostgreSQL 18.6 + PostGIS**, instalado localmente (servicio `postgresql-x64-18`, puerto 5432) |
| Tareas pesadas | Endpoints que se ejecutan **manualmente** desde la API, con `BackgroundTasks`. Sin Celery ni Redis. |
| ML | pandas, scikit-learn, XGBoost, **PyTorch** (LSTM), registro de modelos propio en PostgreSQL |
| Satélite | Interfaz `SatelliteProvider`: CHIRPS, ERA5-Land, Copernicus Data Space y Planetary Computer. **Sin servicios de Google** (no están disponibles en Venezuela). |
| Frontend | React + Vite + TypeScript, Tailwind, React Router, TanStack Query, ECharts |
| Mapa | Leaflet con OpenStreetMap o CARTO; capa satelital de Sentinel-2 Cloudless (EOX). **Sin Google Maps.** |
| Despliegue | Docker en la Iteración 7: frontend en Vercel y backend en un VPS o en un servidor institucional |

## Estructura
```
backend/   API FastAPI (app/api, core, models, schemas, services, jobs) + tests
ml/        data/{synthetic,raw,processed}, notebooks, src, models, reports
frontend/  React (se crea en HU-0.4)
docs/      tesis: historias, arquitectura, pendientes, cambios respecto al prompt
scripts/   utilidades (base de datos, verificaciones)
```

## Herramientas de IA del proyecto (`.claude/`)
- Skills: `ui-ux-pro-max` (global) para la UI del panel; `design-taste-frontend` solo para la página de inicio de sesión, una portada y el pulido visual, porque está pensada para sitios web de empresas y no para paneles; 10 weather-skills (CHIRPS, ERA5, SMAP, recorte, agregación, CSV, etc.) para **prototipar** la ingesta satelital.
- Agente: `data-scientist` para el análisis exploratorio y la revisión del backtesting.
- Cómo reinstalarlas: `docs/herramientas-ia.md`.

## Comandos frecuentes
- Verificación completa: `powershell -ExecutionPolicy Bypass -File scripts\check.ps1`
- Backend: `cd backend; uv run uvicorn app.main:app --reload` (http://localhost:8000/docs)
- Migraciones: `cd backend; uv run alembic upgrade head` (y con `APP_ENV=test` para la base de pruebas)
- Frontend: `cd frontend; npm run dev` (http://localhost:5173)
- Dataset sintético: `cd ml; uv run python -m hidrica_ml.synthetic`
- Base de datos (una sola vez): `scripts\db\setup_db.ps1`; verificar con `uv run --project backend python scripts/check_db.py`
- Conectividad satelital: `uv run --project backend python scripts/check_satellite_sources.py`
- uv está en `%LOCALAPPDATA%/Microsoft/WinGet/Packages/astral-sh.uv_*` y no siempre aparece en el PATH de la terminal.

## Notas técnicas
- `ruff` del backend: `alembic` está declarado como paquete de terceros (la carpeta `backend/alembic/` lo confundía).
- `httpx2` (sugerido por un aviso de Starlette) **no se instala**: es un paquete desconocido. Se mantiene `httpx`.
- Los `.ps1` se guardan en UTF-8 **con BOM** (PowerShell 5.1); el resto del repositorio en LF (`.gitattributes`).
- ARCO-ERA5 es demasiado lento (~7 min/día). Para la humedad del suelo se usa ERA5-Land del CDS (C-12).

## Estado
- **Iteración 0 (Exploración): ✅ cerrada el 2026-11-12.**
- **Iteración 1 (M1, M2, M3): ✅ cerrada el 2026-11-12.** Pruebas: 93 en el backend, 12 en ml y 23 en el frontend.
  - Usuarios de demostración: `uv run python -m app.cli demo-users` (contraseñas temporales; dominio `hidrica-zulia.com`, ficticio).
  - Curvas **sintéticas** cargadas en la base de desarrollo con `app.cli load-synthetic-curves`.
  - Pruebas del frontend: `tests/setup.ts` quita el `signal` de `Request` (incompatibilidad entre jsdom y undici con React Router).
  - El validador de correos rechaza los dominios `.test`, `.local` y `.example`: en pruebas se usa `@hidrica-zulia.com`.
- **Iteración 2 (M4, M12): ✅ cerrada el 2026-11-12.** Pruebas: 151 en el backend, 12 en ml y 31 en el frontend.
  - Datos de desarrollo: `app.cli load-synthetic-curves` y `app.cli load-synthetic-measurements` (histórico sintético hasta el 2026-10-15).
  - Ejemplos de importación en `ml/data/synthetic/ejemplos/` (regenerar con `cd ml; uv run python -m hidrica_ml.examples`).
  - El router `measurements` se registra ANTES que `reservoirs` (`/reservoirs/status` frente a `/reservoirs/{code}`).
  - Fórmulas M12 solo en `app/services/hydro_calcs.py`; reglas de calidad solo en `app/services/ingest.py::validate`.
  - El bundle del frontend pesa unos 520 kB: en la Iteración 5 se hará división por rutas (requisito de menos de 3 s).
- **Iteración 3 (M5): ✅ cerrada el 2026-11-12.** Pruebas: 176 en el backend (+1 con red opcional), 12 en ml y 35 en el frontend.
  - Geometrías: `app.cli load-geometries` (OSM provisional + área de influencia de 20 km). Copia en `backend/app/data/geo/embalses_osm.geojson`.
  - Descargas: `app.cli satellite --kind precipitacion|humedad_suelo|agua --from AAAA-MM-DD --to AAAA-MM-DD`, o desde la pantalla "Datos satelitales".
  - Cargado: CHIRPS y ERA5-Land 2005–2026; NDWI y superficie de agua desde 2025 (completar 2005–2024: P-31).
  - Windows: el `PROJ_LIB` de PostGIS rompe rasterio; `water.configure_proj()` fuerza el PROJ incluido en rasterio.
  - Open-Meteo limita el uso gratuito (429): se usa la media diaria y reintentos con espera.
  - Pruebas con red: `RUN_NETWORK_TESTS=1 uv run pytest tests/test_satellite.py`.
  - Heredocs muy largos en bash fallan en este entorno: para editar varios archivos, escribir un script .py en el scratchpad y ejecutarlo.
- **Siguiente:** Iteración 4 (M6 Machine Learning: features, XGBoost, LSTM, backtesting y registro de modelos), a la espera del plan y la aprobación.
