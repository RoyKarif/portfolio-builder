def test_register_success(client):
    resp = client.post("/auth/register", json={
        "email": "new@example.com",
        "password": "securepass123",
        "country": "US",
    })
    assert resp.status_code == 201
    assert resp.json()["email"] == "new@example.com"


def test_register_duplicate_email(client):
    payload = {"email": "dup@example.com", "password": "pass123", "country": "US"}
    client.post("/auth/register", json=payload)
    resp = client.post("/auth/register", json=payload)
    assert resp.status_code == 409


def test_login_success(client):
    client.post("/auth/register", json={
        "email": "login@example.com",
        "password": "pass123",
        "country": "US",
    })
    resp = client.post("/auth/login", json={
        "email": "login@example.com",
        "password": "pass123",
    })
    assert resp.status_code == 200
    assert "access_token" in resp.json()
    assert "refresh_token" in resp.json()


def test_login_wrong_password(client):
    client.post("/auth/register", json={
        "email": "wrong@example.com",
        "password": "pass123",
        "country": "US",
    })
    resp = client.post("/auth/login", json={
        "email": "wrong@example.com",
        "password": "wrongpass",
    })
    assert resp.status_code == 401


def test_refresh_token(client):
    client.post("/auth/register", json={
        "email": "refresh@example.com",
        "password": "pass123",
        "country": "US",
    })
    login_resp = client.post("/auth/login", json={
        "email": "refresh@example.com",
        "password": "pass123",
    })
    refresh_token = login_resp.json()["refresh_token"]
    resp = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    assert "access_token" in resp.json()
