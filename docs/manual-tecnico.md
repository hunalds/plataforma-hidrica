# Manual técnico · Plataforma Hídrica Zulia

Para administradores y desarrolladores que instalan, despliegan o mantienen la plataforma.

Documentos relacionados:

| Tema | Documento |
|---|---|
| Diagramas de componentes, despliegue, entidad-relación y secuencias | [arquitectura.md](arquitectura.md) |
| Tablas y columnas | [diccionario-datos.md](diccionario-datos.md) |
| Endpoints | [api/endpoints.md](api/endpoints.md) y [api/openapi.json](api/openapi.json) |
| Modelos de predicción | [../ml/reports/backtesting.md](../ml/reports/backtesting.md) |
| Valores por confirmar | [PENDIENTES.md](PENDIENTES.md) |
| Desviaciones del prompt original | [CAMBIOS-PROMPT.md](CAMBIOS-PROMPT.md) |

---

## 1. Componentes

| Carpeta | Contenido | Tecnología |
|---|---|---|
| `backend/` | API REST, servicios, migraciones, CLI | Python 3.12, FastAPI, SQLAlchemy 2, Alembic, GeoAlchemy2 |
| `ml/` | Paquete `hidrica_ml`: dataset sintético, features, modelos, backtesting | pandas, XGBoost, PyTorch |
| `frontend/` | Aplicación web | React 19, Vite, TypeScript, Tailwind 4, TanStack Query, ECharts, Leaflet |
| `scripts/` | Base de datos, verificación, respaldo, rendimiento, documentación | PowerShell, sh, Python |
| `docs/` | Documentación de la tesis | Markdown y Mermaid |

Base de datos: **PostgreSQL 18 + PostGIS 3.6**.
- `plataforma_hidrica`: desarrollo y producción.
- `plataforma_hidrica_test`: pruebas automáticas y E2E. **Se vacía en cada prueba.**

---

## 2. Instalación local (Windows, desarrollo)

### 2.1 Requisitos
- PostgreSQL 18 con PostGIS (Stack Builder), servicio `postgresql-x64-18`, puerto 5432.
- `uv`: `winget install astral-sh.uv`. uv instala Python 3.12 por su cuenta.
- Node.js 20 o superior.

### 2.2 Pasos
```powershell
# 1. Configuración
copy .env.example .env      # completar DB_PASSWORD y JWT_SECRET (≥ 32 caracteres aleatorios)

# 2. Base de datos (una sola vez): crea el usuario hidrica_app, las dos bases y PostGIS.
#    Pide la contraseña de postgres de forma interactiva; no la guarda.
powershell -ExecutionPolicy Bypass -File scripts\db\setup_db.ps1

# 3. Backend
cd backend
uv sync
uv run alembic upgrade head
$env:APP_ENV="test"; uv run alembic upgrade head; Remove-Item Env:APP_ENV
uv run python -m app.cli seed
uv run python -m app.cli demo-users            # un usuario por rol, con contraseña temporal
uv run uvicorn app.main:app --reload           # http://localhost:8000/docs

# 4. Frontend (otra terminal)
cd frontend
npm ci
npm run dev                                    # http://localhost:5173
```

> **Contraseñas:** la contraseña real de la base va **solo** en `.env`, que está en `.gitignore`. `.env.example` lleva valores de ejemplo y sí se versiona.

### 2.3 Datos de demostración (SINTÉTICOS)
```powershell
cd backend
uv run python -m app.cli load-synthetic-curves
uv run python -m app.cli load-synthetic-measurements --until 2026-10-15
uv run python -m app.cli load-geometries               # polígonos OSM provisionales + área de influencia de 20 km
uv run python -m app.cli load-synthetic-satellite      # lluvia, humedad y agua sintéticas coherentes
uv run python -m app.cli train-models --report         # backtesting + modelos + ml/reports/backtesting.md
```
El entrenamiento completo, con el LSTM, tarda varios minutos. Para probar rápido: `--kinds persistencia estacional`.

---

## 3. Comandos de administración (CLI)

`uv run python -m app.cli <comando>`, desde `backend/`. Con Docker: `docker compose exec backend python -m app.cli <comando>`.

| Comando | Uso |
|---|---|
| `seed` | Crea los tres embalses (idempotente). |
| `create-user --email E --name N --role GERENCIA\|INGENIERO\|OPERADOR [--reservoirs TULE ...]` | Crea un usuario con contraseña temporal; el usuario la cambia en su primer acceso. |
| `create-user ... --password X` | Contraseña fija, sin cambio obligatorio. **Solo desarrollo y pruebas**: se rechaza con `APP_ENV=production`. |
| `demo-users` | Un usuario de demostración por rol. |
| `load-synthetic-curves`, `load-synthetic-measurements`, `load-synthetic-satellite` | Datos **sintéticos**, solo para desarrollo. |
| `load-geometries [--influence-km 20] [--force]` | Polígonos OSM provisionales. `--force` reemplaza también los que cargó un usuario. |
| `satellite --kind precipitacion\|humedad_suelo\|agua --from AAAA-MM-DD --to AAAA-MM-DD` | Descarga de datos satelitales reales (CHIRPS, ERA5-Land vía Open-Meteo, Planetary Computer). |
| `train-models [--reservoirs ...] [--kinds ...] [--test-years ...] [--fast] [--report]` | Backtesting y entrenamiento; activa el modelo de menor error. |

