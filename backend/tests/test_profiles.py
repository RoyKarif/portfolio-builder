PROFILE_PAYLOAD = {
    "risk_level": 3,
    "investment_horizon": "3-5y",
    "available_amount": 50000.00,
    "target_return": 12.0,
    "preferred_sectors": ["Technology", "Healthcare"],
    "include_tickers": ["AAPL"],
    "exclude_tickers": ["META"],
}


def test_create_profile(client, auth_headers):
    resp = client.post("/profiles", json=PROFILE_PAYLOAD, headers=auth_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["risk_level"] == 3
    assert data["available_amount"] == 50000.00


def test_list_profiles(client, auth_headers):
    client.post("/profiles", json=PROFILE_PAYLOAD, headers=auth_headers)
    resp = client.get("/profiles", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_get_profile(client, auth_headers):
    create_resp = client.post("/profiles", json=PROFILE_PAYLOAD, headers=auth_headers)
    profile_id = create_resp.json()["id"]
    resp = client.get(f"/profiles/{profile_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == profile_id


def test_create_profile_unauthorized(client):
    resp = client.post("/profiles", json=PROFILE_PAYLOAD)
    assert resp.status_code == 403
