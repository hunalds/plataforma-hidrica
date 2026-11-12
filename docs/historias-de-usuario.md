# Historias de usuario

Formato XP: cada tarjeta tiene ID, rol, historia, prioridad, estimación (puntos: 1 punto ≈ medio día ideal), criterios de aceptación e iteración.

Estados: ⬜ pendiente · 🔄 en curso · ✅ terminada

---

## Iteración 0 — Exploración

### HU-0.1 · Repositorio y estructura ✅
- **Rol:** equipo de desarrollo
- **Historia:** Como equipo, quiero un repositorio con la estructura acordada para trabajar de forma ordenada y trazable.
- **Prioridad:** Alta · **Estimación:** 1
- **Criterios de aceptación:**
  - Repositorio Git local inicializado en la rama `main`.
  - Estructura de carpetas `backend/`, `ml/`, `docs/` y `scripts/`.
  - `.gitignore` que excluye secretos, datos crudos, modelos y dependencias.
  - `.env.example` con todas las variables previstas.
  - `CLAUDE.md`, `docs/PENDIENTES.md`, `docs/CAMBIOS-PROMPT.md` y `docs/herramientas-ia.md` creados.

### HU-0.2 · Entorno local de base de datos y Python ✅
- **Rol:** desarrollador
- **Historia:** Como desarrollador, quiero crear la base de datos con PostGIS y el entorno Python 3.12 con un script para que cualquiera pueda reproducir el entorno.
- **Prioridad:** Alta · **Estimación:** 1
- **Criterios de aceptación:**
  - Un script crea el usuario `hidrica_app`, las bases `plataforma_hidrica` y `plataforma_hidrica_test`, y la extensión PostGIS. Pide la contraseña de `postgres` sin guardarla.
  - `uv sync` instala las dependencias del backend con Python 3.12.

### HU-0.3 · Backend base con `/health` ✅
- **Rol:** sistema
- **Historia:** Como sistema, quiero un backend FastAPI con configuración, logs estructurados y `/health` para monitorear el servicio.
- **Prioridad:** Alta · **Estimación:** 2
- **Criterios de aceptación:**
  - `GET /health` devuelve 200 con el estado de la base y la versión de PostGIS.
  - Si la base no responde, devuelve 503 con un mensaje controlado.
  - Alembic queda inicializado, con una migración que activa PostGIS.

### HU-0.4 · Frontend base ✅
- **Rol:** usuario
- **Historia:** Como usuario, quiero un frontend en español que confirme la conexión con la API.
- **Prioridad:** Alta · **Estimación:** 2
- **Criterios de aceptación:**
  - Vite + React + TS + Tailwind + Router + TanStack Query.
  - La página de estado muestra "API conectada" o "Sin conexión".
  - Las pruebas de `vitest` pasan.

### HU-0.5 · Dataset sintético ✅
- **Rol:** analista
- **Historia:** Como analista, quiero un dataset sintético realista de los tres embalses para desarrollar sin los datos oficiales.
- **Prioridad:** Alta · **Estimación:** 2
- **Criterios de aceptación:**
  - Series diarias desde 2005 (Tulé y Manuelote) y desde 2008 (Tres Ríos).
  - Las columnas coinciden con la plantilla de importación de M4.
  - Las cotas se mantienen dentro de los rangos de referencia, con algunos días de alivio.
  - El dataset está marcado como SINTÉTICO.

### HU-0.6 · Prueba de fuentes satelitales ⬜
- **Rol:** ingeniero
- **Historia:** Como ingeniero, quiero verificar que las fuentes satelitales funcionan desde Venezuela antes de construir la ingesta.
- **Prioridad:** Alta · **Estimación:** 2
- **Criterios de aceptación:**
  - Interfaz `SatelliteProvider` con implementación simulada (`mock`) y pruebas.
  - Descarga real de un mes de CHIRPS y de humedad del suelo, recortada al estado Zulia.
  - Informe de la conectividad de cada fuente.

### HU-0.7 · Calidad local ⬜
- **Rol:** equipo de desarrollo
- **Historia:** Como equipo, quiero un script único de verificación para detectar errores antes de cada commit.
- **Prioridad:** Media · **Estimación:** 1
- **Criterios de aceptación:**
  - `scripts/check.ps1` ejecuta ruff, pytest, eslint y vitest.
  - El workflow de CI queda preparado pero inactivo.
