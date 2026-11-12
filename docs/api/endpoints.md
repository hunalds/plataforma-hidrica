# API REST · índice de endpoints

Generado el 2026-11-12 desde FastAPI. Especificación completa: [openapi.json](openapi.json). Documentación interactiva en el servidor: `/docs` (Swagger) y `/redoc`.

Autenticación: `Authorization: Bearer <token de acceso>` (ver `/auth/login`). Errores: `{"detail": {"code", "message"}}`.

## Alertas

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/alerts` | Alertas (activas o historial) |
| POST | `/alerts/evaluate` | Evaluar ahora las alertas de todos los embalses |
| GET | `/alerts/recipients` | Destinatarios de alertas |
| POST | `/alerts/recipients` | Agregar destinatario |
| DELETE | `/alerts/recipients/{rid}` | Eliminar destinatario |
| PUT | `/alerts/recipients/{rid}` | Editar destinatario |
| POST | `/alerts/recipients/{rid}/test` | Enviar un mensaje de prueba |
| POST | `/alerts/{alert_id}/ack` | Acusar recibo de una alerta |

## Auditoría

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/audit` | Consultar la bitácora de auditoría |

## Autenticación

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/auth/change-password` | Cambiar mi contraseña |
| POST | `/auth/forgot-password` | Solicitar recuperación de contraseña |
| POST | `/auth/login` | Iniciar sesión |
| POST | `/auth/logout` | Cerrar sesión |
| GET | `/auth/me` | Usuario actual y sus permisos |
| POST | `/auth/refresh` | Renovar la sesión |
| POST | `/auth/reset-password` | Restablecer la contraseña con el enlace |

## Datos satelitales

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/reservoirs/{code}/satellite/series` | Serie de una variable satelital |
| GET | `/reservoirs/{code}/satellite/summary` | Indicadores satelitales recientes |
| GET | `/satellite/coverage` | Datos satelitales disponibles |
| GET | `/satellite/jobs` | Últimas descargas |
| POST | `/satellite/jobs` | Lanzar una descarga satelital |
| GET | `/satellite/jobs/{job_id}` | Estado de una descarga |
| GET | `/satellite/sources` | Fuentes satelitales configuradas |

## Embalses

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/reservoirs` | Listar los embalses visibles para el usuario |
| GET | `/reservoirs/curve-template.csv` | Plantilla CSV de curva cota–volumen |
| GET | `/reservoirs/{code}` | Ficha del embalse |
| PATCH | `/reservoirs/{code}` | Editar la ficha del embalse |
| GET | `/reservoirs/{code}/curves` | Versiones de la curva cota–área–volumen |
| POST | `/reservoirs/{code}/curves` | Cargar una nueva versión de la curva desde CSV o Excel |
| GET | `/reservoirs/{code}/curves/interpolate` | Convertir cota ↔ volumen con la curva vigente |
| GET | `/reservoirs/{code}/curves/{version}` | Puntos de una versión de la curva |
| GET | `/reservoirs/{code}/geometry` | Polígono del embalse o su cuenca en GeoJSON |
| PUT | `/reservoirs/{code}/geometry` | Cargar el polígono (GeoJSON) del embalse o su cuenca |
| GET | `/reservoirs/{code}/thresholds` | Umbrales del embalse |
| PUT | `/reservoirs/{code}/thresholds` | Definir los umbrales del embalse |

## Ingesta

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/ingest/batches` | Últimas importaciones |
| GET | `/ingest/batches/{batch_id}` | Ver una importación |
| POST | `/ingest/batches/{batch_id}/confirm` | Confirmar y guardar las filas válidas |
| POST | `/ingest/batches/{batch_id}/discard` | Descartar una vista previa |
| POST | `/ingest/preview` | Validar un archivo y mostrar la vista previa |
| GET | `/ingest/template.csv` | Plantilla CSV del movimiento diario |
| GET | `/ingest/template.xlsx` | Plantilla Excel del movimiento diario (con hoja de instrucciones) |

## Movimiento diario

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/reservoirs/status` | Estado operativo de los embalses visibles |
| GET | `/reservoirs/{code}/balance` | Balance hídrico diario |
| GET | `/reservoirs/{code}/measurements` | Movimiento diario del embalse |
| POST | `/reservoirs/{code}/measurements` | Registrar el movimiento del día (registro manual) |
| PATCH | `/reservoirs/{code}/measurements/{day}` | Corregir un registro |
| GET | `/reservoirs/{code}/status` | Estado operativo actual (último dato) |

## Panel y mapa

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/dashboard/comparison` | Disponibilidad diaria comparada entre embalses |
| GET | `/map/features` | Capas del mapa: embalses con semáforo y áreas de influencia con indicadores |
| GET | `/reservoirs/{code}/history` | Cota del período y rango histórico |

## Predicción

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/ml/jobs` | Últimos entrenamientos |
| GET | `/ml/models` | Modelos registrados |
| POST | `/ml/models/{model_id}/pin` | Fijar este modelo para su embalse |
| POST | `/ml/models/{model_id}/unpin` | Volver a la selección automática |
| POST | `/ml/train` | Reentrenar los modelos |
| GET | `/reservoirs/{code}/forecast` | Proyección a 90 días con banda de incertidumbre |

## Reportes

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/reports/alerts` | Registro de alertas |
| GET | `/reports/bulletin` | Boletín diario del estado de los embalses |
| GET | `/reports/comparison` | Comparativo entre embalses |
| GET | `/reports/historical/{code}` | Histórico comparativo entre dos períodos |
| GET | `/reports/prediction/{code}` | Reporte de predicción de un embalse |

## Salud

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/health` | Estado del servicio |

## Usuarios

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/users` | Listar usuarios |
| POST | `/users` | Crear usuario |
| GET | `/users/{user_id}` | Ver usuario |
| PATCH | `/users/{user_id}` | Editar usuario, rol, estado o embalses asignados |
| POST | `/users/{user_id}/reset-password` | Generar una contraseña temporal (desbloquea la cuenta y cierra sus sesiones) |
