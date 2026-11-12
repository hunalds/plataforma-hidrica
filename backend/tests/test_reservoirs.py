"""HU-1.6 (ficha, umbrales y geometría de embalses) y HU-1.7 (curva cota–volumen versionada)."""

from __future__ import annotations

import io

import pytest
from openpyxl import Workbook

from app.models.user import Role
from app.services.curves import (
    CurveFileError,
    CurveInterpolator,
    CurvePoint,
    CurveRangeError,
    parse_curve_file,
)

CURVE_CSV = b"cota_msnm,area_km2,volumen_hm3\n26.0,10,20\n27.0,12,31\n30.0,18,76\n34.0,26,166\n"

# Polígono sencillo de prueba (no representa ningún embalse real)
SQUARE = {
    "type": "Polygon",
    "coordinates": [[[-71.0, 10.0], [-70.9, 10.0], [-70.9, 10.1], [-71.0, 10.1], [-71.0, 10.0]]],
}


# ---------------------------------------------------------------- HU-1.6 ficha y visibilidad


def test_seed_creates_three_reservoirs_with_official_levels(client, auth_headers, reservoirs):
    r = client.get("/reservoirs", headers=auth_headers(Role.GERENCIA))
    assert r.status_code == 200
    by_code = {x["code"]: x for x in r.json()}
    assert set(by_code) == {"TULE", "MANUELOTE", "TRES_RIOS"}
    assert (by_code["TULE"]["normal_level"], by_code["TULE"]["dead_level"]) == (33.40, 26.60)
    assert (by_code["MANUELOTE"]["normal_level"], by_code["MANUELOTE"]["dead_level"]) == (48.00, 36.10)
    assert (by_code["TRES_RIOS"]["normal_level"], by_code["TRES_RIOS"]["dead_level"]) == (180.00, 139.50)
    assert by_code["TRES_RIOS"]["records_start"] == "2008-01-01"
    assert by_code["TULE"]["has_geometry"] is False  # los polígonos los cargan los autores


def test_non_gerencia_only_see_assigned_reservoirs(client, auth_headers, reservoirs):
    h = auth_headers(Role.OPERADOR, reservoirs=["TULE"])
    codes = [x["code"] for x in client.get("/reservoirs", headers=h).json()]
    assert codes == ["TULE"]
    assert client.get("/reservoirs/MANUELOTE", headers=h).status_code == 404
    assert client.get("/reservoirs/tule", headers=h).status_code == 200


def test_user_without_assignments_sees_none(client, auth_headers, reservoirs):
    assert client.get("/reservoirs", headers=auth_headers(Role.INGENIERO)).json() == []


def test_only_ingeniero_edits_reservoir(client, auth_headers, reservoirs):
    body = {"basin": "Río Cachirí"}
    for role in (Role.GERENCIA, Role.OPERADOR):
        h = auth_headers(role, reservoirs=["TULE"])
        assert client.patch("/reservoirs/TULE", headers=h, json=body).status_code == 403
    ing = auth_headers(Role.INGENIERO, reservoirs=["TULE"])
    r = client.patch("/reservoirs/TULE", headers=ing, json=body)
    assert r.status_code == 200 and r.json()["basin"] == "Río Cachirí"


def test_dead_level_must_be_below_normal(client, auth_headers, reservoirs):
    ing = auth_headers(Role.INGENIERO, reservoirs=["TULE"])
    r = client.patch("/reservoirs/TULE", headers=ing, json={"dead_level": 40})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "INVALID_LEVELS"


# ---------------------------------------------------------------- HU-1.6 umbrales


def test_thresholds_valid_order_and_audit(client, auth_headers, reservoirs):
    ing = auth_headers(Role.INGENIERO, reservoirs=["TULE"])
    body = {"low_critical": 27.5, "low_alert": 29.0, "high_alert": 33.0, "spill_level": 33.4}
    r = client.put("/reservoirs/TULE/thresholds", headers=ing, json=body)
    assert r.status_code == 200 and r.json()["low_alert"] == 29.0
    assert client.get("/reservoirs/TULE", headers=ing).json()["thresholds"]["spill_level"] == 33.4

    admin = auth_headers(Role.GERENCIA)
    entry = client.get("/audit?action=threshold.update", headers=admin).json()["items"][0]
    assert entry["entity_id"] == "TULE" and entry["new_value"]["low_alert"] == 29.0


