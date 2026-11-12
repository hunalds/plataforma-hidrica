"""Configuración central de la aplicación, leída de variables de entorno y del archivo .env."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

# plataforma-hidrica/ (raíz del repositorio): backend/app/core/config.py -> parents[3]
ROOT_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: Literal["development", "test", "production"] = "development"
    app_name: str = "Plataforma Hídrica Zulia"
    log_level: str = "INFO"

    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "plataforma_hidrica"
    db_name_test: str = "plataforma_hidrica_test"
    db_user: str = "hidrica_app"
    db_password: SecretStr = Field(..., min_length=1)
    db_connect_timeout: int = 3

    # Se escribe en .env como lista separada por comas: CORS_ORIGINS=http://a,http://b
    cors_origins: str = "http://localhost:5173"

    # Fuente satelital activa (ver app/services/satellite/registry.py)
    satellite_provider: str = "mock"

    # --- Machine Learning (M6) ---
    # Carpeta de artefactos (fuera de Git). Por defecto ml/models del repositorio.
    ml_models_dir: Path = ROOT_DIR / "ml" / "models"
    # Fuente de lluvia/humedad para entrenar: "sintetico" (coherente con el histórico sintético)
    # o "real" (CHIRPS + ERA5-Land). Cambiar a "real" cuando lleguen los datos de MINAGUAS (C-24).
    ml_satellite_source: Literal["sintetico", "real"] = "sintetico"
    ml_reports_dir: Path = ROOT_DIR / "ml" / "reports"

    # --- Seguridad (M1) ---
    # En pruebas se acepta un secreto por defecto; en desarrollo/producción debe venir del .env
    jwt_secret: SecretStr = SecretStr("solo-para-pruebas-no-usar-en-produccion-0123456789")
    jwt_algorithm: str = "HS256"
    jwt_access_minutes: int = 15
    jwt_refresh_days: int = 7
    session_idle_minutes: int = 30  # cierre de sesión por inactividad (refresh sin uso)
    login_max_attempts: int = 5  # intentos fallidos antes del bloqueo temporal
    login_lockout_minutes: int = 15
    login_rate_limit_per_minute: int = 10  # por IP
    password_reset_minutes: int = 30
    frontend_url: str = "http://localhost:5173"  # para armar el enlace de recuperación

    # --- Correo (M1 recuperación de contraseña; M9 alertas) ---
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: SecretStr = SecretStr("")
    smtp_from: str = ""

    @field_validator("log_level")
    @classmethod
    def _upper(cls, value: str) -> str:
        return value.upper()

    @model_validator(mode="after")
    def _strong_secret_outside_tests(self) -> Settings:
        secret = self.jwt_secret.get_secret_value()
        if self.app_env != "test" and (
            len(secret) < 32 or secret.startswith(("solo-para-pruebas", "genera-"))
        ):
            raise ValueError("JWT_SECRET debe definirse en .env con al menos 32 caracteres aleatorios")
        return self

    @property
    def effective_db_name(self) -> str:
        """En el entorno de pruebas se usa siempre la base de pruebas."""
        return self.db_name_test if self.app_env == "test" else self.db_name

    @property
    def database_url(self) -> URL:
        return URL.create(
            "postgresql+psycopg",
            username=self.db_user,
            password=self.db_password.get_secret_value(),
            host=self.db_host,
            port=self.db_port,
            database=self.effective_db_name,
        )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
