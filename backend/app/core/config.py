"""Configuración central de la aplicación, leída de variables de entorno y del archivo .env."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
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

    @field_validator("log_level")
    @classmethod
    def _upper(cls, value: str) -> str:
        return value.upper()

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
