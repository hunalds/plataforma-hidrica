# Arquitectura

Documento vivo: se actualiza al cerrar cada iteración. **Estado: cierre de la Iteración 0 (2026-11-12).** Los bloques marcados *(previsto)* todavía no existen.

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
        API[Routers<br/>/health ✅ · auth · embalses · ingesta<br/>predicciones · alertas · reportes]
        SVC[Servicios<br/>hydro_calcs · alertas · reportes <i>(previsto)</i>]
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

En la Iteración 0 la base solo tiene PostGIS activado (migración `0001_postgis`). Este diagrama es el **modelo previsto** para las iteraciones 1 a 4 y se irá ajustando:

```mermaid
erDiagram
    USUARIO ||--o{ USUARIO_EMBALSE : "asignado a"
    EMBALSE ||--o{ USUARIO_EMBALSE : ""
    EMBALSE ||--o{ UMBRAL : tiene
    EMBALSE ||--o{ CURVA_COTA_VOLUMEN : "versiones"
    EMBALSE ||--o{ MEDICION_DIARIA : registra
    EMBALSE ||--o{ OBSERVACION_SATELITAL : "zona de interés"
    EMBALSE ||--o{ PREDICCION : ""
    MODELO_ML ||--o{ PREDICCION : genera
    EMBALSE ||--o{ ALERTA : ""
    USUARIO ||--o{ AUDITORIA : realiza

    EMBALSE {
        string codigo PK
        string nombre
        geometry poligono
        geometry cuenca
        float cota_normal
        float cota_volumen_muerto
        date inicio_registros
    }
    MEDICION_DIARIA {
        string embalse FK
        date fecha
        time hora
        float cota_msnm
        float volumen_hm3
        float caudal_entrada_m3s
        float caudal_salida_m3s
        float gasto_ecologico_m3s
        float apertura_compuertas_pct
        float captacion_m3s
        string observaciones
    }
    OBSERVACION_SATELITAL {
        string area_codigo
        date fecha
        string variable
        float valor
        string fuente
        string calidad
        float nubosidad_pct
    }
```

## 4. Decisiones de arquitectura

| Decisión | Razón |
|---|---|
| `create_app(settings)` como fábrica | Permite probar con otra configuración (base de pruebas, puerto inválido para el error 503) sin variables globales. |
| Contraseña como `SecretStr` y error 503 sin detalle del driver | Evita filtrar credenciales en las respuestas y en los logs. |
| `SatelliteProvider` abstracto | Cambiar de fuente sin tocar la ingesta ni el ML (C-10, C-12). |
| Plantilla de importación definida en un solo lugar (`ml/src/schema.py`) | El dataset sintético y los datos reales comparten el mismo formato. |
| Variables `VITE_*` desde el `.env` de la raíz | Una sola fuente de configuración; Vite no expone al navegador las variables sin prefijo. |