**Tareas periódicas sugeridas** (cron del servidor; la aplicación no tiene programador, ver C-08):
```cron
# Satélite: últimos 10 días, todas las mañanas
30 6 * * *  docker compose exec -T backend python -m app.cli satellite --kind precipitacion --from $(date -d '-10 day' +\%F) --to $(date +\%F)
45 6 * * *  docker compose exec -T backend python -m app.cli satellite --kind humedad_suelo --from $(date -d '-10 day' +\%F) --to $(date +\%F)
# Reentrenamiento mensual
0 3 1 * *   docker compose exec -T backend python -m app.cli train-models
```

---

## 4. Variables de entorno

Todas están en `.env.example`, con comentarios. Las principales:

| Variable | Descripción |
|---|---|
| `APP_ENV` | `development`, `test` o `production`. En producción: logs en JSON, sin `--password` y con `JWT_SECRET` obligatorio. |
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_NAME_TEST` | Conexión a PostgreSQL. |
| `JWT_SECRET`, `JWT_ACCESS_MINUTES` (15), `JWT_REFRESH_DAYS` (7) | Tokens de sesión. |
| `CORS_ORIGINS` | Orígenes del frontend, separados por comas. No hace falta si se sirve por el proxy `/api`. |
| `VITE_API_URL` | URL del backend vista desde el navegador: `/api` con Docker propio, o la URL pública del backend con Vercel. |
| `FRONTEND_URL` | Base de los enlaces de los correos (recuperación y alertas). |
| `ML_SATELLITE_SOURCE` | `sintetico` o `real`. |
| `SATELLITE_PROVIDER` | Proveedor del NDWI: `planetary_computer`, `copernicus`, `gee` o `mock`. |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | Correo saliente. Si están vacíos, los correos se escriben en el log. |
| `TELEGRAM_BOT_TOKEN` | Bot de Telegram para las alertas. Si está vacío, el canal queda "omitido". |
| `ALERT_PROJECTION_DAYS` (30), `ALERT_PROBABILITY` (0,5) | Parámetros de las alertas proyectadas. |
| `HTTP_PORT`, `WEB_WORKERS`, `DOMINIO`, `BACKUP_KEEP_DAYS`, `BACKUP_HOUR` | Producción con Docker. |

---

## 5. Despliegue

> **Estado:** los archivos de despliegue están escritos y revisados, pero **no se han ejecutado**, porque Docker no estaba instalado en el equipo de desarrollo y no hay cuentas de VPS ni Vercel (P-32). El primer despliegue debe seguir esta sección y anotar cualquier ajuste.

### 5.1 Opción A: servidor institucional o VPS con Docker Compose (recomendada)
Requisitos: Linux con Docker Engine y el plugin Compose, 2 vCPU, 4 GB de RAM (el LSTM entrena en CPU) y 20 GB de disco.

```bash
git clone <repositorio> plataforma-hidrica && cd plataforma-hidrica
cp .env.example .env
#   APP_ENV=production · DB_PASSWORD y JWT_SECRET aleatorios · VITE_API_URL=/api · FRONTEND_URL=https://DOMINIO
docker compose up -d --build                         # db, backend (migra al arrancar), frontend, backup
docker compose exec backend python -m app.cli seed
docker compose exec backend python -m app.cli create-user --email gerencia@... --name "..." --role GERENCIA
# HTTPS automático (Let's Encrypt) con Caddy: DOMINIO=... en .env y puertos 80/443 abiertos
docker compose --profile https up -d
```

- **Servicios:**
  - `db`: PostGIS, sin puertos publicados.
  - `backend`: uvicorn con usuario sin privilegios; ejecuta `alembic upgrade head` al arrancar.
  - `frontend`: nginx con los archivos estáticos y el proxy `/api` hacia el backend.
  - `backup`: respaldo diario.
  - `caddy`: opcional.
- **Comprobación:** `curl http://localhost:8080/api/health` debe responder `"database": "ok"`.
- **Actualizar:** `git pull && docker compose up -d --build`. Las migraciones corren solas.

### 5.2 Opción B: frontend en Vercel y backend en VPS
1. El backend se despliega en el VPS como en la opción A. Se puede dejar el servicio `frontend` o no.
2. En Vercel, importa el repositorio con **Root Directory = `frontend`**. `frontend/vercel.json` ya define la compilación, la reescritura para la SPA y las cabeceras de seguridad.
3. En Vercel, define la variable `VITE_API_URL=https://api.DOMINIO`.
4. En el `.env` del backend: `CORS_ORIGINS=https://<proyecto>.vercel.app` y `FRONTEND_URL` con la misma URL.