@pytest.mark.parametrize(
    "body",
    [
        {"low_critical": 30.0, "low_alert": 29.0},  # crítico por encima de alerta
        {"low_alert": 31.0, "high_alert": 30.0},
        {"high_alert": 34.0, "spill_level": 33.4},
    ],
)
def test_thresholds_out_of_order_are_rejected(client, auth_headers, reservoirs, body):
    ing = auth_headers(Role.INGENIERO, reservoirs=["TULE"])
    assert client.put("/reservoirs/TULE/thresholds", headers=ing, json=body).status_code == 422


def test_critical_threshold_cannot_be_below_dead_level(client, auth_headers, reservoirs):
    ing = auth_headers(Role.INGENIERO, reservoirs=["TULE"])
    r = client.put("/reservoirs/TULE/thresholds", headers=ing, json={"low_critical": 20.0})
    assert r.status_code == 422 and "volumen muerto" in r.json()["detail"]["message"]


def test_operador_cannot_change_thresholds(client, auth_headers, reservoirs):
    op = auth_headers(Role.OPERADOR, reservoirs=["TULE"])
    assert client.put("/reservoirs/TULE/thresholds", headers=op, json={"low_alert": 29}).status_code == 403
    assert client.get("/reservoirs/TULE/thresholds", headers=op).status_code == 200


# ---------------------------------------------------------------- HU-1.6 geometría


def test_upload_polygon_geometry_as_feature(client, auth_headers, reservoirs):
    ing = auth_headers(Role.INGENIERO, reservoirs=["TULE"])
    feature = {"type": "Feature", "properties": {}, "geometry": SQUARE}
    r = client.put("/reservoirs/TULE/geometry", headers=ing, json={"kind": "reservoir", "geojson": feature})
    assert r.status_code == 200 and r.json()["has_geometry"] is True
    g = client.get("/reservoirs/TULE/geometry", headers=ing).json()
    assert g["geometry"]["type"] == "MultiPolygon"
    assert client.get("/reservoirs/TULE/geometry?kind=basin", headers=ing).status_code == 404


@pytest.mark.parametrize(
    "geojson",
    [
        {"type": "Point", "coordinates": [-71, 10]},
        {"type": "Polygon", "coordinates": [[[0, 0], [1, 1], [1, 0], [0, 1], [0, 0]]]},  # se cruza a sí mismo
        {
            "type": "Polygon",
            "coordinates": [[[500000, 1100000], [500100, 1100000], [500100, 1100100], [500000, 1100000]]],
        },  # UTM, no WGS84
    ],
)
def test_invalid_geometries_are_rejected(client, auth_headers, reservoirs, geojson):
    ing = auth_headers(Role.INGENIERO, reservoirs=["TULE"])
    r = client.put("/reservoirs/TULE/geometry", headers=ing, json={"kind": "reservoir", "geojson": geojson})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "INVALID_GEOMETRY"


# ---------------------------------------------------------------- HU-1.7 curvas (servicio)


def test_parse_csv_with_semicolon_and_decimal_comma():
    content = "Cota (m.s.n.m.);Área (km²);Volumen (hm³)\n26,5;10;20,5\n27,0;12;31\n".encode()
    pts = parse_curve_file(content, "curva.csv")
    assert pts == [CurvePoint(26.5, 20.5, 10.0), CurvePoint(27.0, 31.0, 12.0)]


def test_parse_xlsx():
    wb = Workbook()
    ws = wb.active
    ws.append(["cota", "volumen"])
    ws.append([30, 76])
    ws.append([26, 20])
    buf = io.BytesIO()
    wb.save(buf)
    pts = parse_curve_file(buf.getvalue(), "curva.xlsx")
    assert [p.elevation for p in pts] == [26, 30]  # se ordena por cota


@pytest.mark.parametrize(
    ("content", "fragment"),
    [
        (b"nivel,otra\n1,2\n", "Faltan columnas"),
        (b"cota,volumen\n26,20\n27,abc\n", "no num"),
        (b"cota,volumen\n26,20\n26,25\n", "repetida"),
        (b"cota,volumen\n26,30\n27,20\n", "disminuye"),
        (b"cota,volumen\n26,20\n", "al menos 2"),
        (b"cota,volumen\n26,-1\n27,5\n", "negativos"),
    ],
)
def test_parse_reports_errors(content, fragment):
    with pytest.raises(CurveFileError) as exc:
        parse_curve_file(content, "curva.csv")
    text = str(exc.value) + " ".join(m for _, m in exc.value.rows)
    assert fragment in text


