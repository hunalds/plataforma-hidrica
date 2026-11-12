import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.main import create_app


def test_missing_db_password_is_rejected(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("DB_PASSWORD", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_test_env_uses_test_database():
    s = Settings(app_env="test", db_password="x", _env_file=None)
    assert s.effective_db_name == s.db_name_test
    assert s.database_url.database == "plataforma_hidrica_test"


def test_password_is_hidden_in_repr():
    s = Settings(db_password="super-secreta", _env_file=None)
    assert "super-secreta" not in repr(s)
    assert "super-secreta" not in str(s.database_url)  # SQLAlchemy enmascara la contraseña


def test_cors_origin_list_parsing():
    s = Settings(db_password="x", cors_origins="http://a.com, http://b.com ,", _env_file=None)
    assert s.cors_origin_list == ["http://a.com", "http://b.com"]


def test_cors_only_allows_configured_origins(settings: Settings):
    app = create_app(settings.model_copy(update={"cors_origins": "http://permitido.test"}))
    with TestClient(app) as c:
        ok = c.options(
            "/health",
            headers={"Origin": "http://permitido.test", "Access-Control-Request-Method": "GET"},
        )
        bad = c.options(
            "/health",
            headers={"Origin": "http://malicioso.test", "Access-Control-Request-Method": "GET"},
        )
    assert ok.headers.get("access-control-allow-origin") == "http://permitido.test"
    assert "access-control-allow-origin" not in bad.headers


def test_cors_exposes_content_disposition_for_downloads(settings: Settings):
    app = create_app(settings.model_copy(update={"cors_origins": "http://permitido.test"}))
    with TestClient(app) as c:
        r = c.get("/reservoirs/curve-template.csv", headers={"Origin": "http://permitido.test"})
    assert "content-disposition" in r.headers.get("access-control-expose-headers", "").lower()
