# Arquitectura

Documento vivo: se actualiza al cerrar cada iteración. **Estado: cierre de la Iteración 8 (2026-11-12).** Todos los módulos M1–M12 están implementados; lo que depende de terceros (proveedor de SMS/WhatsApp, datos oficiales) está marcado como pendiente.

## 1. Arquitectura lógica (componentes)

```mermaid
flowchart LR
    subgraph Usuarios
        G[Gerencia]
        I[Ingeniero / Analista]
        O[Operador]
    end

    subgraph Frontend["Frontend · React + Vite + TS"]
        UI[Páginas y componentes<br/>Tailwind · Phosphor]
        Q[TanStack Query<br/>cliente API]
        MAP[Mapa Leaflet ✅<br/>OSM / EOX]
        CH2[Gráficas ECharts ✅]
    end

    subgraph Backend["Backend · FastAPI (Python 3.12)"]
        API[Routers<br/>/health · /auth · /users · /audit · /reservoirs ✅<br/>/ingest · /measurements · /status · /balance ✅<br/>/satellite · /satellite/jobs ✅<br/>/ml · /forecast · /dashboard · /map ✅<br/>/alerts · /reports ✅]
        SVC[Servicios<br/>auditoría · sesiones · correo · curvas ✅<br/>hydro_calcs · ingest · tabular ✅<br/>ml_service · alerts · notifications · reports ✅]
        SAT[SatelliteProvider ✅<br/>chirps · era5_land_openmeteo · planetary_computer · mock]
        JOBS[Tareas manuales ✅<br/>BackgroundTasks + tabla jobs]
    end

    subgraph ML["ML · ml/ (Python 3.12)"]
        SYN[Dataset sintético ✅]
        FEAT[hidrica_ml ✅<br/>features · XGBoost · LSTM PyTorch<br/>backtesting · calibración]
    end

    DB[(PostgreSQL 18<br/>+ PostGIS 3.6 ✅)]

    subgraph Externos["Fuentes externas (verificadas en HU-0.6)"]
        CH[CHIRPS<br/>dynamical.org]
        E5[ERA5-Land<br/>vía Open-Meteo]
        OSM[Polígonos<br/>OpenStreetMap]
        S2[Sentinel-2 / Landsat<br/>Planetary Computer · CDSE]
    end

    G & I & O --> UI
    UI --> Q --> API
    UI --> MAP
    API --> SVC --> DB
    API --> JOBS --> SAT
    JOBS --> FEAT
    SAT --> CH & E5 & S2
    SVC -. copia versionada .-> OSM
    SAT --> DB
    FEAT --> DB
    SYN -. datos de desarrollo .-> DB
    UI --> CH2
    SVC --> NOTIF[Canales ✅<br/>correo · Telegram<br/>SMS · WhatsApp pendientes]
```

## 2. Arquitectura física

### 2.1 Desarrollo (actual)

```mermaid
flowchart TB
    subgraph PC["PC de desarrollo · Windows 11"]
        V[Vite dev server<br/>:5173]
        U[Uvicorn · FastAPI<br/>:8000]
        P[(PostgreSQL 18 + PostGIS<br/>servicio Windows :5432<br/>plataforma_hidrica<br/>plataforma_hidrica_test)]
        V -- HTTP/JSON · CORS --> U
        U -- psycopg 3 --> P
    end
    Internet((Internet)) --- U
```

### 2.2 Producción (Iteración 7 · archivos listos, sin desplegar)

Hay dos variantes. Los archivos están escritos (`docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile`, `frontend/nginx.conf`, `frontend/vercel.json`) pero Docker no estaba instalado en el equipo de desarrollo y no había cuentas de VPS ni Vercel (P-32).

**Variante A — todo en un servidor (recomendada para MINAGUAS):**

