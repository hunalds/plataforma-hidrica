"""Pruebas de autenticación.

HU-1.1 login, logout y refresh · HU-1.2 bloqueo y límite de intentos · HU-1.3 primer acceso y recuperación.
"""

from __future__ import annotations

from datetime import timedelta

import jwt
from sqlalchemy import select, update

from app.core.security import utcnow
from app.models.audit import AuditLog
from app.models.user import RefreshToken, Role
from tests.conftest import PASSWORD

# ---------------------------------------------------------------- HU-1.1


def test_login_ok_returns_tokens_user_and_permissions(client, make_user):
    make_user(Role.INGENIERO, email="ana@hidrica-zulia.com")
    r = client.post("/auth/login", json={"email": "ANA@hidrica-zulia.com", "password": PASSWORD})
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer" and body["expires_in"] == 15 * 60
    assert body["user"]["email"] == "ana@hidrica-zulia.com"
    assert body["user"]["permissions"]["M3_embalses"] == "MANAGE"
    assert "M2_usuarios" not in body["user"]["permissions"]


def test_login_wrong_password_and_unknown_email_give_same_generic_error(client, make_user):
    make_user(email="ana@hidrica-zulia.com")
    wrong = client.post("/auth/login", json={"email": "ana@hidrica-zulia.com", "password": "otra-cosa-123"})
    unknown = client.post(
        "/auth/login", json={"email": "nadie@hidrica-zulia.com", "password": "otra-cosa-123"}
    )
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["detail"] == unknown.json()["detail"]
    assert wrong.json()["detail"]["message"] == "Correo o contraseña incorrectos."


def test_inactive_user_cannot_login(client, make_user):
    make_user(email="ana@hidrica-zulia.com", is_active=False)
    r = client.post("/auth/login", json={"email": "ana@hidrica-zulia.com", "password": PASSWORD})
    assert r.status_code == 403 and r.json()["detail"]["code"] == "USER_INACTIVE"


def test_me_requires_valid_token(client, make_user, login):
    make_user(email="ana@hidrica-zulia.com")
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers={"Authorization": "Bearer basura"}).status_code == 401
    tokens = login("ana@hidrica-zulia.com")
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert r.status_code == 200 and r.json()["email"] == "ana@hidrica-zulia.com"


def test_expired_access_token_is_rejected(client, make_user, settings):
    user = make_user()
    past = utcnow() - timedelta(minutes=1)
    token = jwt.encode(
        {"sub": str(user.id), "ver": 0, "type": "access", "role": "GERENCIA", "exp": past},
        settings.jwt_secret.get_secret_value(),
        algorithm="HS256",
    )
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_refresh_token_cannot_be_used_as_access_token(client, make_user, login):
    make_user(email="ana@hidrica-zulia.com")
    tokens = login("ana@hidrica-zulia.com")
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {tokens['refresh_token']}"})
    assert r.status_code == 401


