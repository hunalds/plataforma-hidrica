"""Iteración 6: alertas tempranas (M9) y reportes (M10)."""

from __future__ import annotations

import io
import json
from datetime import date, timedelta

import pytest
from openpyxl import load_workbook

from app.cli import main as cli
from app.core.config import Settings
from app.models.alert import Alert, AlertRecipient
from app.models.user import Role
from app.services import alerts as svc
from app.services import geo
from app.services.notifications import DeliveryResult

YESTERDAY = date.today() - timedelta(days=1)
THRESHOLDS = {"low_critical": 27.5, "low_alert": 29.0, "high_alert": 33.0, "spill_level": 33.4}


class FakeChannel:
    def __init__(self, name):
        self.name, self.sent = name, []

    def send(self, alert, reservoir_name, target):
        self.sent.append((alert.severity, alert.title, target))
        return DeliveryResult("enviada")


@pytest.fixture
def channels(app):
    fake = {
        "correo": FakeChannel("correo"),
        "telegram": FakeChannel("telegram"),
        "sms": FakeChannel("sms"),
        "whatsapp": FakeChannel("whatsapp"),
    }
    app.state.channels = fake
    return fake


@pytest.fixture
def tule(client, db, auth_headers, reservoirs, channels):
    assert cli(["load-synthetic-curves"]) == 0
    ing = auth_headers(Role.INGENIERO, reservoirs=["TULE", "MANUELOTE", "TRES_RIOS"])
    client.put("/reservoirs/TULE/thresholds", headers=ing, json=THRESHOLDS)
    db.add(
        AlertRecipient(
            name="Director Estadal",
            channel="correo",
            target="director@hidrica-zulia.com",
            min_severity="alerta",
        )
    )
    db.add(
        AlertRecipient(
            name="Sala situacional",
            channel="telegram",
            target="123456",
            reservoir_code="TULE",
            min_severity="critica",
        )
    )
    db.commit()
    return ing


def record(client, h, level, day=YESTERDAY):
    return client.post(
        "/reservoirs/TULE/measurements",
        headers=h,
        json={"day": day.isoformat(), "level_m": level, "outflow_m3s": 4, "eco_flow_m3s": 0.4},
    )


# ---------------------------------------------------------------- disparadores observados


def test_observed_alert_is_created_notified_and_not_duplicated(client, db, tule, channels):
    record(client, tule, 28.5, YESTERDAY - timedelta(days=2))  # bajo alerta → se evalúa en segundo plano
    alerts = db.query(Alert).all()
    assert len(alerts) == 1 and alerts[0].severity == "alerta" and alerts[0].direction == "escasez"
    assert channels["correo"].sent and not channels["telegram"].sent  # telegram solo críticas

    record(client, tule, 28.4, YESTERDAY - timedelta(days=1))  # sigue en alerta: se actualiza, no se duplica
    db.expire_all()
    assert db.query(Alert).count() == 1 and len(channels["correo"].sent) == 1

    record(client, tule, 27.3)  # escala a crítica: misma alerta, nueva notificación (también por Telegram)
    db.expire_all()
    a = db.query(Alert).one()
    assert a.severity == "critica" and len(channels["telegram"].sent) == 1 and len(a.deliveries) == 3


def test_alert_resolves_when_condition_disappears(client, db, tule):
    record(client, tule, 28.5, YESTERDAY - timedelta(days=1))
    record(client, tule, 31.0)
    db.expire_all()
    assert db.query(Alert).one().resolved_at is not None


def test_flood_direction(client, db, tule):
    record(client, tule, 33.6)
    a = db.query(Alert).one()
    assert (a.direction, a.severity) == ("inundacion_alivio", "critica") and "aliviando" in a.title


def test_projected_conditions_from_forecast():
    settings = Settings(app_env="test")
    forecast = {
        "origin": "2026-10-15",
        "normal_level": 33.4,
        "horizons": [{"horizon_days": 30, "spill_probability": 0.05}],
        "probabilities": [
            {"threshold": "low_critical", "level": 27.5, "horizon_days": 30, "probability": 0.3},
            {"threshold": "low_alert", "level": 29.0, "horizon_days": 30, "probability": 0.7},
        ],
    }
    conds = svc.projected_conditions(forecast, settings)
    assert [(c.severity, c.threshold, c.kind) for c in conds] == [("alerta", "low_alert", "proyectada")]
    forecast["probabilities"][1]["probability"] = 0.25
    assert [c.severity for c in svc.projected_conditions(forecast, settings)] == ["informativa"]
    forecast["horizons"][0]["spill_probability"] = 0.8
    assert "inundacion_alivio" in {c.direction for c in svc.projected_conditions(forecast, settings)}


def test_default_thresholds_use_official_levels(db, reservoirs):
    from app.models.reservoir import Reservoir

    th = svc.thresholds_for(db.get(Reservoir, "TULE"))
    assert th == {"low_critical": 26.6, "spill_level": 33.4}