```mermaid
flowchart TB
    Nav[Navegador<br/>PC · tableta · teléfono]
    subgraph SRV["VPS o servidor institucional · Docker Compose"]
        CA[Caddy · HTTPS automático<br/>perfil https]
        NG[frontend · nginx<br/>estáticos + proxy /api]
        BE2[backend · FastAPI + ML<br/>uvicorn, usuario sin privilegios]
        DB2[(db · postgis 18-3.6<br/>sin puertos publicados)]
        BK2[backup · pg_dump diario<br/>retención BACKUP_KEEP_DAYS]
    end
    Nav -- HTTPS 443 --> CA --> NG -- /api --> BE2 --> DB2
    BK2 --> DB2
    BK2 --> V[(./backups)]
```

**Variante B — frontend en Vercel:**

```mermaid
flowchart TB
    Nav[Navegador<br/>PC · tableta · teléfono]
    subgraph Vercel
        FE[Frontend estático<br/>build de Vite]
    end
    subgraph VPS["VPS o servidor institucional · Docker Compose"]
        RP[Proxy inverso HTTPS]
        BE[Contenedor backend<br/>FastAPI + ML]
        DBc[(Contenedor PostGIS 18)]
        BK[Respaldo diario<br/>pg_dump + cron]
    end
    Nav -- HTTPS --> FE
    Nav -- HTTPS · VITE_API_URL --> RP --> BE --> DBc
    BK --> DBc
```

Si las normativas de la institución lo exigen (P-16), el frontend también se puede servir desde el mismo servidor institucional y prescindir de Vercel.

## 3. Modelo de datos (entidad-relación)

Tablas **implementadas** en la Iteración 1 (migración `0002_auth_reservoirs`):

```mermaid
erDiagram
    USERS ||--o{ USER_RESERVOIR : "asignado a"
    RESERVOIRS ||--o{ USER_RESERVOIR : ""
    RESERVOIRS ||--|| THRESHOLDS : tiene
    RESERVOIRS ||--o{ ELEVATION_CURVES : "versiones"
    ELEVATION_CURVES ||--o{ ELEVATION_CURVE_POINTS : puntos
    USERS ||--o{ REFRESH_TOKENS : sesiones
    USERS ||--o{ PASSWORD_RESET_TOKENS : recuperación
    USERS ||--o{ AUDIT_LOG : realiza
    RESERVOIRS ||--o{ DAILY_MEASUREMENTS : "movimiento diario"
    IMPORT_BATCHES ||--o{ DAILY_MEASUREMENTS : "origen"
    USERS ||--o{ IMPORT_BATCHES : carga
    RESERVOIRS ||--o{ SATELLITE_OBSERVATIONS : "observaciones"
    USERS ||--o{ JOBS : lanza

    USERS {
        int id PK
        string email UK
        string full_name
        enum role "GERENCIA | INGENIERO | OPERADOR"
        string password_hash "Argon2id"
        bool is_active
        bool must_change_password
        int failed_attempts
        timestamptz locked_until
        int token_version
    }
    RESERVOIRS {
        string code PK "TULE | MANUELOTE | TRES_RIOS"
        string name
        string basin
        date records_start
        float normal_level
        float dead_level
        geometry geom "MultiPolygon 4326"
        geometry basin_geom "MultiPolygon 4326"
    }
    THRESHOLDS {
        string reservoir_code PK,FK
        float low_critical
        float low_alert
        float high_alert
        float spill_level
        int updated_by FK
    }
    ELEVATION_CURVES {
        int id PK
        string reservoir_code FK
        int version
        date valid_from
        string source_filename
    }
    ELEVATION_CURVE_POINTS {
        int curve_id FK
        float elevation
        float area_km2
        float volume_hm3
    }
    REFRESH_TOKENS {
        uuid id PK "jti"
        int user_id FK
        timestamptz expires_at
        timestamptz last_used_at
        timestamptz revoked_at
    }
    PASSWORD_RESET_TOKENS {
        int id PK
        int user_id FK
        string token_hash "SHA-256"
        timestamptz expires_at
        timestamptz used_at
    }
    DAILY_MEASUREMENTS {
        int id PK
        string reservoir_code FK
        date day "UK con reservoir_code"
        time reading_time
        float level_m
        float volume_hm3
        enum volume_source "REPORTADO | CURVA"
        int curve_version
        float inflow_m3s
        float outflow_m3s
        float eco_flow_m3s
        float gate_opening_pct
        float intake_m3s
        jsonb quality_flags
        enum source "MANUAL | IMPORT | SQL"
        uuid import_batch_id FK
    }
    IMPORT_BATCHES {
        uuid id PK
        string filename
        enum status "PREVIEW | CONFIRMED | DISCARDED"
        jsonb summary
        jsonb issues
        jsonb rows "filas válidas hasta confirmar"
        int created_by FK
    }
    SATELLITE_OBSERVATIONS {
        int id PK
        string reservoir_code FK
        enum scope "EMBALSE | CUENCA"
        date day
        string variable "precipitacion_mm | humedad_suelo_m3m3 | ndwi_medio | superficie_agua_km2"
        float value
        string source
        string quality "buena | dudosa | sin_dato"
        float cloud_pct
        jsonb meta
    }
    JOBS {
        uuid id PK
        string kind
        jsonb params
        enum status "PENDIENTE | EN_CURSO | TERMINADA | FALLIDA"
        float progress
        string message
        jsonb result
    }
    AUDIT_LOG {
        int id PK
        timestamptz created_at
        int user_id FK
        string action
        string entity
        string entity_id
        jsonb old_value
        jsonb new_value
        string ip
    }
```