def test_unsupported_format():
    with pytest.raises(CurveFileError, match="Formato no soportado"):
        parse_curve_file(b"x", "curva.pdf")


def test_linear_interpolation_both_directions():
    interp = CurveInterpolator([CurvePoint(26, 20, 10), CurvePoint(27, 31, 12), CurvePoint(30, 76, 18)])
    assert interp.volume_at(26.5) == pytest.approx(25.5)
    assert interp.area_at(28.5) == pytest.approx(15.0)
    assert interp.elevation_at(53.5) == pytest.approx(28.5)
    assert interp.volume_at(30) == 76
    with pytest.raises(CurveRangeError):
        interp.volume_at(31)


# ---------------------------------------------------------------- HU-1.7 curvas (API)


def _upload(client, h, valid_from, content=CURVE_CSV, name="curva.csv"):
    return client.post(
        "/reservoirs/TULE/curves",
        headers=h,
        files={"file": (name, content, "text/csv")},
        data={"valid_from": valid_from, "notes": "Curva de prueba"},
    )


def test_upload_curve_versions_and_current_by_date(client, auth_headers, reservoirs):
    ing = auth_headers(Role.INGENIERO, reservoirs=["TULE"])
    v1 = _upload(client, ing, "2020-01-01")
    assert v1.status_code == 201, v1.text
    assert v1.json()["version"] == 1 and v1.json()["points"] == 4

    newer = CURVE_CSV.replace(b"34.0,26,166", b"34.0,26,150")
    v2 = _upload(client, ing, "2026-01-01", newer)
    assert v2.json()["version"] == 2

    # La vigente depende de la fecha
    old = client.get("/reservoirs/TULE/curves/interpolate?cota=34&fecha=2025-06-01", headers=ing).json()
    new = client.get("/reservoirs/TULE/curves/interpolate?cota=34&fecha=2026-06-01", headers=ing).json()
    assert (old["curve_version"], old["volume_hm3"]) == (1, 166)
    assert (new["curve_version"], new["volume_hm3"]) == (2, 150)
    assert [c["version"] for c in client.get("/reservoirs/TULE/curves", headers=ing).json()] == [2, 1]


def test_reservoir_card_shows_volumes_from_current_curve(client, auth_headers, reservoirs):
    ing = auth_headers(Role.INGENIERO, reservoirs=["TULE"])
    _upload(client, ing, "2020-01-01")
    card = client.get("/reservoirs/TULE", headers=ing).json()
    assert card["current_curve"]["version"] == 1
    # muerto 26.6 → 20 + 0.6·11 = 26.6 hm³ ; normal 33.4 → 76 + (3.4/4)·90 = 152.5 hm³
    assert card["dead_volume_hm3"] == pytest.approx(26.6)
    assert card["normal_volume_hm3"] == pytest.approx(152.5)
    assert card["useful_capacity_hm3"] == pytest.approx(125.9)


def test_interpolate_volume_to_level_and_errors(client, auth_headers, reservoirs):
    ing = auth_headers(Role.INGENIERO, reservoirs=["TULE"])
    assert (
        client.get("/reservoirs/TULE/curves/interpolate?cota=27", headers=ing).status_code == 404
    )  # sin curva
    _upload(client, ing, "2020-01-01")
    r = client.get("/reservoirs/TULE/curves/interpolate?volumen=31", headers=ing).json()
    assert r["elevation"] == 27.0 and r["area_km2"] == 12.0
    assert client.get("/reservoirs/TULE/curves/interpolate?cota=50", headers=ing).status_code == 422
    assert client.get("/reservoirs/TULE/curves/interpolate", headers=ing).status_code == 422


def test_invalid_curve_upload_returns_row_errors(client, auth_headers, reservoirs):
    ing = auth_headers(Role.INGENIERO, reservoirs=["TULE"])
    r = _upload(client, ing, "2020-01-01", b"cota,volumen\n26,20\n27,abc\n")
    assert r.status_code == 422 and "Fila 3" in r.json()["detail"]["message"]


def test_only_ingeniero_uploads_curves_and_template_is_downloadable(client, auth_headers, reservoirs):
    op = auth_headers(Role.OPERADOR, reservoirs=["TULE"])
    assert _upload(client, op, "2020-01-01").status_code == 403
    t = client.get("/reservoirs/curve-template.csv")  # pública
    assert t.status_code == 200 and t.text.startswith("cota_msnm,area_km2,volumen_hm3")