def test_refresh_rotates_and_detects_reuse(client, make_user, login):
    make_user(email="ana@hidrica-zulia.com")
    first = login("ana@hidrica-zulia.com")
    r = client.post("/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert r.status_code == 200
    second = r.json()
    assert second["refresh_token"] != first["refresh_token"]

    # Reusar el token ya rotado cierra TODAS las sesiones (incluida la nueva)
    assert client.post("/auth/refresh", json={"refresh_token": first["refresh_token"]}).status_code == 401
    assert client.post("/auth/refresh", json={"refresh_token": second["refresh_token"]}).status_code == 401


def test_session_expires_after_inactivity(client, db, make_user, login, settings):
    make_user(email="ana@hidrica-zulia.com")
    tokens = login("ana@hidrica-zulia.com")
    db.execute(
        update(RefreshToken).values(
            last_used_at=utcnow() - timedelta(minutes=settings.session_idle_minutes + 1)
        )
    )
    db.commit()
    r = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 401 and r.json()["detail"]["code"] == "SESSION_IDLE"


def test_logout_revokes_refresh_token(client, make_user, login):
    make_user(email="ana@hidrica-zulia.com")
    tokens = login("ana@hidrica-zulia.com")
    assert client.post("/auth/logout", json={"refresh_token": tokens["refresh_token"]}).status_code == 200
    assert client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code == 401


# ---------------------------------------------------------------- HU-1.2


def test_account_locks_after_five_failed_attempts(client, db, make_user):
    make_user(email="ana@hidrica-zulia.com")
    codes = [
        client.post(
            "/auth/login", json={"email": "ana@hidrica-zulia.com", "password": f"mala-{i}-xyz1"}
        ).status_code
        for i in range(5)
    ]
    assert codes == [401, 401, 401, 401, 423]
    # Bloqueada: ni siquiera la contraseña correcta entra
    r = client.post("/auth/login", json={"email": "ana@hidrica-zulia.com", "password": PASSWORD})
    assert r.status_code == 423 and r.json()["detail"]["code"] == "ACCOUNT_LOCKED"
    actions = db.scalars(select(AuditLog.action)).all()
    assert actions.count("login.fail") == 4 and "login.lockout" in actions and "login.locked" in actions


def test_successful_login_resets_failed_attempts(client, make_user):
    make_user(email="ana@hidrica-zulia.com")
    for _ in range(4):
        client.post("/auth/login", json={"email": "ana@hidrica-zulia.com", "password": "mala-clave-1"})
    assert (
        client.post("/auth/login", json={"email": "ana@hidrica-zulia.com", "password": PASSWORD}).status_code
        == 200
    )
    # El contador volvió a cero: 4 fallos más no bloquean
    codes = [
        client.post(
            "/auth/login", json={"email": "ana@hidrica-zulia.com", "password": "mala-clave-1"}
        ).status_code
        for _ in range(4)
    ]
    assert 423 not in codes


def test_lock_expires(client, db, make_user):
    user = make_user(email="ana@hidrica-zulia.com")
    user.locked_until = utcnow() - timedelta(seconds=1)
    db.commit()
    assert (
        client.post("/auth/login", json={"email": "ana@hidrica-zulia.com", "password": PASSWORD}).status_code
        == 200
    )


def test_rate_limit_per_ip(client, settings):
    codes = [
        client.post("/auth/login", json={"email": f"x{i}@hidrica-zulia.com", "password": "abc"}).status_code
        for i in range(settings.login_rate_limit_per_minute + 1)
    ]
    assert (
        codes[-1] == 429
        and "Retry-After"
        in client.post("/auth/login", json={"email": "y@hidrica-zulia.com", "password": "a"}).headers
    )


# ---------------------------------------------------------------- HU-1.3


def test_first_login_forces_password_change(client, make_user, auth_headers):
    make_user(Role.INGENIERO, email="nuevo@hidrica-zulia.com", must_change_password=True)
    r = client.post("/auth/login", json={"email": "nuevo@hidrica-zulia.com", "password": PASSWORD})
    assert r.json()["user"]["must_change_password"] is True
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

    # Puede ver /auth/me, pero no otros recursos
    assert client.get("/auth/me", headers=headers).status_code == 200
    blocked = client.get("/reservoirs", headers=headers)
    assert blocked.status_code == 403 and blocked.json()["detail"]["code"] == "PASSWORD_CHANGE_REQUIRED"

    r = client.post(
        "/auth/change-password",
        headers=headers,
        json={"current_password": PASSWORD, "new_password": "Nueva-Clave-2027"},
    )
    assert r.status_code == 200
    new_headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert r.json()["user"]["must_change_password"] is False
    # El token anterior queda invalidado; el nuevo funciona
    assert client.get("/auth/me", headers=headers).status_code == 401
    assert client.get("/reservoirs", headers=new_headers).status_code == 200


def test_change_password_validates_current_and_policy(client, make_user, login):
    make_user(email="ana@hidrica-zulia.com")
    h = {"Authorization": f"Bearer {login('ana@hidrica-zulia.com')['access_token']}"}
    wrong = client.post(
        "/auth/change-password", headers=h, json={"current_password": "x", "new_password": "Otra-Clave-99"}
    )
    assert wrong.status_code == 400
    weak = client.post(
        "/auth/change-password", headers=h, json={"current_password": PASSWORD, "new_password": "corta"}
    )
    assert weak.status_code == 422 and "10 caracteres" in weak.json()["detail"]["message"]
    same = client.post(
        "/auth/change-password", headers=h, json={"current_password": PASSWORD, "new_password": PASSWORD}
    )
    assert same.status_code == 422


def _reset_token_from_email(app) -> str:
    body = app.state.email_sender.outbox[-1].body
    return body.split("token=")[1].split()[0]


def test_password_recovery_flow_single_use(client, app, make_user):
    make_user(email="ana@hidrica-zulia.com")
    r = client.post("/auth/forgot-password", json={"email": "ana@hidrica-zulia.com"})
    assert r.status_code == 202
    assert len(app.state.email_sender.outbox) == 1
    token = _reset_token_from_email(app)

    ok = client.post("/auth/reset-password", json={"token": token, "new_password": "Recuperada-2026"})
    assert ok.status_code == 200
    assert (
        client.post(
            "/auth/login", json={"email": "ana@hidrica-zulia.com", "password": "Recuperada-2026"}
        ).status_code
        == 200
    )
    # Un solo uso
    again = client.post("/auth/reset-password", json={"token": token, "new_password": "Otra-Vez-2026"})
    assert again.status_code == 400


def test_forgot_password_does_not_reveal_unknown_emails(client, app):
    r = client.post("/auth/forgot-password", json={"email": "nadie@hidrica-zulia.com"})
    assert r.status_code == 202
    assert app.state.email_sender.outbox == []


def test_reset_token_expires(client, app, db, make_user):
    from app.models.user import PasswordResetToken

    make_user(email="ana@hidrica-zulia.com")
    client.post("/auth/forgot-password", json={"email": "ana@hidrica-zulia.com"})
    token = _reset_token_from_email(app)
    db.execute(update(PasswordResetToken).values(expires_at=utcnow() - timedelta(seconds=1)))
    db.commit()
    r = client.post("/auth/reset-password", json={"token": token, "new_password": "Recuperada-2026"})
    assert r.status_code == 400 and r.json()["detail"]["code"] == "INVALID_RESET_TOKEN"


def test_reset_password_unlocks_account(client, app, make_user):
    make_user(email="ana@hidrica-zulia.com")
    for i in range(5):
        client.post("/auth/login", json={"email": "ana@hidrica-zulia.com", "password": f"mala-{i}-xyz1"})
    client.post("/auth/forgot-password", json={"email": "ana@hidrica-zulia.com"})
    client.post(
        "/auth/reset-password",
        json={"token": _reset_token_from_email(app), "new_password": "Recuperada-2026"},
    )
    assert (
        client.post(
            "/auth/login", json={"email": "ana@hidrica-zulia.com", "password": "Recuperada-2026"}
        ).status_code
        == 200
    )


def test_audit_never_stores_passwords(client, db, make_user, login):
    make_user(email="ana@hidrica-zulia.com")
    h = {"Authorization": f"Bearer {login('ana@hidrica-zulia.com')['access_token']}"}
    client.post(
        "/auth/change-password",
        headers=h,
        json={"current_password": PASSWORD, "new_password": "Nueva-Clave-2027"},
    )
    rows = db.scalars(select(AuditLog)).all()
    dumped = str([(r.old_value, r.new_value) for r in rows])
    assert PASSWORD not in dumped and "Nueva-Clave-2027" not in dumped
