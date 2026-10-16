from sqlalchemy import select

from app.models import AuthSession
from tests.conftest import sign_in


def test_csrf_login_logout(client, scenario, db):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "tenant-a@example.com", "password": "testing-password-2026"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "CSRF"
    headers = sign_in(client)
    assert client.get("/api/v1/auth/me").json()["role"] == "TENANT"
    session = db.scalar(select(AuthSession))
    assert session.token_hash != client.cookies.get("intakeflow_session")
    assert "HttpOnly" in next(c for c in client.cookies.jar if c.name == "intakeflow_session")._rest
    assert (
        client.post(
            "/api/v1/auth/logout", headers={**headers, "Origin": "https://evil.example"}
        ).status_code
        == 403
    )
    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 401


def test_tenant_cannot_admin(client, scenario):
    headers = sign_in(client)
    assert client.get("/api/v1/ai-usage").status_code == 403
    assert (
        client.post(
            "/api/v1/properties", json={"name": "Test", "address": "Test address"}, headers=headers
        ).status_code
        == 403
    )
    assert client.get("/api/v1/units").json()["total"] == 1


def test_rate_limit(client, scenario):
    csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    statuses = [
        client.post(
            "/api/v1/auth/login",
            json={"email": "tenant-a@example.com", "password": "wrong-password"},
            headers={"X-CSRF-Token": csrf},
        ).status_code
        for _ in range(11)
    ]
    assert statuses[:10] == [401] * 10
    assert statuses[10] == 429


def test_register(client):
    csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    response = client.post(
        "/api/v1/auth/register",
        json={
            "organization_name": "Fresh Org",
            "name": "Admin User",
            "email": "new@example.com",
            "password": "new-password-2026",
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 201, response.text
    me = client.get("/api/v1/auth/me").json()
    assert me["role"] == "ADMIN"
    assert me["organization"]["timezone"] == "Asia/Karachi"