Si las normativas exigen que los datos residan en la institución (P-16), usa la opción A.

### 5.3 Producción sin Docker (servidor institucional con Windows)
Repite la sección 2 con `APP_ENV=production`, compila el frontend con `npm run build` y sirve `frontend/dist` con IIS o nginx, con un proxy `/api` hacia `uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2 --proxy-headers`, registrado como servicio (por ejemplo, con NSSM).

---

## 6. Respaldo y restauración

| Entorno | Respaldo | Restauración |
|---|---|---|
| Docker | Servicio `backup`: `pg_dump -Fc` diario a la hora `BACKUP_HOUR`, en `./backups/`, con retención de `BACKUP_KEEP_DAYS` días | `docker compose exec -T backup sh -c 'pg_restore --clean --if-exists --no-owner -d "$PGDATABASE" /backups/ARCHIVO.dump'` |
| Linux sin Docker | `scripts/backup/backup_db.sh` (con las variables `PG*`) | `scripts/backup/restore_db.sh ARCHIVO.dump` (pide escribir **SI**) |
| Windows local | `scripts\backup\backup_local.ps1` (Programador de tareas) | `pg_restore --clean --if-exists --no-owner -d plataforma_hidrica ARCHIVO.dump` |

Copia los respaldos **fuera del servidor**: otro equipo o almacenamiento institucional. Los modelos entrenados (`ml/models`, volumen `mlmodels`) se pueden regenerar con `train-models`, pero conviene respaldarlos también. Falta ensayar la restauración y medir su duración (P-33).

---

## 7. Calidad y pruebas

```powershell
powershell -ExecutionPolicy Bypass -File scripts\check.ps1     # ruff + pytest (backend, ml) + eslint + tsc + vitest
cd frontend; npx playwright install chromium; npx playwright test            # E2E: escritorio y teléfono
$env:CAPTURAS=1; npx playwright test e2e/capturas.spec.ts --project=escritorio   # regenera docs/capturas
cd backend; uv run python ../scripts/perf/dashboard_perf.py                  # tiempos del panel y la ficha
cd backend; $env:PYTHONPATH="."; uv run python ../scripts/docs/generate_docs.py   # diccionario y referencia de la API
```

| Conjunto | Pruebas | Notas |
|---|---|---|
| Backend (pytest) | ~205 | Usa la base `plataforma_hidrica_test`. `RUN_NETWORK_TESTS=1` activa la prueba con red. |
| ML (pytest) | 25 | Sin base de datos. |
| Frontend (vitest) | 48 | jsdom; el mapa y las gráficas se sustituyen por versiones simuladas. |
| E2E (Playwright) | 8 | 4 flujos × escritorio y teléfono. Levanta el backend en el puerto 8010 y Vite en el 5180. |

Rendimiento medido en la API (datos sintéticos de 21 años): panel 151 ms y ficha 249 ms (`docs/evidencias/`).

---

## 8. Seguridad

- **Contraseñas:** Argon2id, con un mínimo de 10 caracteres. Bloqueo de 15 min tras 5 intentos fallidos.
- **JWT:** token de acceso de 15 min y de renovación de 7 días, con rotación y detección de reuso. `token_version` invalida todas las sesiones al cambiar la contraseña, el rol o el estado del usuario.
- **Permisos:** matriz declarativa en `backend/app/core/permissions.py`, aplicada en el backend. El frontend solo oculta opciones.
- **Bitácora:** cada cambio queda registrado con el usuario, la IP, el valor anterior y el nuevo.
- **Secretos:** solo en `.env`, nunca en Git. Los errores 503 no muestran detalles del driver.
- **Cabeceras:** nginx y Vercel envían `nosniff`, `X-Frame-Options: DENY` y `Referrer-Policy`.
- **Pendiente (P-22):** guardar el token de renovación en una cookie `httpOnly` cuando estén definidos los dominios.

---

## 9. Solución de problemas

| Síntoma | Causa y solución |
|---|---|
| `uv` no se reconoce | Abre una terminal nueva, o agrega `%LOCALAPPDATA%\Microsoft\WinGet\Packages\astral-sh.uv_*` al PATH. |
| `/health` responde 503 | PostgreSQL está detenido o `DB_PASSWORD` es incorrecta. Revisa el servicio `postgresql-x64-18` y el `.env`. |
| Error de PROJ al calcular el NDWI en Windows | El `PROJ_LIB` de PostGIS entra en conflicto. `water.configure_proj()` lo corrige; no definas `PROJ_LIB` a mano. |
| Open-Meteo responde 429 | Límite del plan gratuito. Espera, o descarga rangos más cortos; hay reintentos automáticos. |
| El nombre del archivo descargado es genérico | Falta exponer `Content-Disposition` en CORS (ya corregido en `main.py`). Revisa los proxies intermedios. |
| Una prueba de pytest falla después de correr las E2E | Las E2E siembran la base de pruebas. `conftest.py` la vacía antes de cada prueba; actualiza el repositorio. |