Tablas agregadas en las Iteraciones 4 y 6 (migraciones `0005` y `0006_alerts`):

```mermaid
erDiagram
    RESERVOIRS ||--o{ ML_MODELS : "modelos entrenados"
    USERS ||--o{ ML_MODELS : "entrenó"
    RESERVOIRS ||--o{ ALERTS : genera
    ALERTS ||--o{ ALERT_ACKS : "acuses"
    USERS ||--o{ ALERT_ACKS : "atendió"
    ALERTS ||--o{ ALERT_DELIVERIES : "envíos"
    RESERVOIRS |o--o{ ALERT_RECIPIENTS : "filtra (opcional)"

    ML_MODELS {
        int id PK
        string reservoir_code FK
        string kind "persistencia | estacional | xgboost | lstm"
        string version_tag
        string data_source "sintetico | real"
        jsonb test_years
        jsonb params
        jsonb metrics "MAE, RMSE, sesgo, cobertura por horizonte"
        jsonb importance
        float score "MAE medio de volumen (hm³)"
        string artifact_dir
        bool pinned
        int created_by FK
    }
    ALERTS {
        int id PK
        string reservoir_code FK
        string dedup_key "embalse:tipo:dirección"
        string kind "observada | proyectada"
        string direction "escasez | inundacion_alivio"
        string severity "informativa | alerta | critica"
        string threshold
        float threshold_level
        float value
        int horizon_days
        float probability
        date event_day
        timestamptz resolved_at
    }
    ALERT_ACKS {
        int id PK
        int alert_id FK
        int user_id FK
        string user_email
        timestamptz at
    }
    ALERT_DELIVERIES {
        int id PK
        int alert_id FK
        string channel "correo | telegram | sms | whatsapp"
        string recipient
        string status "enviada | error | omitida"
        string severity
    }
    ALERT_RECIPIENTS {
        int id PK
        string name
        string channel
        string target
        string reservoir_code FK
        string min_severity
        bool active
    }
```

Las predicciones **no se guardan**: se calculan al consultar con el modelo activo (en caché) y así siempre usan el último dato. El diccionario completo de columnas está en [diccionario-datos.md](diccionario-datos.md).

## 4. Casos de uso (Iteración 1)

```mermaid
flowchart LR
    G([Gerencia])
    I([Ingeniero])
    O([Operador])
    subgraph Sistema["Plataforma Hídrica"]
        UC1((Iniciar / cerrar sesión))
        UC2((Recuperar contraseña))
        UC3((Cambiar contraseña))
        UC4((Gestionar usuarios))
        UC5((Consultar bitácora))
        UC6((Consultar embalses))
        UC7((Definir umbrales))
        UC8((Cargar curva cota–volumen))
        UC9((Cargar polígono))
    end
    G --- UC1 & UC2 & UC3 & UC4 & UC5 & UC6
    I --- UC1 & UC2 & UC3 & UC6 & UC7 & UC8 & UC9
    O --- UC1 & UC2 & UC3 & UC6
```

