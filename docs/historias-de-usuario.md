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

---

## Iteración 2 — Datos (M4 ingesta hidrológica, M12 cálculos operativos)

### HU-2.1 · Modelo del movimiento diario ✅
- **Rol:** sistema · **Prioridad:** Alta · **Estimación:** 1
- **Historia:** Como sistema, quiero guardar un registro por embalse y día con la cota, el volumen y los caudales para tener el histórico completo.
- **Criterios de aceptación:**
  - Tabla `daily_measurements` con unicidad (embalse, día).
  - Se guarda el origen del volumen (reportado o calculado con la curva) y la versión de curva usada.
  - Banderas de calidad, origen del dato (manual, importado o SQL) y lote de importación.

### HU-2.2 · Cálculos operativos (M12) ✅
- **Rol:** Ingeniero · **Prioridad:** Alta · **Estimación:** 2
- **Historia:** Como Ingeniero, quiero que el sistema calcule el volumen útil, la disponibilidad, los días de reserva, el alivio y el balance diario con fórmulas documentadas.
- **Criterios de aceptación:**
  - Las fórmulas viven en un único módulo (`hydro_calcs.py`) con pruebas unitarias.
  - Están marcadas como POR VALIDAR (P-09 a P-13).
  - El alivio estimado por el balance coincide (±15 %) con el alivio simulado en el dataset sintético.

### HU-2.3 · Control de calidad ✅
- **Rol:** Ingeniero · **Prioridad:** Alta · **Estimación:** 3
- **Historia:** Como Ingeniero, quiero que el sistema detecte datos imposibles o sospechosos antes de guardarlos para no contaminar el histórico ni los modelos.
- **Criterios de aceptación:**
  - Errores, que bloquean la fila: fecha inválida, futura o repetida; valor no numérico o faltante; negativo; compuertas fuera de 0–100 %; cota fuera de la curva; embalse desconocido o no asignado.
  - Avisos, que se guardan con bandera: salto brusco (umbral por embalse), días faltantes, bajo el volumen muerto, muy sobre el nivel normal, volumen distinto al de la curva, sin curva, fecha ya existente.

### HU-2.4 · Importación con vista previa ✅
- **Rol:** Ingeniero · **Prioridad:** Alta · **Estimación:** 3
- **Historia:** Como Ingeniero, quiero importar Excel o CSV y revisar una vista previa con los errores por fila antes de confirmar.
- **Criterios de aceptación:**
  - Plantillas Excel (con hoja de instrucciones) y CSV.
  - Acepta `;` y coma decimal (formato venezolano).
  - Nada se guarda hasta confirmar; se elige si sobrescribir los días existentes.
  - Solo quien cargó el archivo confirma. El Operador no importa archivos.

### HU-2.5 · Registro manual del Operador ✅
- **Rol:** Operador · **Prioridad:** Alta · **Estimación:** 2
- **Historia:** Como Operador, quiero registrar la lectura diaria desde el teléfono o la PC y ver de inmediato el volumen y los avisos.
- **Criterios de aceptación:**
  - Mismas reglas de calidad que la importación.
  - Un día repetido devuelve 409.
  - El Operador corrige sus propios registros solo durante 24 h; el Ingeniero corrige cualquiera.
  - Toda corrección queda auditada con el valor anterior y el nuevo.

### HU-2.6 · Estado operativo y semáforo ✅
- **Rol:** todos · **Prioridad:** Alta · **Estimación:** 2
- **Historia:** Como usuario, quiero ver el estado actual de cada embalse con un semáforo y explicaciones sencillas.
- **Criterios de aceptación:**
  - Semáforo verde, amarillo o rojo (escasez o alivio), y gris sin datos.
  - Si no hay umbrales, se usan las cotas oficiales.
  - Dato marcado como desactualizado después de 2 días.
  - Balance hídrico por período.

### HU-2.7 · Carga del dataset sintético y archivos de ejemplo ✅
- **Rol:** equipo · **Prioridad:** Alta · **Estimación:** 1
- **Historia:** Como equipo, quiero cargar el histórico sintético y tener archivos de ejemplo para demostrar la importación y el control de calidad.
- **Criterios de aceptación:**
  - `app.cli load-synthetic-measurements` carga 22.779 días hasta el 2026-10-15 con el mismo validador y sin errores.
  - Tres archivos de ejemplo: válido en Excel, válido en formato venezolano y uno con 11 errores o avisos introducidos a propósito.

