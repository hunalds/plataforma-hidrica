"""HU-1.4 (bitácora de auditoría) y HU-1.5 (gestión de usuarios y matriz de permisos)."""

from __future__ import annotations

import pytest

from app.core.permissions import Access, Module, access_for, permissions_for
from app.models.user import Role

NEW_USER = {"email": "Operador.Nuevo@hidrica-zulia.com", "full_name": "Pedro Pérez", "role": "OPERADOR"}


# ---------------------------------------------------------------- matriz de permisos


@pytest.mark.parametrize(
    ("role", "module", "expected"),
    [
        (Role.GERENCIA, Module.USERS, Access.MANAGE),
        (Role.GERENCIA, Module.AUDIT, Access.READ),
        (Role.GERENCIA, Module.RESERVOIRS, Access.READ),
        (Role.INGENIERO, Module.RESERVOIRS, Access.MANAGE),
        (Role.INGENIERO, Module.USERS, Access.NONE),
        (Role.OPERADOR, Module.HYDRO_INGEST, Access.MANAGE),
        (Role.OPERADOR, Module.PREDICTION, Access.NONE),
        (Role.OPERADOR, Module.REPORTS, Access.NONE),
        (Role.GERENCIA, Module.REPORTS, Access.MANAGE),
    ],
)
def test_permission_matrix_matches_requirements(role, module, expected):
    assert access_for(role, module) == expected


def test_every_role_sees_dashboard_map_and_help():
    for role in Role:
        perms = permissions_for(role)
        assert {"M7_panel", "M8_mapa", "M11_ayuda"} <= set(perms)


# ---------------------------------------------------------------- HU-1.5 usuarios


def test_gerencia_creates_user_with_temporary_password(client, auth_headers, reservoirs):
    h = auth_headers(Role.GERENCIA)
    r = client.post("/users", headers=h, json={**NEW_USER, "reservoir_codes": ["TULE", "MANUELOTE"]})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["user"]["email"] == "operador.nuevo@hidrica-zulia.com"
    assert body["user"]["must_change_password"] is True
    assert body["user"]["reservoir_codes"] == ["MANUELOTE", "TULE"]
    temp = body["temporary_password"]
    assert len(temp) >= 10

    login = client.post("/auth/login", json={"email": NEW_USER["email"], "password": temp})
    assert login.status_code == 200 and login.json()["user"]["must_change_password"] is True


def test_duplicate_email_and_unknown_reservoir_are_rejected(client, auth_headers, reservoirs):
    h = auth_headers(Role.GERENCIA)
    assert client.post("/users", headers=h, json=NEW_USER).status_code == 201
    assert client.post("/users", headers=h, json=NEW_USER).status_code == 409
    bad = client.post(
        "/users", headers=h, json={**NEW_USER, "email": "otro@hidrica-zulia.com", "reservoir_codes": ["XYZ"]}
    )
    assert bad.status_code == 422 and "XYZ" in bad.json()["detail"]["message"]


@pytest.mark.parametrize("role", [Role.INGENIERO, Role.OPERADOR])
def test_only_gerencia_manages_users(client, auth_headers, role):
    h = auth_headers(role)
    assert client.get("/users", headers=h).status_code == 403
    assert client.post("/users", headers=h, json=NEW_USER).status_code == 403


def test_deactivating_user_closes_sessions_immediately(client, auth_headers, make_user, login):
    admin = auth_headers(Role.GERENCIA)
    target = make_user(Role.OPERADOR, email="op@hidrica-zulia.com")
    tokens = login("op@hidrica-zulia.com")
    target_h = {"Authorization": f"Bearer {tokens['access_token']}"}
    assert client.get("/auth/me", headers=target_h).status_code == 200

    r = client.patch(f"/users/{target.id}", headers=admin, json={"is_active": False})
    assert r.status_code == 200 and r.json()["is_active"] is False
    assert client.get("/auth/me", headers=target_h).status_code == 401
    assert client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code == 401