## 5. Secuencia: inicio de sesión con primer acceso

```mermaid
sequenceDiagram
    actor U as Usuario
    participant F as Frontend
    participant A as API /auth
    participant D as PostgreSQL
    U->>F: correo + contraseña temporal
    F->>A: POST /auth/login
    A->>A: límite por IP (10/min)
    A->>D: buscar usuario, verificar Argon2id
    alt contraseña incorrecta
        A->>D: failed_attempts + 1 (5 → bloqueo 15 min) · bitácora
        A-->>F: 401 / 423 con mensaje en español
    else correcta
        A->>D: guardar refresh token (jti) · bitácora login.ok
        A-->>F: access (15 min) + refresh (7 días) + usuario y permisos
        F->>F: must_change_password → /cambiar-clave
        U->>F: nueva contraseña
        F->>A: POST /auth/change-password
        A->>D: nuevo hash · token_version + 1 · revocar sesiones
        A-->>F: tokens nuevos
        F->>A: GET /reservoirs (Bearer)
        A-->>F: embalses visibles según el rol
    end
```

## 6. Secuencia: importación con vista previa (Iteración 2)

```mermaid
sequenceDiagram
    actor I as Ingeniero
    participant F as Frontend
    participant A as API /ingest
    participant Q as Control de calidad (ingest.validate)
    participant D as PostgreSQL
    I->>F: elige archivo .xlsx / .csv
    F->>A: POST /ingest/preview (multipart)
    A->>Q: leer filas (formato ES/VE) y validar
    Q->>D: curvas vigentes por fecha · días existentes · cota del día anterior
    Q-->>A: filas válidas + errores y avisos por fila + resumen
    A->>D: guardar ImportBatch (PREVIEW) · bitácora
    A-->>F: resumen, problemas por fila, muestra
    I->>F: revisa y confirma (¿sobrescribir existentes?)
    F->>A: POST /ingest/batches/{id}/confirm
    A->>D: INSERT … ON CONFLICT (embalse, día) · lote CONFIRMED · bitácora
    A-->>F: insertadas / actualizadas / omitidas
```

## 7. Secuencia: descarga satelital en segundo plano (Iteración 3)

```mermaid
sequenceDiagram
    actor I as Ingeniero
    participant F as Frontend
    participant A as API /satellite
    participant B as BackgroundTasks
    participant P as Proveedor (CHIRPS / Open-Meteo / Planetary Computer)
    participant D as PostgreSQL
    I->>F: tipo de dato + rango de fechas
    F->>A: POST /satellite/jobs
    A->>D: validar geometrías · crear Job (PENDIENTE) · bitácora
    A-->>F: 202 + id de la tarea
    A->>B: agendar run_job
    loop por bloque (año o trimestre) y embalse
        B->>P: descargar / recortar al polígono
        P-->>B: observaciones diarias (+ nubes y calidad)
        B->>D: upsert observaciones · commit · avance del Job
    end
    B->>D: Job TERMINADA (o FALLIDA con el mensaje)
    F->>A: GET /satellite/jobs (cada 3 s mientras haya tareas en curso)
```

## 8. Decisiones de arquitectura

