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

### HU-0.6 · Prueba de fuentes satelitales ✅
- **Rol:** ingeniero
- **Historia:** Como ingeniero, quiero verificar que las fuentes satelitales funcionan desde Venezuela antes de construir la ingesta.
- **Prioridad:** Alta · **Estimación:** 2
- **Criterios de aceptación:**
  - Interfaz `SatelliteProvider` con implementación simulada (`mock`) y pruebas.
  - Descarga real de un mes de CHIRPS y de humedad del suelo, recortada al estado Zulia.
  - Informe de la conectividad de cada fuente.

### HU-0.7 · Calidad local ✅
- **Rol:** equipo de desarrollo
- **Historia:** Como equipo, quiero un script único de verificación para detectar errores antes de cada commit.
- **Prioridad:** Media · **Estimación:** 1
- **Criterios de aceptación:**
  - `scripts/check.ps1` ejecuta ruff, pytest, eslint y vitest.
  - El workflow de CI queda preparado pero inactivo.

---

## Iteración 1 — Esqueleto completo (M1, M2, M3)

### HU-1.1 · Inicio y cierre de sesión ✅
- **Rol:** todos · **Prioridad:** Alta · **Estimación:** 3
- **Historia:** Como usuario, quiero iniciar y cerrar sesión de forma segura para acceder solo a lo que me corresponde.
- **Criterios de aceptación:**
  - JWT de acceso (15 min) y de renovación (7 días) con rotación en cada uso.
  - Si se reutiliza un token de renovación ya usado, se cierran todas las sesiones del usuario.
  - La sesión se cierra tras 30 min de inactividad, tanto en el navegador como en el servidor.
  - Credenciales erróneas y correos inexistentes reciben el mismo mensaje genérico.
  - Contraseñas guardadas con Argon2id.

### HU-1.2 · Bloqueo y límite de intentos ✅
- **Rol:** sistema · **Prioridad:** Alta · **Estimación:** 1
- **Historia:** Como sistema, quiero bloquear la cuenta tras intentos fallidos para impedir ataques de fuerza bruta.
- **Criterios de aceptación:**
  - 5 intentos fallidos → bloqueo de 15 min (HTTP 423).
  - Máximo 10 intentos de inicio de sesión por minuto desde una misma IP (HTTP 429).
  - Un inicio de sesión correcto reinicia el contador.

### HU-1.3 · Primer acceso y recuperación de contraseña ✅
- **Rol:** todos · **Prioridad:** Alta · **Estimación:** 2
- **Historia:** Como usuario nuevo, quiero cambiar mi contraseña temporal y poder recuperarla por correo si la olvido.
- **Criterios de aceptación:**
  - Con contraseña temporal solo se permite cambiarla (403 `PASSWORD_CHANGE_REQUIRED` en el resto).
  - Política: 10 o más caracteres, letras y números, y distinta del correo.
  - El enlace de recuperación es de un solo uso, vence en 30 min y en la base solo se guarda su hash.
  - En desarrollo el correo se escribe en el log.

### HU-1.4 · Bitácora de auditoría ✅
- **Rol:** Gerencia · **Prioridad:** Alta · **Estimación:** 2
- **Historia:** Como Gerencia, quiero consultar quién hizo qué y cuándo para tener trazabilidad completa.
- **Criterios de aceptación:**
  - Cada registro guarda usuario, acción, entidad, valor anterior y nuevo, fecha y hora, e IP.
  - Filtros por acción y fechas, con paginación. Nunca se guardan contraseñas.
  - Solo Gerencia la consulta.

### HU-1.5 · Gestión de usuarios y roles ✅
- **Rol:** Gerencia · **Prioridad:** Alta · **Estimación:** 3
- **Historia:** Como Gerencia, quiero crear usuarios, asignar su rol y sus embalses, y activar o desactivar su acceso.
- **Criterios de aceptación:**
  - La contraseña temporal se muestra una sola vez.
  - Desactivar a un usuario o cambiarle el rol cierra sus sesiones de inmediato.
  - Nadie puede desactivarse ni quitarse el rol a sí mismo.
  - La matriz de permisos de la sección 6 se aplica en el backend (403).

### HU-1.6 · Ficha de embalses, umbrales y polígonos ✅
- **Rol:** Ingeniero · **Prioridad:** Alta · **Estimación:** 3
- **Historia:** Como Ingeniero, quiero mantener la ficha y los umbrales de cada embalse para que el semáforo y las alertas usen valores correctos.
- **Criterios de aceptación:**
  - La carga inicial crea los 3 embalses con sus cotas oficiales.
  - Umbrales en orden: crítico bajo < alerta baja < alerta alta < alivio; el crítico no puede estar por debajo del volumen muerto.
  - Polígonos en GeoJSON validados con PostGIS (WGS84).
  - Gerencia ve todos los embalses; Ingeniero y Operador solo los asignados.

### HU-1.7 · Curva cota–área–volumen versionada ✅
- **Rol:** Ingeniero · **Prioridad:** Alta · **Estimación:** 3
- **Historia:** Como Ingeniero, quiero cargar la curva desde CSV o Excel con fecha de vigencia para convertir cotas en volúmenes.
- **Criterios de aceptación:**
  - Errores reportados por fila y plantilla descargable.
  - Cada carga crea una nueva versión; la vigente se elige según la fecha.
  - Interpolación lineal en ambos sentidos (cota a volumen y volumen a cota).
  - Volumen muerto, volumen normal y capacidad útil se calculan con la curva vigente.

### HU-1.8 · Interfaz con inicio de sesión y navegación por rol ✅
- **Rol:** todos · **Prioridad:** Alta · **Estimación:** 3
- **Historia:** Como usuario, quiero iniciar sesión y ver solo los módulos de mi rol, desde PC, tableta o teléfono.
- **Criterios de aceptación:**
  - Pantallas de inicio de sesión, recuperación, restablecimiento y cambio obligatorio de contraseña.
  - Menú lateral en escritorio y desplegable en móvil.
  - Embalses (lista y ficha con umbrales y curvas), Usuarios y Bitácora (solo Gerencia).
  - La sesión se renueva sola si el token vence.
