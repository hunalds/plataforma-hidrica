"""HU-2.3 (control de calidad) y HU-2.4 (importación con vista previa) con los ejemplos sintéticos."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from app.cli import main as cli
from app.models.user import Role
from app.services.ingest import TEMPLATE_COLUMNS
from app.services.tabular import to_date, to_float

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "ml" / "data" / "synthetic" / "ejemplos"
VALID_XLSX = EXAMPLES / "importacion_valida_2026-10-16_al_31.xlsx"
VALID_VE_CSV = EXAMPLES / "importacion_valida_formato_venezolano.csv"
ERRORS_XLSX = EXAMPLES / "importacion_con_errores.xlsx"
ALL = ["TULE", "MANUELOTE", "TRES_RIOS"]


@pytest.fixture
def curves(app, reservoirs):
    assert cli(["load-synthetic-curves"]) == 0


@pytest.fixture
def ing(auth_headers, reservoirs):
    return auth_headers(Role.INGENIERO, reservoirs=ALL)


def preview(client, headers, path: Path):
    mime = (
        "text/csv"
        if path.suffix == ".csv"
        else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    return client.post(
        "/ingest/preview", headers=headers, files={"file": (path.name, path.read_bytes(), mime)}
    )


# ---------------------------------------------------------------- lectura


def test_template_matches_ml_schema_and_synthetic_dataset():
    header = (
        (ROOT / "ml" / "data" / "synthetic" / "movimiento_diario_sintetico.csv")
        .open(encoding="utf-8")
        .readline()
    )
    assert [c[0] for c in TEMPLATE_COLUMNS] == header.strip().split(",")


def test_templates_are_downloadable(client):
    csv_t = client.get("/ingest/template.csv")
    assert csv_t.status_code == 200 and csv_t.text.startswith("embalse,fecha,hora,cota_msnm")
    xlsx = client.get("/ingest/template.xlsx")
    assert xlsx.status_code == 200 and xlsx.content[:2] == b"PK"  # zip (xlsx)


@pytest.mark.parametrize(
    ("value", "expected"),
    [("26,5", 26.5), ("1.234,56", 1234.56), ("1,234.5", 1234.5), (" 7 ", 7.0), ("", None), (3, 3.0)],
)
def test_number_parsing(value, expected):
    assert to_float(value) == expected


@pytest.mark.parametrize("value", ["2026-10-16", "16/10/2026", "16-10-2026", "2026/10/16"])
def test_date_parsing(value):
    assert to_date(value).isoformat() == "2026-10-16"


# ---------------------------------------------------------------- vista previa y confirmación


def test_valid_file_preview_then_confirm(client, ing, curves):
    r = preview(client, ing, VALID_XLSX)
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["status"] == "PREVIEW"
    assert b["summary"]["filas_validas"] == 48 and b["summary"]["errores"] == 0
    assert set(b["summary"]["por_embalse"]) == set(ALL)
    assert len(b["sample"]) == 20 and b["sample"][0]["volume_source"] == "REPORTADO"

    # Nada se guarda hasta confirmar
    assert client.get("/reservoirs/TULE/measurements", headers=ing).json() == []
    c = client.post(f"/ingest/batches/{b['id']}/confirm", headers=ing, json={"overwrite": False})
    assert c.status_code == 200 and c.json() == {"inserted": 48, "updated": 0, "skipped": 0}
    rows = client.get("/reservoirs/TULE/measurements", headers=ing).json()
    assert len(rows) == 16 and rows[0]["day"] == "2026-10-31"
    assert rows[0]["useful_volume_hm3"] is not None and rows[0]["reserve_days"] is not None
    # Confirmar dos veces no se permite
    assert client.post(f"/ingest/batches/{b['id']}/confirm", headers=ing, json={}).status_code == 409


def test_venezuelan_csv_format_gives_same_result(client, ing, curves):
    xlsx = preview(client, ing, VALID_XLSX).json()
    ve = preview(client, ing, VALID_VE_CSV).json()
    assert ve["summary"]["filas_validas"] == xlsx["summary"]["filas_validas"] == 48
    assert ve["summary"]["errores"] == 0
    assert ve["sample"][0]["level_m"] == xlsx["sample"][0]["level_m"]


def test_reimport_detects_existing_days_and_respects_overwrite(client, ing, curves):
    first = preview(client, ing, VALID_XLSX).json()
    client.post(f"/ingest/batches/{first['id']}/confirm", headers=ing, json={})
    again = preview(client, ing, VALID_XLSX).json()
    assert again["summary"]["por_embalse"]["TULE"]["existentes"] == 16
    assert any(i["code"] == "EXISTS" for i in again["issues"])
    skipped = client.post(
        f"/ingest/batches/{again['id']}/confirm", headers=ing, json={"overwrite": False}
    ).json()
    assert skipped == {"inserted": 0, "updated": 0, "skipped": 48}
    third = preview(client, ing, VALID_XLSX).json()
    replaced = client.post(
        f"/ingest/batches/{third['id']}/confirm", headers=ing, json={"overwrite": True}
    ).json()
    assert replaced == {"inserted": 0, "updated": 48, "skipped": 0}


def test_quality_control_detects_every_injected_error(client, ing, curves):
    b = preview(client, ing, ERRORS_XLSX).json()
    codes = {(i["severity"], i["code"]) for i in b["issues"]}
    for code in (
        "DUPLICATE",
        "BAD_DATE",
        "NOT_NUMERIC",
        "MISSING",
        "NEGATIVE",
        "OUT_OF_RANGE",
        "OUT_OF_CURVE",
        "UNKNOWN_RESERVOIR",
        "FUTURE_DATE",
    ):
        assert ("error", code) in codes, code
    for code in ("SUDDEN_JUMP", "MISSING_DAYS"):
        assert ("aviso", code) in codes, code
    # Cada error indica la fila del archivo
    assert all(i["row"] for i in b["issues"] if i["severity"] == "error")
    gap = next(i for i in b["issues"] if i["code"] == "MISSING_DAYS" and i["reservoir"] == "TRES_RIOS")
    assert "2026-10-27 a 2026-10-28" in gap["message"]
    # Las filas con error no se guardan; las demás sí
    assert b["summary"]["filas_con_error"] >= 9
    assert 0 < b["summary"]["filas_validas"] < 48


def test_jump_is_measured_against_data_already_in_database(client, db, ing, curves):
    # Base hasta el 15/10; el archivo empieza el 16/10: el salto del primer día se compara con la base
    assert cli(["load-synthetic-measurements", "--until", "2026-10-15"]) == 0
    content = (
        b"embalse,fecha,cota_msnm\n"
        b"TULE,2026-10-16,32.80\n"  # el 15/10 sintético está cerca de 29,2 m → salto > 1 m
    )
    b = client.post("/ingest/preview", headers=ing, files={"file": ("salto.csv", content, "text/csv")}).json()
    jump = [i for i in b["issues"] if i["code"] == "SUDDEN_JUMP"]
    assert jump and "+3." in jump[0]["message"]


def test_volume_is_computed_from_curve_when_missing(client, ing, curves):
    content = b"embalse,fecha,cota_msnm\nTULE,2026-10-16,30.00\n"
    b = client.post("/ingest/preview", headers=ing, files={"file": ("v.csv", content, "text/csv")}).json()
    row = b["sample"][0]
    assert row["volume_source"] == "CURVA" and row["curve_version"] == 1 and row["volume_hm3"] > 0


def test_no_curve_is_a_warning_not_an_error(client, ing, reservoirs):
    content = b"embalse,fecha,cota_msnm\nTULE,2026-10-16,30.00\n"
    b = client.post("/ingest/preview", headers=ing, files={"file": ("v.csv", content, "text/csv")}).json()
    assert b["summary"]["filas_validas"] == 1
    assert any(i["code"] == "NO_CURVE" and i["severity"] == "aviso" for i in b["issues"])


def test_missing_required_columns(client, ing, reservoirs):
    b = client.post(
        "/ingest/preview", headers=ing, files={"file": ("x.csv", b"a,b\n1,2\n", "text/csv")}
    ).json()
    assert b["summary"]["filas_validas"] == 0
    assert b["issues"][0]["code"] == "MISSING_COLUMNS"


# ---------------------------------------------------------------- permisos


def test_operador_and_gerencia_cannot_import(client, auth_headers, reservoirs):
    for role in (Role.OPERADOR, Role.GERENCIA):
        h = auth_headers(role, reservoirs=ALL)
        assert preview(client, h, VALID_XLSX).status_code == 403


def test_rows_of_unassigned_reservoirs_are_rejected(client, auth_headers, curves):
    h = auth_headers(Role.INGENIERO, reservoirs=["TULE"])
    b = preview(client, h, VALID_XLSX).json()
    assert b["summary"]["filas_validas"] == 16
    assert sum(1 for i in b["issues"] if i["code"] == "NOT_ASSIGNED") == 32


def test_only_uploader_can_confirm(client, auth_headers, make_user, login, curves):
    a = auth_headers(Role.INGENIERO, reservoirs=ALL)
    b_user = make_user(Role.INGENIERO, email="otro@hidrica-zulia.com", reservoirs=ALL)
    other = {"Authorization": f"Bearer {login(b_user.email)['access_token']}"}
    batch = preview(client, a, VALID_XLSX).json()
    assert client.post(f"/ingest/batches/{batch['id']}/confirm", headers=other, json={}).status_code == 403


def test_import_is_audited(client, ing, auth_headers, curves):
    batch = preview(client, ing, VALID_XLSX).json()
    client.post(f"/ingest/batches/{batch['id']}/confirm", headers=ing, json={})
    admin = auth_headers(Role.GERENCIA, email="jefe@hidrica-zulia.com")
    actions = [e["action"] for e in client.get("/audit?action=ingest", headers=admin).json()["items"]]
    assert actions == ["ingest.confirm", "ingest.preview"]


# ---------------------------------------------------------------- carga del histórico sintético (HU-2.7)


def test_load_full_synthetic_history_without_errors(client, ing, curves, capsys):
    assert cli(["load-synthetic-measurements"]) == 0
    out = capsys.readouterr().out
    assert "errores: 0" in out
    with (ROOT / "ml" / "data" / "synthetic" / "movimiento_diario_sintetico.csv").open(
        encoding="utf-8"
    ) as fh:
        expected = sum(1 for r in csv.DictReader(fh) if r["fecha"] <= "2026-10-15")
    assert f"insertadas: {expected}" in out
    status = {s["reservoir_code"]: s for s in client.get("/reservoirs/status", headers=ing).json()}
    assert status["TULE"]["last_day"] == "2026-10-15"
    assert status["TULE"]["availability_pct"] is not None