| Decisión | Razón |
|---|---|
| `create_app(settings)` como fábrica | Permite probar con otra configuración (base de pruebas, puerto inválido para el error 503) sin variables globales. |
| Contraseña como `SecretStr` y error 503 sin detalle del driver | Evita filtrar credenciales en las respuestas y en los logs. |
| `SatelliteProvider` abstracto | Cambiar de fuente sin tocar la ingesta ni el ML (C-10, C-12). |
| Plantilla de importación definida en un solo lugar (`ml/src/schema.py`) | El dataset sintético y los datos reales comparten el mismo formato. |
| Variables `VITE_*` desde el `.env` de la raíz | Una sola fuente de configuración; Vite no expone al navegador las variables sin prefijo. |
| `token_version` en el usuario | Cambiar la contraseña, desactivar o cambiar el rol invalida al instante todos los tokens emitidos, sin listas negras. |
| Rotación de refresh tokens con detección de reuso | Si alguien roba un token de renovación y lo usa, la segunda vez se detecta y se cierran todas las sesiones. |
| Permisos en una matriz declarativa (`core/permissions.py`) | Refleja literalmente la tabla de la sección 6. El backend la aplica con `require()` y el frontend la recibe en `/auth/me`. |
| Errores con `{"detail": {"code", "message"}}` | El frontend muestra el mensaje en español y decide según el código (p. ej. `PASSWORD_CHANGE_REQUIRED`). |
| Curvas versionadas por fecha de vigencia | Los cálculos históricos usan la curva que regía en cada fecha, no la última cargada. |
| Un solo validador para importación, registro manual, corrección y carga sintética | Las reglas de calidad son idénticas en todos los caminos de entrada y se prueban una sola vez. |
| Vista previa persistida (`import_batches`) | El archivo se valida una vez; al confirmar se guarda exactamente lo que el usuario revisó. |
| Indicadores M12 calculados al consultar (no guardados) | Si cambia la curva o se corrige una fórmula, todo el histórico se recalcula sin migrar datos. |
| Proveedores satelitales detrás de `SatelliteProvider`; cálculos en `compute.py` (sin red) | Cambiar de fuente (p. ej. al CDS con cuenta) no toca la ingesta ni la API, y los cálculos se prueban con arreglos sintéticos. |
| Copia versionada de los polígonos OSM (`app/data/geo`) | El sistema no depende de que OSM o Nominatim estén disponibles, y la geometría usada queda trazable. |
| Tareas con `BackgroundTasks` + tabla `jobs` | Descargas de minutos u horas sin bloquear la API, con avance visible y sin instalar Redis ni Celery. |
| Fórmulas en funciones puras (`hydro_calcs.py`) | Se auditan y prueban sin base de datos. Es el único lugar que hay que cambiar cuando MINAGUAS valide las fórmulas. |
| Paquete `hidrica_ml` compartido por el backend y los cuadernos | Las features y los modelos de la tesis son exactamente los que corren en producción. |
| Registro de modelos propio (`ml_models` + archivos) en lugar de MLflow | Un servidor menos que mantener; cumple lo necesario (versiones, métricas, activo, fijado). |
| Selección automática por MAE, incluida la línea base | Si el ML no supera a la línea base estacional, se usa la línea base: honestidad frente al usuario. |
| Calibración conformal de las bandas | Las bandas de XGBoost y LSTM se ajustan con los residuos de validación para acercarse al 80 % nominal. |
| Alertas con `dedup_key` y escalamiento | Una alerta por evento: no inunda de mensajes a la Gerencia y sí avisa cuando la situación empeora. |
| Canales detrás de `NotificationChannel` | Agregar SMS o WhatsApp es implementar una clase, sin tocar la lógica de alertas. |
| Reportes con ReportLab (sin dependencias del sistema) | Funciona igual en Windows, en Docker slim y en el servidor institucional. |
| Frontend servido por nginx con proxy `/api` | Mismo origen en producción: sin CORS ni cookies de terceros. |

## 9. Secuencia: evaluación de alertas (Iteración 6)

```mermaid
sequenceDiagram
    actor O as Operador
    participant API as FastAPI
    participant AL as services/alerts
    participant ML as ml_service
    participant DB as PostgreSQL
    participant CH as Canales (correo, Telegram)
    O->>API: POST /measurements (lectura del día)
    API->>DB: guarda el registro
    API-->>O: 201 Creado
    API->>AL: evaluate() en segundo plano
    AL->>DB: estado actual y umbrales
    AL->>ML: forecast(30 días)
    ML-->>AL: probabilidades por umbral
    AL->>DB: busca alerta abierta con la misma dedup_key
    alt nueva o escalada
        AL->>DB: crea o actualiza la alerta
        AL->>CH: notifica a los destinatarios por severidad
        CH-->>AL: enviada / error / omitida
        AL->>DB: registra cada envío
    else sin cambios
        AL->>DB: actualiza valor y fecha
    else la condición desapareció
        AL->>DB: marca resuelta
    end
```