### HU-2.8 · Interfaz de ingesta y estado ✅
- **Rol:** todos · **Prioridad:** Alta · **Estimación:** 3
- **Historia:** Como usuario, quiero ver el semáforo en cada embalse, registrar el día y, como Ingeniero, importar archivos con vista previa.
- **Criterios de aceptación:**
  - Tarjetas con semáforo, barra de disponibilidad, volumen útil y días de reserva.
  - Ficha con estado actual, tabla del movimiento diario (7 días a 1 año) y balance.
  - Pantallas "Registro diario" e "Importar datos".
  - Ayudas en lenguaje sencillo en cada indicador.

---

## Iteración 3 — Datos satelitales (M5)

### HU-3.1 · Polígonos de los embalses y áreas de influencia ✅
- **Rol:** Ingeniero · **Prioridad:** Alta · **Estimación:** 2
- **Historia:** Como Ingeniero, quiero los polígonos de cada embalse y de su zona de aporte para agregar los datos satelitales sobre el área correcta.
- **Criterios de aceptación:**
  - Polígonos reales de los espejos de agua tomados de OpenStreetMap (ODbL), con copia versionada y marcados como PROVISIONALES.
  - Área de influencia provisional (espejo + 20 km) mientras no estén las cuencas oficiales.
  - Cada geometría guarda su origen. Los polígonos cargados por un usuario no se reemplazan.

### HU-3.2 · Precipitación diaria por cuenca (CHIRPS) ✅
- **Rol:** Ingeniero · **Prioridad:** Alta · **Estimación:** 2
- **Historia:** Como Ingeniero, quiero la lluvia diaria sobre la zona de aporte de cada embalse desde 2005, sin depender de una cuenta.
- **Criterios de aceptación:**
  - CHIRPS v3 desde dynamical.org: producto final y preliminar, promedio por polígono a 0,05°.
  - Histórico completo 2005–2026 cargado: 23.937 días.

### HU-3.3 · Humedad del suelo (ERA5-Land) ✅
- **Rol:** Ingeniero · **Prioridad:** Alta · **Estimación:** 2
- **Historia:** Como Ingeniero, quiero la humedad del suelo diaria de la zona de aporte, porque condiciona cuánto de la lluvia llega al embalse.
- **Criterios de aceptación:**
  - ERA5-Land (capa 0–7 cm) vía Open-Meteo, sin cuenta, promediando una malla de puntos dentro del área de influencia.
  - Reintentos ante el límite de uso (429).

### HU-3.4 · NDWI y superficie del espejo de agua ✅
- **Rol:** Ingeniero · **Prioridad:** Alta · **Estimación:** 3
- **Historia:** Como Ingeniero, quiero medir desde el satélite la superficie de agua de cada embalse para contrastarla con la cota medida.
- **Criterios de aceptación:**
  - Sentinel-2 L2A y Landsat C2 L2 desde Planetary Computer; NDWI de McFeeters.
  - Se usa la escena con menos nubes de cada fecha y se reportan el porcentaje de nubes y la calidad (buena, dudosa o sin dato).
  - Se corrigen el desplazamiento de Sentinel-2 y la escala de Landsat.

### HU-3.5 · Ingesta y tareas en segundo plano ✅
- **Rol:** Ingeniero · **Prioridad:** Alta · **Estimación:** 2
- **Historia:** Como Ingeniero, quiero lanzar descargas largas sin bloquear la plataforma y ver su avance.
- **Criterios de aceptación:**
  - Las tareas registran estado, avance, resultado o error.
  - Guardado por bloques e idempotente.
  - No se permiten dos descargas del mismo tipo a la vez.
  - CLI para el histórico.

### HU-3.6 · API de series e indicadores satelitales ✅
- **Rol:** todos · **Prioridad:** Alta · **Estimación:** 2
- **Historia:** Como usuario, quiero ver la lluvia reciente frente a lo normal, la humedad del suelo y el último espejo de agua de cada embalse.
- **Criterios de aceptación:**
  - Resumen con lluvia de 7 y 30 días y su anomalía, humedad del suelo frente a su normal mensual, y superficie de agua frente al polígono.
  - Serie por variable con filtro de calidad.
  - Permisos: M5 para descargas y M7 (todos) para consultar.

### HU-3.7 · Interfaz satelital ✅
- **Rol:** todos · **Prioridad:** Alta · **Estimación:** 2
- **Historia:** Como usuario, quiero ver los indicadores satelitales en la ficha del embalse y, como Ingeniero, gestionar las descargas.
- **Criterios de aceptación:**
  - Tarjeta de indicadores con ayudas y aviso de geometría provisional.
  - Pantalla "Datos satelitales" con avance en vivo, cobertura y fuentes.
