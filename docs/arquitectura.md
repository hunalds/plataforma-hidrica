# Arquitectura

Documento vivo: se actualiza al cerrar cada iteración. **Estado: cierre de la Iteración 1 (2026-11-12).** Los bloques marcados *(previsto)* todavía no existen.

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
        MAP[Mapa Leaflet<br/>OSM / EOX <i>(previsto)</i>]
    end

    subgraph Backend["Backend · FastAPI (Python 3.12)"]
        API[Routers<br/>/health · /auth · /users · /audit · /reservoirs ✅<br/>ingesta · predicciones · alertas · reportes <i>(previsto)</i>]
        SVC[Servicios<br/>auditoría · sesiones · correo · curvas ✅<br/>hydro_calcs · alertas · reportes <i>(previsto)</i>]
        SAT[SatelliteProvider ✅<br/>mock · chirps · era5_land · copernicus · planetary_computer]
        JOBS[Tareas manuales<br/>BackgroundTasks <i>(previsto)</i>]
    end

    subgraph ML["ML · ml/ (Python 3.12)"]
        SYN[Dataset sintético ✅]
        FEAT[features · XGBoost · LSTM PyTorch<br/>backtesting · registro <i>(previsto)</i>]
    end

    DB[(PostgreSQL 18<br/>+ PostGIS 3.6 ✅)]

    subgraph Externos["Fuentes externas (verificadas en HU-0.6)"]
        CH[CHIRPS<br/>dynamical.org]
        E5[ERA5-Land<br/>Copernicus CDS]
        S2[Sentinel-2 / Landsat<br/>Planetary Computer · CDSE]
    end

    G & I & O --> UI
    UI --> Q --> API
    UI --> MAP
    API --> SVC --> DB
    API --> JOBS --> SAT
    JOBS --> FEAT
    SAT --> CH & E5 & S2
    SAT --> DB
    FEAT --> DB
    SYN -. datos de desarrollo .-> DB
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

### 2.2 Producción (previsto, Iteración 7)

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

Previstas para las próximas iteraciones: `MEDICION_DIARIA` (M4), `OBSERVACION_SATELITAL` (M5), `MODELO_ML` y `PREDICCION` (M6), `ALERTA` (M9).

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

## 6. Decisiones de arquitectura

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