def test_cannot_demote_or_deactivate_self(client, make_user, login):
    me = make_user(Role.GERENCIA, email="jefe@hidrica-zulia.com")
    h = {"Authorization": f"Bearer {login('jefe@hidrica-zulia.com')['access_token']}"}
    assert client.patch(f"/users/{me.id}", headers=h, json={"is_active": False}).status_code == 409
    assert client.patch(f"/users/{me.id}", headers=h, json={"role": "OPERADOR"}).status_code == 409
    assert (
        client.patch(f"/users/{me.id}", headers=h, json={"full_name": "Jefe Renombrado"}).status_code == 200
    )


def test_admin_reset_password_unlocks_and_forces_change(client, auth_headers, make_user):
    admin = auth_headers(Role.GERENCIA)
    target = make_user(Role.INGENIERO, email="ing@hidrica-zulia.com")
    for i in range(5):
        client.post("/auth/login", json={"email": "ing@hidrica-zulia.com", "password": f"mala-{i}-abc1"})
    r = client.post(f"/users/{target.id}/reset-password", headers=admin)
    assert r.status_code == 200
    login = client.post(
        "/auth/login", json={"email": "ing@hidrica-zulia.com", "password": r.json()["temporary_password"]}
    )
    assert login.status_code == 200 and login.json()["user"]["must_change_password"] is True


def test_list_users_filters(client, auth_headers, make_user):
    h = auth_headers(Role.GERENCIA)
    make_user(Role.OPERADOR, email="op1@hidrica-zulia.com")
    make_user(Role.OPERADOR, email="op2@hidrica-zulia.com", is_active=False)
    make_user(Role.INGENIERO, email="ing@hidrica-zulia.com")
    assert client.get("/users", headers=h).json()["total"] == 4
    assert client.get("/users?role=OPERADOR", headers=h).json()["total"] == 2
    assert client.get("/users?role=OPERADOR&active=true", headers=h).json()["total"] == 1
    assert client.get("/users?search=ing@", headers=h).json()["total"] == 1


# ---------------------------------------------------------------- HU-1.4 auditoría


def test_user_changes_are_audited_with_old_and_new_values(client, auth_headers, make_user, reservoirs):
    h = auth_headers(Role.GERENCIA)
    target = make_user(Role.OPERADOR, email="op@hidrica-zulia.com")
    client.patch(f"/users/{target.id}", headers=h, json={"role": "INGENIERO", "reservoir_codes": ["TULE"]})

    r = client.get("/audit?action=user.update", headers=h)
    assert r.status_code == 200
    entry = r.json()["items"][0]
    assert entry["user_email"] == "gerencia@hidrica-zulia.com"
    assert entry["entity"] == "user" and entry["entity_id"] == str(target.id)
    assert entry["old_value"] == {"role": "OPERADOR", "reservoir_codes": []}
    assert entry["new_value"] == {"role": "INGENIERO", "reservoir_codes": ["TULE"]}
    assert entry["ip"] is not None and entry["created_at"]


def test_audit_records_logins_and_is_gerencia_only(client, auth_headers):
    h = auth_headers(Role.GERENCIA)
    client.post("/auth/login", json={"email": "gerencia@hidrica-zulia.com", "password": "incorrecta-1"})
    actions = [e["action"] for e in client.get("/audit?action=login", headers=h).json()["items"]]
    assert "login.ok" in actions and "login.fail" in actions

    for role in (Role.INGENIERO, Role.OPERADOR):
        other = auth_headers(role)
        assert client.get("/audit", headers=other).status_code == 403


def test_audit_pagination_and_date_filter(client, auth_headers):
    h = auth_headers(Role.GERENCIA)
    for _ in range(3):
        client.post("/auth/login", json={"email": "nadie@hidrica-zulia.com", "password": "x"})
    page = client.get("/audit?limit=2&offset=0", headers=h).json()
    assert len(page["items"]) == 2 and page["total"] >= 4
    assert client.get("/audit?date_from=2000-01-01&date_to=2000-01-02", headers=h).json()["total"] == 0