# ---------------------------------------------------------------- API de alertas


def test_list_ack_and_visibility(client, db, tule, auth_headers):
    record(client, tule, 28.5)
    op = auth_headers(Role.OPERADOR, reservoirs=["TULE"])
    other = auth_headers(Role.OPERADOR, email="op2@hidrica-zulia.com", reservoirs=["MANUELOTE"])
    items = client.get("/alerts?active=true", headers=op).json()
    assert len(items) == 1 and items[0]["acknowledged_by_me"] is False
    assert client.get("/alerts", headers=other).json() == []
    r = client.post(f"/alerts/{items[0]['id']}/ack", headers=op).json()
    assert (
        r["acknowledged_by_me"] is True and r["acknowledgements"][0]["user"] == "operador@hidrica-zulia.com"
    )
    assert client.post(f"/alerts/{items[0]['id']}/ack", headers=other).status_code == 404


def test_recipients_crud_is_engineer_only(client, tule, auth_headers):
    body = {
        "name": "Viceministro",
        "channel": "correo",
        "target": "vice@hidrica-zulia.com",
        "min_severity": "critica",
    }
    created = client.post("/alerts/recipients", headers=tule, json=body)
    assert created.status_code == 201
    rid = created.json()["id"]
    assert (
        client.post("/alerts/recipients", headers=tule, json={**body, "target": "sin-arroba"}).status_code
        == 422
    )
    assert (
        client.put(f"/alerts/recipients/{rid}", headers=tule, json={**body, "active": False}).json()["active"]
        is False
    )
    assert client.post(f"/alerts/recipients/{rid}/test", headers=tule).json()["status"] == "enviada"
    assert client.delete(f"/alerts/recipients/{rid}", headers=tule).status_code == 204
    op = auth_headers(Role.OPERADOR, email="op9@hidrica-zulia.com", reservoirs=["TULE"])
    assert client.get("/alerts/recipients", headers=op).status_code == 403


def test_telegram_and_pending_channels_without_configuration():
    from app.services.notifications import PendingProviderChannel, TelegramChannel

    a = Alert(reservoir_code="TULE", severity="alerta", title="t", message="m")
    assert TelegramChannel(Settings(app_env="test")).send(a, "Tulé", "1").status == "omitida"
    assert PendingProviderChannel("sms").send(a, "Tulé", "+58").status == "omitida"


# ---------------------------------------------------------------- reportes


@pytest.fixture
def report_data(client, db, tule):
    assert cli(["load-synthetic-measurements", "--until", "2026-10-15"]) == 0
    geo.apply_osm_geometries(db)
    db.commit()
    return tule


@pytest.mark.parametrize("fmt", ["pdf", "xlsx", "csv", "png", "geojson", "kml"])
def test_bulletin_in_every_format(client, report_data, fmt):
    r = client.get(f"/reports/bulletin?format={fmt}", headers=report_data)
    assert r.status_code == 200, r.text
    assert "attachment" in r.headers["content-disposition"]
    body = r.content
    if fmt == "pdf":
        assert body[:4] == b"%PDF"
    elif fmt == "xlsx":
        ws = load_workbook(io.BytesIO(body)).active
        assert ws["A1"].value == "Boletín diario de embalses" and ws["A4"].value == "Embalse"
    elif fmt == "csv":
        assert body.decode("utf-8-sig").startswith("Embalse,Fecha del dato,Cota (m)")
    elif fmt == "png":
        assert body[:8] == b"\x89PNG\r\n\x1a\n"
    elif fmt == "geojson":
        fc = json.loads(body)
        assert len(fc["features"]) == 3 and "Estado" in fc["features"][0]["properties"]
    else:
        assert b"<kml" in body and b"Tul" in body


def test_comparison_historical_and_alerts_reports(client, report_data):
    h = report_data
    assert (
        client.get(
            "/reports/comparison?date_from=2026-01-01&date_to=2026-06-30&format=xlsx", headers=h
        ).status_code
        == 200
    )
    r = client.get(
        "/reports/historical/TULE?a_from=2015-01-01&a_to=2015-03-31&b_from=2025-01-01&b_to=2025-03-31&format=csv",
        headers=h,
    )
    assert r.status_code == 200 and "Período" in r.content.decode("utf-8-sig")
    assert client.get("/reports/alerts?format=pdf", headers=h).status_code == 200
    assert client.get("/reports/alerts?format=kml", headers=h).status_code == 422  # sin geometría
    assert client.get("/reports/prediction/TULE?format=pdf", headers=h).status_code == 404  # aún sin modelo


def test_reports_permissions(client, report_data, auth_headers):
    op = auth_headers(Role.OPERADOR, email="op5@hidrica-zulia.com", reservoirs=["TULE"])
    assert client.get("/reports/bulletin", headers=op).status_code == 403
    ger = auth_headers(Role.GERENCIA, email="jefe@hidrica-zulia.com")
    assert client.get("/reports/bulletin?format=csv", headers=ger).status_code == 200
