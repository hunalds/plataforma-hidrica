# Diccionario de datos

Generado automáticamente desde los modelos SQLAlchemy el 2026-11-12 (`scripts/docs/generate_docs.py`). Base de datos: PostgreSQL 18 + PostGIS. Esquema migrado con Alembic.

Convenciones: cotas en m.s.n.m., volúmenes en hm³, caudales en m³/s (media diaria), fechas en hora de Caracas.

## Índice

- [`alert_acks`](#alert-acks)
- [`alert_deliveries`](#alert-deliveries)
- [`alert_recipients`](#alert-recipients)
- [`alerts`](#alerts)
- [`audit_log`](#audit-log)
- [`daily_measurements`](#daily-measurements)
- [`elevation_curve_points`](#elevation-curve-points)
- [`elevation_curves`](#elevation-curves)
- [`import_batches`](#import-batches)
- [`jobs`](#jobs)
- [`ml_models`](#ml-models)
- [`password_reset_tokens`](#password-reset-tokens)
- [`refresh_tokens`](#refresh-tokens)
- [`reservoirs`](#reservoirs)
- [`satellite_observations`](#satellite-observations)
- [`thresholds`](#thresholds)
- [`user_reservoir`](#user-reservoir)
- [`users`](#users)

## alert_acks

Acuse de recibo: quién vio la alerta y cuándo.

| Columna | Tipo | Nulo | Clave | Descripción |
|---|---|---|---|---|
| `id` | INTEGER | no | PK | — |
| `alert_id` | INTEGER | no | FK → alerts.id | — |
| `user_id` | INTEGER | no | FK → users.id | — |
| `user_email` | VARCHAR(254) | no | — | — |
| `at` | TIMESTAMP WITH TIME ZONE | no | — | — |

Restricción de unicidad: (alert_id, user_id).

## alert_deliveries

Intento de envío por un canal (plataforma, correo, telegram, sms, whatsapp).

| Columna | Tipo | Nulo | Clave | Descripción |
|---|---|---|---|---|
| `id` | INTEGER | no | PK | — |
| `alert_id` | INTEGER | no | FK → alerts.id | — |
| `channel` | VARCHAR(20) | no | — | — |
| `recipient` | VARCHAR(200) | no | — | — |
| `status` | VARCHAR(20) | no | — | enviada | error | omitida |
| `detail` | TEXT | sí | — | — |
| `severity` | VARCHAR(20) | no | — | — |
| `at` | TIMESTAMP WITH TIME ZONE | no | — | — |

## alert_recipients

Destinatario configurable por embalse (o todos) y severidad mínima.

| Columna | Tipo | Nulo | Clave | Descripción |
|---|---|---|---|---|
| `id` | INTEGER | no | PK | — |
| `name` | VARCHAR(120) | no | — | p. ej. "Director Estadal" |
| `channel` | VARCHAR(20) | no | — | correo | telegram | sms | whatsapp |
| `target` | VARCHAR(200) | no | — | correo, chat_id o teléfono |
| `reservoir_code` | VARCHAR(20) | sí | FK → reservoirs.code | — |
| `min_severity` | VARCHAR(20) | no | — | — |
| `active` | BOOLEAN | no | — | — |
| `created_at` | TIMESTAMP WITH TIME ZONE | no | — | — |

## alerts

Una alerta por evento. Mientras el evento siga activo se ACTUALIZA (no se duplica); al desaparecer la condición se marca resuelta (resolved_at).

| Columna | Tipo | Nulo | Clave | Descripción |
|---|---|---|---|---|
| `id` | INTEGER | no | PK | — |
| `reservoir_code` | VARCHAR(20) | no | FK → reservoirs.code | — |
| `dedup_key` | VARCHAR(120) | no | — | embalse:tipo:umbral |
| `kind` | VARCHAR(20) | no | — | observada | proyectada |
| `direction` | VARCHAR(30) | no | — | escasez | inundacion_alivio |
| `severity` | VARCHAR(20) | no | — | informativa | alerta | critica |
| `threshold` | VARCHAR(40) | no | — | — |
| `threshold_level` | FLOAT | no | — | — |
| `title` | VARCHAR(200) | no | — | — |
| `message` | TEXT | no | — | — |
| `value` | FLOAT | sí | — | cota observada o probabilidad proyectada |
| `horizon_days` | INTEGER | sí | — | — |
| `probability` | FLOAT | sí | — | — |
| `event_day` | DATE | no | — | — |
| `created_at` | TIMESTAMP WITH TIME ZONE | no | — | — |
| `updated_at` | TIMESTAMP WITH TIME ZONE | no | — | — |
| `resolved_at` | TIMESTAMP WITH TIME ZONE | sí | — | — |

## audit_log

Base class used for declarative class definitions. The :class:`_orm.DeclarativeBase` allows for the creation of new declarative bases in such a way that is compatible with type checkers:: from sqlalchemy.orm import DeclarativeBase class Base(DeclarativeBase): pass The above ``Base`` class is now usable as the base for new declarative mappings. The superclass makes use of the ``__init_subclass__()`` method to set up new classes and metaclasses aren't used. When first used, the :class:`_orm.DeclarativeBase` class instantiates a new :class:`_orm.registry` to be used with the base, assuming one was not provided explicitly. The :class:`_orm.DeclarativeBase` class supports class-level attributes which act as parameters for the construction of this registry; such as to indicate a specific :class:`_schema.MetaData` collection as well as a specific value for :paramref:`_orm.registry.type_annotation_map`:: from typing import Annotated from sqlalchemy import BigInteger from sqlalchemy import MetaData from sqlalchemy import String from sqlalchemy.orm import DeclarativeBase bigint = Annotated[int, "bigint"] my_metadata = MetaData() class Base(DeclarativeBase): metadata = my_metadata type_annotation_map = { str: String().with_variant(String(255), "mysql", "mariadb"), bigint: BigInteger(), } Class-level attributes which may be specified include: :param metadata: optional :class:`_schema.MetaData` collection. If a :class:`_orm.registry` is constructed automatically, this :class:`_schema.MetaData` collection will be used to construct it. Otherwise, the local :class:`_schema.MetaData` collection will supersede that used by an existing :class:`_orm.registry` passed using the :paramref:`_orm.DeclarativeBase.registry` parameter. :param type_annotation_map: optional type annotation map that will be passed to the :class:`_orm.registry` as :paramref:`_orm.registry.type_annotation_map`. :param registry: supply a pre-existing :class:`_orm.registry` directly. .. versionadded:: 2.0 Added :class:`.DeclarativeBase`, so that declarative base classes may be constructed in such a way that is also recognized by :pep:`484` type checkers. As a result, :class:`.DeclarativeBase` and other subclassing-oriented APIs should be seen as superseding previous "class returned by a function" APIs, namely :func:`_orm.declarative_base` and :meth:`_orm.registry.generate_base`, where the base class returned cannot be recognized by type checkers without using plugins. **__init__ behavior** In a plain Python class, the base-most ``__init__()`` method in the class hierarchy is ``object.__init__()``, which accepts no arguments. However, when the :class:`_orm.DeclarativeBase` subclass is first declared, the class is given an ``__init__()`` method that links to the :paramref:`_orm.registry.constructor` constructor function, if no ``__init__()`` method is already present; this is the usual declarative constructor that will assign keyword arguments as attributes on the instance, assuming those attributes are established at the class level (i.e. are mapped, or are linked to a descriptor). This constructor is **never accessed by a mapped class without being called explicitly via super()**, as mapped classes are themselves given an ``__init__()`` method directly which calls :paramref:`_orm.registry.constructor`, so in the default case works independently of what the base-most ``__init__()`` method does. .. versionchanged:: 2.0.1 :class:`_orm.DeclarativeBase` has a default constructor that links to :paramref:`_orm.registry.constructor` by default, so that calls to ``super().__init__()`` can access this constructor. Previously, due to an implementation mistake, this default constructor was missing, and calling ``super().__init__()`` would invoke ``object.__init__()``. The :class:`_orm.DeclarativeBase` subclass may also declare an explicit ``__init__()`` method which will replace the use of the :paramref:`_orm.registry.constructor` function at this level:: class Base(DeclarativeBase): def __init__(self, id=None): self.id = id Mapped classes still will not invoke this constructor implicitly; it remains only accessible by calling ``super().__init__()``:: class MyClass(Base): def __init__(self, id=None, name=None): self.name = name super().__init__(id=id) Note that this is a different behavior from what functions like the legacy :func:`_orm.declarative_base` would do; the base created by those functions would always install :paramref:`_orm.registry.constructor` for ``__init__()``.

| Columna | Tipo | Nulo | Clave | Descripción |
|---|---|---|---|---|
| `id` | INTEGER | no | PK | — |
| `created_at` | TIMESTAMP WITH TIME ZONE | no | — | — |
| `user_id` | INTEGER | sí | FK → users.id | — |
| `user_email` | VARCHAR(254) | sí | — | se conserva aunque el usuario se elimine |
| `action` | VARCHAR(60) | no | — | p. ej. "login.ok", "user.update" |
| `entity` | VARCHAR(60) | sí | — | p. ej. "user", "reservoir", "threshold" |
| `entity_id` | VARCHAR(60) | sí | — | — |
| `old_value` | JSONB | sí | — | — |
| `new_value` | JSONB | sí | — | — |
| `ip` | VARCHAR(45) | sí | — | — |

## daily_measurements

Un registro por embalse y día (la lectura diaria del limnímetro y los caudales del día).

| Columna | Tipo | Nulo | Clave | Descripción |
|---|---|---|---|---|
| `id` | INTEGER | no | PK | — |
| `reservoir_code` | VARCHAR(20) | no | FK → reservoirs.code | — |
| `day` | DATE | no | — | — |
| `reading_time` | TIME WITHOUT TIME ZONE | sí | — | hora de la lectura (P-20) |
| `level_m` | FLOAT | no | — | cota (m.s.n.m.) |
| `volume_hm3` | FLOAT | sí | — | — |
| `volume_source` | ENUM(REPORTED, CURVE) | sí | — | — |
| `curve_version` | INTEGER | sí | — | versión de curva usada si volume_source = CURVA |
| `inflow_m3s` | FLOAT | sí | — | caudal de entrada |
| `outflow_m3s` | FLOAT | sí | — | salida/extracción a potabilizadoras |
| `eco_flow_m3s` | FLOAT | sí | — | gasto ecológico |
| `gate_opening_pct` | FLOAT | sí | — | apertura de compuertas |
| `intake_m3s` | FLOAT | sí | — | captación (P-19) |
| `notes` | TEXT | sí | — | — |
| `quality_flags` | JSONB | sí | — | avisos de calidad aceptados al guardar |
| `source` | ENUM(MANUAL, IMPORT, SQL) | no | — | — |
| `import_batch_id` | UUID | sí | FK → import_batches.id | — |
| `created_by` | INTEGER | sí | FK → users.id | — |
| `created_at` | TIMESTAMP WITH TIME ZONE | no | — | — |
| `updated_at` | TIMESTAMP WITH TIME ZONE | no | — | — |

Restricción de unicidad: (reservoir_code, day).

## elevation_curve_points

Base class used for declarative class definitions. The :class:`_orm.DeclarativeBase` allows for the creation of new declarative bases in such a way that is compatible with type checkers:: from sqlalchemy.orm import DeclarativeBase class Base(DeclarativeBase): pass The above ``Base`` class is now usable as the base for new declarative mappings. The superclass makes use of the ``__init_subclass__()`` method to set up new classes and metaclasses aren't used. When first used, the :class:`_orm.DeclarativeBase` class instantiates a new :class:`_orm.registry` to be used with the base, assuming one was not provided explicitly. The :class:`_orm.DeclarativeBase` class supports class-level attributes which act as parameters for the construction of this registry; such as to indicate a specific :class:`_schema.MetaData` collection as well as a specific value for :paramref:`_orm.registry.type_annotation_map`:: from typing import Annotated from sqlalchemy import BigInteger from sqlalchemy import MetaData from sqlalchemy import String from sqlalchemy.orm import DeclarativeBase bigint = Annotated[int, "bigint"] my_metadata = MetaData() class Base(DeclarativeBase): metadata = my_metadata type_annotation_map = { str: String().with_variant(String(255), "mysql", "mariadb"), bigint: BigInteger(), } Class-level attributes which may be specified include: :param metadata: optional :class:`_schema.MetaData` collection. If a :class:`_orm.registry` is constructed automatically, this :class:`_schema.MetaData` collection will be used to construct it. Otherwise, the local :class:`_schema.MetaData` collection will supersede that used by an existing :class:`_orm.registry` passed using the :paramref:`_orm.DeclarativeBase.registry` parameter. :param type_annotation_map: optional type annotation map that will be passed to the :class:`_orm.registry` as :paramref:`_orm.registry.type_annotation_map`. :param registry: supply a pre-existing :class:`_orm.registry` directly. .. versionadded:: 2.0 Added :class:`.DeclarativeBase`, so that declarative base classes may be constructed in such a way that is also recognized by :pep:`484` type checkers. As a result, :class:`.DeclarativeBase` and other subclassing-oriented APIs should be seen as superseding previous "class returned by a function" APIs, namely :func:`_orm.declarative_base` and :meth:`_orm.registry.generate_base`, where the base class returned cannot be recognized by type checkers without using plugins. **__init__ behavior** In a plain Python class, the base-most ``__init__()`` method in the class hierarchy is ``object.__init__()``, which accepts no arguments. However, when the :class:`_orm.DeclarativeBase` subclass is first declared, the class is given an ``__init__()`` method that links to the :paramref:`_orm.registry.constructor` constructor function, if no ``__init__()`` method is already present; this is the usual declarative constructor that will assign keyword arguments as attributes on the instance, assuming those attributes are established at the class level (i.e. are mapped, or are linked to a descriptor). This constructor is **never accessed by a mapped class without being called explicitly via super()**, as mapped classes are themselves given an ``__init__()`` method directly which calls :paramref:`_orm.registry.constructor`, so in the default case works independently of what the base-most ``__init__()`` method does. .. versionchanged:: 2.0.1 :class:`_orm.DeclarativeBase` has a default constructor that links to :paramref:`_orm.registry.constructor` by default, so that calls to ``super().__init__()`` can access this constructor. Previously, due to an implementation mistake, this default constructor was missing, and calling ``super().__init__()`` would invoke ``object.__init__()``. The :class:`_orm.DeclarativeBase` subclass may also declare an explicit ``__init__()`` method which will replace the use of the :paramref:`_orm.registry.constructor` function at this level:: class Base(DeclarativeBase): def __init__(self, id=None): self.id = id Mapped classes still will not invoke this constructor implicitly; it remains only accessible by calling ``super().__init__()``:: class MyClass(Base): def __init__(self, id=None, name=None): self.name = name super().__init__(id=id) Note that this is a different behavior from what functions like the legacy :func:`_orm.declarative_base` would do; the base created by those functions would always install :paramref:`_orm.registry.constructor` for ``__init__()``.

| Columna | Tipo | Nulo | Clave | Descripción |
|---|---|---|---|---|
| `id` | INTEGER | no | PK | — |
| `curve_id` | INTEGER | no | FK → elevation_curves.id | — |
| `elevation` | FLOAT | no | — | cota (m.s.n.m.) |
| `area_km2` | FLOAT | sí | — | — |
| `volume_hm3` | FLOAT | no | — | — |

Restricción de unicidad: (curve_id, elevation).

## elevation_curves

Versión de la curva cota–área–volumen de un embalse, vigente desde `valid_from`.

| Columna | Tipo | Nulo | Clave | Descripción |
|---|---|---|---|---|
| `id` | INTEGER | no | PK | — |
| `reservoir_code` | VARCHAR(20) | no | FK → reservoirs.code | — |
| `version` | INTEGER | no | — | — |
| `valid_from` | DATE | no | — | — |
| `source_filename` | VARCHAR(255) | sí | — | — |
| `notes` | TEXT | sí | — | — |
| `created_at` | TIMESTAMP WITH TIME ZONE | no | — | — |
| `created_by` | INTEGER | sí | FK → users.id | — |

Restricción de unicidad: (reservoir_code, version).

## import_batches

Archivo importado: se valida y se guarda como vista previa; solo se escribe al confirmar.

| Columna | Tipo | Nulo | Clave | Descripción |
|---|---|---|---|---|
| `id` | UUID | no | PK | — |
| `filename` | VARCHAR(255) | no | — | — |
| `status` | ENUM(PREVIEW, CONFIRMED, DISCARDED) | no | — | — |
| `summary` | JSONB | no | — | — |
| `issues` | JSONB | no | — | errores y avisos por fila |
| `rows` | JSONB | no | — | filas válidas normalizadas |
| `created_by` | INTEGER | sí | FK → users.id | — |
| `created_at` | TIMESTAMP WITH TIME ZONE | no | — | — |
| `confirmed_at` | TIMESTAMP WITH TIME ZONE | sí | — | — |

## jobs

Tarea pesada lanzada manualmente (descarga satelital, más adelante reentrenamiento y reportes).

| Columna | Tipo | Nulo | Clave | Descripción |
|---|---|---|---|---|
| `id` | UUID | no | PK | — |
| `kind` | VARCHAR(40) | no | — | — |
| `params` | JSONB | no | — | — |
| `status` | ENUM(PENDING, RUNNING, DONE, FAILED) | no | — | — |
| `progress` | FLOAT | no | — | 0 a 1 |
| `message` | TEXT | sí | — | — |
| `result` | JSONB | sí | — | — |
| `created_by` | INTEGER | sí | FK → users.id | — |
| `created_at` | TIMESTAMP WITH TIME ZONE | no | — | — |
| `started_at` | TIMESTAMP WITH TIME ZONE | sí | — | — |
| `finished_at` | TIMESTAMP WITH TIME ZONE | sí | — | — |

## ml_models

Un modelo entrenado para un embalse, con sus datos, hiperparámetros y métricas de backtesting.

| Columna | Tipo | Nulo | Clave | Descripción |
|---|---|---|---|---|
| `id` | INTEGER | no | PK | — |
| `reservoir_code` | VARCHAR(20) | no | FK → reservoirs.code | — |
| `kind` | VARCHAR(30) | no | — | persistencia | estacional | xgboost | lstm |
| `version_tag` | VARCHAR(40) | no | — | AAAAMMDD-HHMMSS del entrenamiento |
| `data_from` | VARCHAR(10) | no | — | — |
| `data_to` | VARCHAR(10) | no | — | — |
| `n_days` | INTEGER | no | — | — |
| `data_source` | VARCHAR(60) | no | — | — |
| `test_years` | JSONB | no | — | — |
| `params` | JSONB | no | — | — |
| `metrics` | JSONB | no | — | por horizonte (30/60/90) |
| `importance` | JSONB | sí | — | — |
| `score` | FLOAT | no | — | MAE medio de volumen (hm³) a 30/60/90 días |
| `artifact_dir` | VARCHAR(500) | no | — | — |
| `train_seconds` | FLOAT | no | — | — |
| `pinned` | BOOLEAN | no | — | fijado manualmente por el Ingeniero |
| `created_by` | INTEGER | sí | FK → users.id | — |
| `created_at` | TIMESTAMP WITH TIME ZONE | no | — | — |

## password_reset_tokens

Token de un solo uso. Solo se guarda su hash SHA-256, nunca el valor enviado por correo.

| Columna | Tipo | Nulo | Clave | Descripción |
|---|---|---|---|---|
| `id` | INTEGER | no | PK | — |
| `user_id` | INTEGER | no | FK → users.id | — |
| `token_hash` | VARCHAR(64) | no | único | — |
| `expires_at` | TIMESTAMP WITH TIME ZONE | no | — | — |
| `used_at` | TIMESTAMP WITH TIME ZONE | sí | — | — |
| `created_at` | TIMESTAMP WITH TIME ZONE | no | — | — |

## refresh_tokens

Sesión renovable. Se rota en cada uso; reusar uno revocado revoca todas las del usuario.

| Columna | Tipo | Nulo | Clave | Descripción |
|---|---|---|---|---|
| `id` | UUID | no | PK | — |
| `user_id` | INTEGER | no | FK → users.id | — |
| `expires_at` | TIMESTAMP WITH TIME ZONE | no | — | — |
| `last_used_at` | TIMESTAMP WITH TIME ZONE | no | — | — |
| `revoked_at` | TIMESTAMP WITH TIME ZONE | sí | — | — |
| `created_at` | TIMESTAMP WITH TIME ZONE | no | — | — |
| `ip` | VARCHAR(45) | sí | — | — |

## reservoirs

Base class used for declarative class definitions. The :class:`_orm.DeclarativeBase` allows for the creation of new declarative bases in such a way that is compatible with type checkers:: from sqlalchemy.orm import DeclarativeBase class Base(DeclarativeBase): pass The above ``Base`` class is now usable as the base for new declarative mappings. The superclass makes use of the ``__init_subclass__()`` method to set up new classes and metaclasses aren't used. When first used, the :class:`_orm.DeclarativeBase` class instantiates a new :class:`_orm.registry` to be used with the base, assuming one was not provided explicitly. The :class:`_orm.DeclarativeBase` class supports class-level attributes which act as parameters for the construction of this registry; such as to indicate a specific :class:`_schema.MetaData` collection as well as a specific value for :paramref:`_orm.registry.type_annotation_map`:: from typing import Annotated from sqlalchemy import BigInteger from sqlalchemy import MetaData from sqlalchemy import String from sqlalchemy.orm import DeclarativeBase bigint = Annotated[int, "bigint"] my_metadata = MetaData() class Base(DeclarativeBase): metadata = my_metadata type_annotation_map = { str: String().with_variant(String(255), "mysql", "mariadb"), bigint: BigInteger(), } Class-level attributes which may be specified include: :param metadata: optional :class:`_schema.MetaData` collection. If a :class:`_orm.registry` is constructed automatically, this :class:`_schema.MetaData` collection will be used to construct it. Otherwise, the local :class:`_schema.MetaData` collection will supersede that used by an existing :class:`_orm.registry` passed using the :paramref:`_orm.DeclarativeBase.registry` parameter. :param type_annotation_map: optional type annotation map that will be passed to the :class:`_orm.registry` as :paramref:`_orm.registry.type_annotation_map`. :param registry: supply a pre-existing :class:`_orm.registry` directly. .. versionadded:: 2.0 Added :class:`.DeclarativeBase`, so that declarative base classes may be constructed in such a way that is also recognized by :pep:`484` type checkers. As a result, :class:`.DeclarativeBase` and other subclassing-oriented APIs should be seen as superseding previous "class returned by a function" APIs, namely :func:`_orm.declarative_base` and :meth:`_orm.registry.generate_base`, where the base class returned cannot be recognized by type checkers without using plugins. **__init__ behavior** In a plain Python class, the base-most ``__init__()`` method in the class hierarchy is ``object.__init__()``, which accepts no arguments. However, when the :class:`_orm.DeclarativeBase` subclass is first declared, the class is given an ``__init__()`` method that links to the :paramref:`_orm.registry.constructor` constructor function, if no ``__init__()`` method is already present; this is the usual declarative constructor that will assign keyword arguments as attributes on the instance, assuming those attributes are established at the class level (i.e. are mapped, or are linked to a descriptor). This constructor is **never accessed by a mapped class without being called explicitly via super()**, as mapped classes are themselves given an ``__init__()`` method directly which calls :paramref:`_orm.registry.constructor`, so in the default case works independently of what the base-most ``__init__()`` method does. .. versionchanged:: 2.0.1 :class:`_orm.DeclarativeBase` has a default constructor that links to :paramref:`_orm.registry.constructor` by default, so that calls to ``super().__init__()`` can access this constructor. Previously, due to an implementation mistake, this default constructor was missing, and calling ``super().__init__()`` would invoke ``object.__init__()``. The :class:`_orm.DeclarativeBase` subclass may also declare an explicit ``__init__()`` method which will replace the use of the :paramref:`_orm.registry.constructor` function at this level:: class Base(DeclarativeBase): def __init__(self, id=None): self.id = id Mapped classes still will not invoke this constructor implicitly; it remains only accessible by calling ``super().__init__()``:: class MyClass(Base): def __init__(self, id=None, name=None): self.name = name super().__init__(id=id) Note that this is a different behavior from what functions like the legacy :func:`_orm.declarative_base` would do; the base created by those functions would always install :paramref:`_orm.registry.constructor` for ``__init__()``.

| Columna | Tipo | Nulo | Clave | Descripción |
|---|---|---|---|---|
| `code` | VARCHAR(20) | no | PK | TULE, MANUELOTE, TRES_RIOS |
| `name` | VARCHAR(80) | no | — | — |
| `basin` | VARCHAR(120) | sí | — | nombre de la cuenca |
| `records_start` | DATE | sí | — | — |
| `normal_level` | FLOAT | no | — | cota normal (m.s.n.m., P-01) |
| `dead_level` | FLOAT | no | — | cota de volumen muerto / mínimo operativo |
| `description` | TEXT | sí | — | — |
| `qc_max_daily_change_m` | FLOAT | no | — | — |
| `geom` | geometry(MULTIPOLYGON,4326) | sí | — | — |
| `basin_geom` | geometry(MULTIPOLYGON,4326) | sí | — | — |
| `geom_source` | VARCHAR(200) | sí | — | — |
| `basin_source` | VARCHAR(200) | sí | — | — |
| `updated_at` | TIMESTAMP WITH TIME ZONE | no | — | — |

## satellite_observations

Un valor diario por embalse, ámbito, variable y fuente.

| Columna | Tipo | Nulo | Clave | Descripción |
|---|---|---|---|---|
| `id` | INTEGER | no | PK | — |
| `reservoir_code` | VARCHAR(20) | no | FK → reservoirs.code | — |
| `scope` | ENUM(RESERVOIR, BASIN) | no | — | — |
| `day` | DATE | no | — | — |
| `variable` | VARCHAR(40) | no | — | ver services/satellite/base.Variable |
| `value` | FLOAT | sí | — | — |
| `source` | VARCHAR(60) | no | — | chirps, era5_land_openmeteo, sentinel-2-l2a… |
| `quality` | VARCHAR(20) | no | — | buena | dudosa | sin_dato |
| `cloud_pct` | FLOAT | sí | — | — |
| `meta` | JSONB | sí | — | — |
| `created_at` | TIMESTAMP WITH TIME ZONE | no | — | — |

Restricción de unicidad: (reservoir_code, scope, variable, source, day).

## thresholds

Umbrales configurables por el Ingeniero. Deben cumplir: crítico bajo < alerta baja < alerta alta < alivio.

| Columna | Tipo | Nulo | Clave | Descripción |
|---|---|---|---|---|
| `reservoir_code` | VARCHAR(20) | no | PK, FK → reservoirs.code | — |
| `low_critical` | FLOAT | sí | — | nivel bajo crítico |
| `low_alert` | FLOAT | sí | — | nivel bajo de alerta |
| `high_alert` | FLOAT | sí | — | nivel alto de alerta |
| `spill_level` | FLOAT | sí | — | nivel de alivio / inundación |
| `updated_at` | TIMESTAMP WITH TIME ZONE | no | — | — |
| `updated_by` | INTEGER | sí | FK → users.id | — |

## user_reservoir

| Columna | Tipo | Nulo | Clave | Descripción |
|---|---|---|---|---|
| `user_id` | INTEGER | no | PK, FK → users.id | — |
| `reservoir_code` | VARCHAR(20) | no | PK, FK → reservoirs.code | — |

## users

Base class used for declarative class definitions. The :class:`_orm.DeclarativeBase` allows for the creation of new declarative bases in such a way that is compatible with type checkers:: from sqlalchemy.orm import DeclarativeBase class Base(DeclarativeBase): pass The above ``Base`` class is now usable as the base for new declarative mappings. The superclass makes use of the ``__init_subclass__()`` method to set up new classes and metaclasses aren't used. When first used, the :class:`_orm.DeclarativeBase` class instantiates a new :class:`_orm.registry` to be used with the base, assuming one was not provided explicitly. The :class:`_orm.DeclarativeBase` class supports class-level attributes which act as parameters for the construction of this registry; such as to indicate a specific :class:`_schema.MetaData` collection as well as a specific value for :paramref:`_orm.registry.type_annotation_map`:: from typing import Annotated from sqlalchemy import BigInteger from sqlalchemy import MetaData from sqlalchemy import String from sqlalchemy.orm import DeclarativeBase bigint = Annotated[int, "bigint"] my_metadata = MetaData() class Base(DeclarativeBase): metadata = my_metadata type_annotation_map = { str: String().with_variant(String(255), "mysql", "mariadb"), bigint: BigInteger(), } Class-level attributes which may be specified include: :param metadata: optional :class:`_schema.MetaData` collection. If a :class:`_orm.registry` is constructed automatically, this :class:`_schema.MetaData` collection will be used to construct it. Otherwise, the local :class:`_schema.MetaData` collection will supersede that used by an existing :class:`_orm.registry` passed using the :paramref:`_orm.DeclarativeBase.registry` parameter. :param type_annotation_map: optional type annotation map that will be passed to the :class:`_orm.registry` as :paramref:`_orm.registry.type_annotation_map`. :param registry: supply a pre-existing :class:`_orm.registry` directly. .. versionadded:: 2.0 Added :class:`.DeclarativeBase`, so that declarative base classes may be constructed in such a way that is also recognized by :pep:`484` type checkers. As a result, :class:`.DeclarativeBase` and other subclassing-oriented APIs should be seen as superseding previous "class returned by a function" APIs, namely :func:`_orm.declarative_base` and :meth:`_orm.registry.generate_base`, where the base class returned cannot be recognized by type checkers without using plugins. **__init__ behavior** In a plain Python class, the base-most ``__init__()`` method in the class hierarchy is ``object.__init__()``, which accepts no arguments. However, when the :class:`_orm.DeclarativeBase` subclass is first declared, the class is given an ``__init__()`` method that links to the :paramref:`_orm.registry.constructor` constructor function, if no ``__init__()`` method is already present; this is the usual declarative constructor that will assign keyword arguments as attributes on the instance, assuming those attributes are established at the class level (i.e. are mapped, or are linked to a descriptor). This constructor is **never accessed by a mapped class without being called explicitly via super()**, as mapped classes are themselves given an ``__init__()`` method directly which calls :paramref:`_orm.registry.constructor`, so in the default case works independently of what the base-most ``__init__()`` method does. .. versionchanged:: 2.0.1 :class:`_orm.DeclarativeBase` has a default constructor that links to :paramref:`_orm.registry.constructor` by default, so that calls to ``super().__init__()`` can access this constructor. Previously, due to an implementation mistake, this default constructor was missing, and calling ``super().__init__()`` would invoke ``object.__init__()``. The :class:`_orm.DeclarativeBase` subclass may also declare an explicit ``__init__()`` method which will replace the use of the :paramref:`_orm.registry.constructor` function at this level:: class Base(DeclarativeBase): def __init__(self, id=None): self.id = id Mapped classes still will not invoke this constructor implicitly; it remains only accessible by calling ``super().__init__()``:: class MyClass(Base): def __init__(self, id=None, name=None): self.name = name super().__init__(id=id) Note that this is a different behavior from what functions like the legacy :func:`_orm.declarative_base` would do; the base created by those functions would always install :paramref:`_orm.registry.constructor` for ``__init__()``.

| Columna | Tipo | Nulo | Clave | Descripción |
|---|---|---|---|---|
| `id` | INTEGER | no | PK | — |
| `email` | VARCHAR(254) | no | único | — |
| `full_name` | VARCHAR(120) | no | — | — |
| `role` | ENUM(GERENCIA, INGENIERO, OPERADOR) | no | — | — |
| `password_hash` | VARCHAR(255) | no | — | — |
| `is_active` | BOOLEAN | no | — | — |
| `must_change_password` | BOOLEAN | no | — | — |
| `failed_attempts` | INTEGER | no | — | — |
| `token_version` | INTEGER | no | — | — |
| `locked_until` | TIMESTAMP WITH TIME ZONE | sí | — | — |
| `last_login_at` | TIMESTAMP WITH TIME ZONE | sí | — | — |
| `password_changed_at` | TIMESTAMP WITH TIME ZONE | sí | — | — |
| `created_at` | TIMESTAMP WITH TIME ZONE | no | — | — |
| `updated_at` | TIMESTAMP WITH TIME ZONE | no | — | — |
