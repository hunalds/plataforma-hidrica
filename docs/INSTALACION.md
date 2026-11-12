# Instalación en una PC nueva (Windows)

Guía paso a paso para clonar el repositorio y dejar la plataforma funcionando en otra computadora. Para producción con Docker o Vercel, ver [manual-tecnico.md](manual-tecnico.md#5-despliegue).

Tiempo estimado: 45–60 minutos, la mayor parte en descargas.

---

## 1. Programas que hay que instalar

| Programa | Versión usada en el desarrollo | Para qué | Cómo instalar |
|---|---|---|---|
| **Git** | 2.55 | Clonar el repositorio | `winget install Git.Git` |
| **PostgreSQL** | **18.6** | Base de datos | Instalador de EDB: <https://www.enterprisedb.com/downloads/postgres-postgresql-downloads> |
| **PostGIS** | **3.6** (para PG 18) | Datos geográficos (polígonos, mapas) | **Stack Builder**, que se abre al terminar el instalador de PostgreSQL: *Spatial Extensions → PostGIS 3.6 Bundle for PostgreSQL 18* |
| **uv** | 0.13 | Instala Python 3.12 y las librerías del backend y del ML | `winget install astral-sh.uv` |
| **Node.js** | 24 (sirve 22 o más reciente) | Frontend (React + Vite) | `winget install OpenJS.NodeJS.LTS` |
| pgAdmin 4 *(opcional)* | — | Ver la base de datos con una interfaz gráfica | Viene con el instalador de PostgreSQL |
| VS Code *(opcional)* | — | Editor | `winget install Microsoft.VisualStudioCode` |

> **No hace falta instalar Python a mano.** `uv` descarga Python 3.12 por su cuenta, porque las librerías de ML todavía no soportan Python 3.14. Si la PC ya tiene otro Python, no hay conflicto.

Al instalar PostgreSQL:
- **Anota la contraseña del usuario `postgres`.** El script de la base la pide una sola vez.
- Deja el puerto **5432**.
- Instala PostGIS con Stack Builder antes de seguir.

Después de instalar todo, **cierra y vuelve a abrir la terminal** para que `git`, `uv`, `node` y `npm` queden en el PATH. Comprueba las versiones:

```powershell
git --version; uv --version; node -v; npm -v
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" --version
```

Si `uv` no se reconoce, agrega al PATH la carpeta `%LOCALAPPDATA%\Microsoft\WinGet\Packages\astral-sh.uv_...`, o reinicia la sesión de Windows.

---

## 2. Clonar el repositorio y configurar

```powershell
cd $HOME\Documents
git clone <URL-DEL-REPOSITORIO> plataforma-hidrica
cd plataforma-hidrica
copy .env.example .env
notepad .env
```

En `.env` (**nunca** en `.env.example`) completa al menos:

| Variable | Valor |
|---|---|
| `DB_PASSWORD` | Una contraseña nueva para el usuario `hidrica_app` de la base (mínimo 8 caracteres). **No** es la contraseña de `postgres`. |
| `JWT_SECRET` | Una cadena aleatoria de 32 caracteres o más. Genera una con: `uv run python -c "import secrets; print(secrets.token_urlsafe(48))"` |

El resto se puede dejar como está. SMTP y Telegram son opcionales: ver la sección 6.

---

## 3. Base de datos

```powershell
powershell -ExecutionPolicy Bypass -File scripts\db\setup_db.ps1
```

El script pide la contraseña de `postgres` y no la guarda. Luego crea:
- el usuario `hidrica_app`, con la `DB_PASSWORD` del `.env`;
- las bases `plataforma_hidrica` (desarrollo) y `plataforma_hidrica_test` (pruebas automáticas);
- la extensión PostGIS en las dos bases.

---

## 4. Dependencias del proyecto

```powershell
# Backend + paquete de ML (Python 3.12, FastAPI, XGBoost, PyTorch, rasterio, ReportLab…)
cd backend
uv sync                      # la primera vez descarga varios cientos de MB (PyTorch); tarda unos minutos
uv run alembic upgrade head  # tablas de la base de desarrollo
$env:APP_ENV="test"; uv run alembic upgrade head; Remove-Item Env:APP_ENV   # tablas de la base de pruebas
cd ..

# ML (solo si vas a trabajar directamente en ml/ o correr sus pruebas)
cd ml; uv sync; cd ..

# Frontend (React, Vite, Tailwind, ECharts, Leaflet…)
cd frontend
npm ci
npx playwright install chromium   # solo para las pruebas E2E y las capturas
cd ..
```

Las versiones exactas de las librerías están fijadas en `backend/uv.lock`, `ml/uv.lock` y `frontend/package-lock.json`. `uv sync` y `npm ci` instalan exactamente esas versiones.

---

## 5. Datos de demostración y arranque

Los modelos entrenados (`ml/models/`) y los datos crudos **no están en el repositorio**: se regeneran en la PC nueva.

```powershell
cd backend
uv run python -m app.cli seed                          # los tres embalses
uv run python -m app.cli demo-users                    # un usuario por rol (muestra las contraseñas temporales)
uv run python -m app.cli load-synthetic-curves         # curvas cota-volumen SINTÉTICAS
uv run python -m app.cli load-synthetic-measurements   # histórico SINTÉTICO 2005–2026
uv run python -m app.cli load-geometries               # polígonos de los embalses (copia local de OSM)
uv run python -m app.cli load-synthetic-satellite      # lluvia, humedad y agua SINTÉTICAS
uv run python -m app.cli train-models --report         # entrena los modelos (varios minutos con el LSTM)
```

Para probar más rápido, sin el LSTM: `uv run python -m app.cli train-models --kinds persistencia estacional xgboost`.

Arranque (dos terminales):

```powershell
# Terminal 1 · API  → http://localhost:8000/docs
cd backend; uv run uvicorn app.main:app --reload

# Terminal 2 · Web  → http://localhost:5173
cd frontend; npm run dev
```

Entra con uno de los usuarios que mostró `demo-users`. El primer acceso pide cambiar la contraseña.

---

## 6. Opcional: notificaciones reales

| Canal | Variables en `.env` | Notas |
|---|---|---|
| Telegram | `TELEGRAM_BOT_TOKEN` | Crea un bot con @BotFather. El destinatario se identifica con su `chat_id`. |
| Correo (p. ej. Gmail) | `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`, `SMTP_USER`, `SMTP_PASSWORD` (contraseña de aplicación), `SMTP_FROM` | Sin SMTP, los correos solo se escriben en la consola de uvicorn. |

Reinicia uvicorn después de cambiar el `.env`.

---

## 7. Verificar que todo quedó bien

```powershell
powershell -ExecutionPolicy Bypass -File scripts\check.ps1      # lint + pruebas de backend, ML y frontend
cd frontend; npx playwright test                                 # opcional: 8 pruebas E2E en el navegador
```

`check.ps1` debe terminar con **"Todo en verde."**. Las pruebas del backend tardan unos 10 minutos.

---

## 8. Problemas frecuentes en una PC nueva

| Problema | Solución |
|---|---|
| `uv` o `npm` no se reconocen | Cierra y abre la terminal, o reinicia la sesión de Windows. |
| `setup_db.ps1`: "no se puede cargar el archivo… scripts deshabilitados" | Ejecútalo como se indica arriba, con `-ExecutionPolicy Bypass`. |
| `setup_db.ps1`: "extension postgis is not available" | Falta PostGIS: instálalo con Stack Builder (sección 1). |
| `/health` responde 503 o "database: error" | El servicio `postgresql-x64-18` está detenido, o `DB_PASSWORD` en `.env` no coincide. Revisa `services.msc`. |
| `uv sync` falla al descargar PyTorch | Conexión lenta: vuelve a ejecutar `uv sync`, que continúa donde quedó. |
| Error de PROJ al descargar datos satelitales reales | No definas `PROJ_LIB` a mano; el sistema lo corrige solo. |
| El puerto 5432, 8000 o 5173 está ocupado | Cambia `DB_PORT` en `.env`, usa `uvicorn ... --port 8001` o `npm run dev -- --port 5174`. Si cambias el puerto de la API, actualiza también `VITE_API_URL` y `CORS_ORIGINS`. |

---

## 9. Herramientas de IA (opcional, solo para seguir desarrollando con Claude Code)

El agente `data-scientist` ya viene en `.claude/agents/`. Las skills (taste-skill, weather-skills, ui-ux-pro-max) no se versionan; se reinstalan siguiendo [herramientas-ia.md](herramientas-ia.md).
