"""Tests for /api/auth endpoints."""


def test_register_returns_token(client):
    r = client.post("/api/auth/register", json={
        "email": "new@example.com",
        "password": "Secret123",
    })
    assert r.status_code == 201
    body = r.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


def test_register_duplicate_email_409(client):
    payload = {"email": "dup@example.com", "password": "Secret123"}
    r1 = client.post("/api/auth/register", json=payload)
    assert r1.status_code == 201
    r2 = client.post("/api/auth/register", json=payload)
    assert r2.status_code == 409


def test_register_short_password_422(client):
    r = client.post("/api/auth/register", json={
        "email": "a@b.com",
        "password": "short",  # < 8 chars
    })
    assert r.status_code == 422


def test_login_with_correct_credentials(client, test_user):
    r = client.post("/api/auth/login", json={
        "email": "alice@example.com",
        "password": "Password123",
    })
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_login_wrong_password_401(client, test_user):
    r = client.post("/api/auth/login", json={
        "email": "alice@example.com",
        "password": "WrongPass",
    })
    assert r.status_code == 401


def test_login_unknown_email_401(client):
    r = client.post("/api/auth/login", json={
        "email": "ghost@example.com",
        "password": "anything",
    })
    assert r.status_code == 401


def test_protected_endpoint_without_token_401(client):
    r = client.get("/api/portfolios")
    assert r.status_code == 401


def test_protected_endpoint_with_token_ok(authenticated_client):
    r = authenticated_client.get("/api/portfolios")
    assert r.status_code == 200
    assert r.json() == []  # no portfolios for fresh test user
