from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_health_ok_reports_postgis(client: TestClient):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["environment"] == "test"
    assert body["postgis"] and body["postgis"][0].isdigit()


def test_health_returns_503_without_leaking_secrets(settings: Settings):
    # Puerto 1: no hay servidor, la conexión falla de inmediato
    broken = settings.model_copy(update={"db_port": 1, "db_connect_timeout": 1})
    with TestClient(create_app(broken)) as c:
        r = c.get("/health")
    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "degraded"
    assert body["database"] == "error"
    assert body["detail"] == "No se pudo conectar a la base de datos"
    assert settings.db_password.get_secret_value() not in r.text


def test_openapi_docs_available(client: TestClient):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    assert "/health" in r.json()["paths"]
