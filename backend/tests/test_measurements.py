"""HU-2.5 (registro manual del Operador) y HU-2.6 (estado operativo, semáforo y balance)."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import update

from app.cli import main as cli
from app.core.security import utcnow
from app.models.measurement import DailyMeasurement
from app.models.user import Role

TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)


@pytest.fixture
def curves(app, reservoirs):
    assert cli(["load-synthetic-curves"]) == 0


@pytest.fixture
def op(auth_headers, curves):
    return auth_headers(Role.OPERADOR, reservoirs=["TULE"])


def record(day: date, level: float = 30.0, **kw) -> dict:
    return {
        "day": day.isoformat(),
        "reading_time": "08:00",
        "level_m": level,
        "inflow_m3s": 6,
        "outflow_m3s": 4,
        "eco_flow_m3s": 0.4,
        **kw,
    }


# ---------------------------------------------------------------- registro manual


def test_operator_registers_daily_movement_with_calculations(client, op):
    r = client.post("/reservoirs/TULE/measurements", headers=op, json=record(YESTERDAY))
    assert r.status_code == 201, r.text
    m = r.json()["measurement"]
    assert m["source"] == "MANUAL" and m["volume_source"] == "CURVA"
    assert m["useful_volume_hm3"] > 0 and 0 < m["availability_pct"] < 100
    # días de reserva = útil / ((4 + 0,4) · 0,0864)
    assert m["reserve_days"] == pytest.approx(m["useful_volume_hm3"] / (4.4 * 0.0864), abs=0.1)


def test_duplicate_day_future_date_and_unassigned_reservoir(client, op):
    assert client.post("/reservoirs/TULE/measurements", headers=op, json=record(YESTERDAY)).status_code == 201
    dup = client.post("/reservoirs/TULE/measurements", headers=op, json=record(YESTERDAY))
    assert dup.status_code == 409 and dup.json()["detail"]["code"] == "ALREADY_EXISTS"
    future = client.post("/reservoirs/TULE/measurements", headers=op, json=record(TODAY + timedelta(days=1)))
    assert future.status_code == 422 and "posterior a hoy" in future.json()["detail"]["message"]
    assert (
        client.post("/reservoirs/MANUELOTE/measurements", headers=op, json=record(YESTERDAY)).status_code
        == 404
    )


def test_invalid_values_are_rejected_with_clear_messages(client, op):
    r = client.post(
        "/reservoirs/TULE/measurements",
        headers=op,
        json=record(YESTERDAY, gate_opening_pct=120, outflow_m3s=-1),
    )
    assert r.status_code == 422
    msg = r.json()["detail"]["message"]
    assert "compuertas" in msg and "negativo" in msg
    out_of_curve = client.post("/reservoirs/TULE/measurements", headers=op, json=record(YESTERDAY, level=3.0))
    assert (
        out_of_curve.status_code == 422
        and "fuera del rango de la curva" in out_of_curve.json()["detail"]["message"]
    )


def test_sudden_jump_is_saved_but_flagged(client, op):
    client.post(
        "/reservoirs/TULE/measurements", headers=op, json=record(YESTERDAY - timedelta(days=1), level=30.0)
    )
    r = client.post("/reservoirs/TULE/measurements", headers=op, json=record(YESTERDAY, level=31.6))
    assert r.status_code == 201
    assert [w["code"] for w in r.json()["warnings"]] == ["SUDDEN_JUMP"]
    assert r.json()["measurement"]["quality_flags"] == ["SUDDEN_JUMP"]


def test_operator_corrects_own_record_within_24h_only(client, db, op, make_user, login):
    client.post("/reservoirs/TULE/measurements", headers=op, json=record(YESTERDAY, level=30.0))
    r = client.patch(f"/reservoirs/TULE/measurements/{YESTERDAY}", headers=op, json={"level_m": 30.2})
    assert r.status_code == 200
    m = r.json()["measurement"]
    assert m["level_m"] == 30.2 and m["volume_source"] == "CURVA"  # el volumen se recalculó

    db.execute(update(DailyMeasurement).values(created_at=utcnow() - timedelta(hours=25)))
    db.commit()
    late = client.patch(f"/reservoirs/TULE/measurements/{YESTERDAY}", headers=op, json={"level_m": 30.3})
    assert late.status_code == 403

    other = make_user(Role.OPERADOR, email="op2@hidrica-zulia.com", reservoirs=["TULE"])
    h2 = {"Authorization": f"Bearer {login(other.email)['access_token']}"}
    assert (
        client.patch(
            f"/reservoirs/TULE/measurements/{YESTERDAY}", headers=h2, json={"level_m": 30.4}
        ).status_code
        == 403
    )


def test_engineer_correction_is_audited_with_old_and_new(client, op, auth_headers):
    client.post("/reservoirs/TULE/measurements", headers=op, json=record(YESTERDAY, level=30.0))
    ing = auth_headers(Role.INGENIERO, reservoirs=["TULE"])
    assert (
        client.patch(
            f"/reservoirs/TULE/measurements/{YESTERDAY}", headers=ing, json={"inflow_m3s": 9.5}
        ).status_code
        == 200
    )
    admin = auth_headers(Role.GERENCIA, email="jefe@hidrica-zulia.com")
    entry = client.get("/audit?action=measurement.update", headers=admin).json()["items"][0]
    assert entry["old_value"] == {"inflow_m3s": 6.0} and entry["new_value"] == {"inflow_m3s": 9.5}


def test_gerencia_reads_but_does_not_register(client, auth_headers, curves):
    h = auth_headers(Role.GERENCIA)
    assert client.post("/reservoirs/TULE/measurements", headers=h, json=record(YESTERDAY)).status_code == 403
    assert client.get("/reservoirs/TULE/measurements", headers=h).status_code == 200


# ---------------------------------------------------------------- estado operativo y semáforo


def test_status_without_data_is_gray(client, op):
    s = client.get("/reservoirs/TULE/status", headers=op).json()
    assert s["light"] == "gris" and s["level_m"] is None and s["is_stale"] is True


@pytest.mark.parametrize(
    ("level", "light", "direction"),
    [
        (27.2, "rojo", "escasez"),
        (28.5, "amarillo", "escasez"),
        (31.0, "verde", "normal"),
        (33.5, "rojo", "inundacion_alivio"),
    ],
)
def test_status_traffic_light_follows_thresholds(client, op, auth_headers, level, light, direction):
    ing = auth_headers(Role.INGENIERO, reservoirs=["TULE"])
    client.put(
        "/reservoirs/TULE/thresholds",
        headers=ing,
        json={"low_critical": 27.5, "low_alert": 29.0, "high_alert": 33.0, "spill_level": 33.4},
    )
    client.post("/reservoirs/TULE/measurements", headers=op, json=record(YESTERDAY, level=level))
    s = client.get("/reservoirs/TULE/status", headers=op).json()
    assert (s["light"], s["direction"]) == (light, direction)
    assert s["thresholds_defined"] is True and s["is_stale"] is False and s["days_since_last"] == 1
    assert s["is_spilling"] is (level > 33.4)
    if level > 33.4:
        assert s["spill_hm3"] > 0 and s["availability_pct"] > 100


def test_status_marks_stale_data(client, op):
    client.post("/reservoirs/TULE/measurements", headers=op, json=record(TODAY - timedelta(days=5)))
    s = client.get("/reservoirs/TULE/status", headers=op).json()
    assert s["is_stale"] is True and s["days_since_last"] == 5


def test_all_status_respects_visibility(client, op, auth_headers):
    assert [s["reservoir_code"] for s in client.get("/reservoirs/status", headers=op).json()] == ["TULE"]
    admin = auth_headers(Role.GERENCIA, email="jefe@hidrica-zulia.com")
    assert len(client.get("/reservoirs/status", headers=admin).json()) == 3


# ---------------------------------------------------------------- balance


def test_balance_over_synthetic_history(client, auth_headers, curves):
    assert cli(["load-synthetic-measurements", "--until", "2026-10-15"]) == 0
    h = auth_headers(Role.GERENCIA)
    b = client.get("/reservoirs/TRES_RIOS/balance?date_from=2025-01-01&date_to=2025-12-31", headers=h).json()
    assert len(b["days"]) == 365
    t = b["totals"]
    # identidad del balance: observado = neto − alivio + residuo
    assert t["observed_change_hm3"] == pytest.approx(
        t["net_hm3"] - t["spill_estimate_hm3"] + t["residual_hm3"], abs=0.01
    )
    assert "P-09 a P-13" in b["note"]


def test_balance_range_limit(client, auth_headers, curves):
    h = auth_headers(Role.GERENCIA)
    r = client.get("/reservoirs/TULE/balance?date_from=2005-01-01&date_to=2026-01-01", headers=h)
    assert r.status_code == 422
