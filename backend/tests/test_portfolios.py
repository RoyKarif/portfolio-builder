from unittest.mock import patch

PROFILE_PAYLOAD = {
    "risk_level": 3,
    "investment_horizon": "3-5y",
    "available_amount": 50000.00,
    "target_return": 10.0,
    "preferred_sectors": ["Technology"],
    "include_tickers": [],
    "exclude_tickers": [],
}

MOCK_ENGINE_RESULT = {
    "holdings": [
        {"ticker": "AAPL", "company_name": "Apple", "sector": "Technology", "allocation_pct": 30.0, "expected_return": 12.0},
        {"ticker": "MSFT", "company_name": "Microsoft", "sector": "Technology", "allocation_pct": 25.0, "expected_return": 10.5},
        {"ticker": "GOOGL", "company_name": "Alphabet", "sector": "Technology", "allocation_pct": 20.0, "expected_return": 11.0},
        {"ticker": "NVDA", "company_name": "NVIDIA", "sector": "Technology", "allocation_pct": 15.0, "expected_return": 15.0},
        {"ticker": "AMZN", "company_name": "Amazon", "sector": "Technology", "allocation_pct": 10.0, "expected_return": 9.5},
    ],
    "risk_score": 18.5,
    "expected_return_low": 5.2,
    "expected_return_high": 16.8,
    "portfolio_return": 11.5,
    "simulation": {"percentile_10": 42000, "percentile_50": 58000, "percentile_90": 78000, "return_low": 0.052, "return_high": 0.168, "initial_value": 50000, "horizon_years": 4.0, "n_simulations": 10000},
    "status": "optimal",
    "covariance_method": "ledoit_wolf",
    "shrinkage_intensity": 0.1823,
}


@patch("app.api.portfolios.generate_portfolio", return_value=MOCK_ENGINE_RESULT)
def test_generate_portfolio(mock_engine, client, auth_headers):
    profile_resp = client.post("/profiles", json=PROFILE_PAYLOAD, headers=auth_headers)
    profile_id = profile_resp.json()["id"]
    resp = client.post(f"/portfolios/generate/{profile_id}", headers=auth_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert len(data["holdings"]) == 5
    assert data["risk_score"] == 18.5
    assert data["covariance_method"] == "ledoit_wolf"
    assert 0.0 <= data["shrinkage_intensity"] <= 1.0


@patch("app.api.portfolios.generate_portfolio", return_value=MOCK_ENGINE_RESULT)
def test_list_portfolios(mock_engine, client, auth_headers):
    profile_resp = client.post("/profiles", json=PROFILE_PAYLOAD, headers=auth_headers)
    profile_id = profile_resp.json()["id"]
    client.post(f"/portfolios/generate/{profile_id}", headers=auth_headers)
    resp = client.get("/portfolios", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@patch("app.api.portfolios.generate_portfolio", return_value=MOCK_ENGINE_RESULT)
def test_archive_portfolio(mock_engine, client, auth_headers):
    profile_resp = client.post("/profiles", json=PROFILE_PAYLOAD, headers=auth_headers)
    profile_id = profile_resp.json()["id"]
    gen_resp = client.post(f"/portfolios/generate/{profile_id}", headers=auth_headers)
    portfolio_id = gen_resp.json()["id"]
    resp = client.patch(f"/portfolios/{portfolio_id}/archive", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "archived"


@patch("app.api.portfolios.generate_portfolio", return_value=MOCK_ENGINE_RESULT)
def test_delete_portfolio(mock_engine, client, auth_headers):
    profile_resp = client.post("/profiles", json=PROFILE_PAYLOAD, headers=auth_headers)
    profile_id = profile_resp.json()["id"]
    gen_resp = client.post(f"/portfolios/generate/{profile_id}", headers=auth_headers)
    portfolio_id = gen_resp.json()["id"]

    del_resp = client.delete(f"/portfolios/{portfolio_id}", headers=auth_headers)
    assert del_resp.status_code == 204

    get_resp = client.get(f"/portfolios/{portfolio_id}", headers=auth_headers)
    assert get_resp.status_code == 404


def test_delete_portfolio_not_found(client, auth_headers):
    resp = client.delete("/portfolios/00000000-0000-0000-0000-000000000000", headers=auth_headers)
    assert resp.status_code == 404


@patch("app.api.portfolios.generate_portfolio", return_value=MOCK_ENGINE_RESULT)
def test_delete_portfolio_requires_auth(mock_engine, client, auth_headers):
    profile_resp = client.post("/profiles", json=PROFILE_PAYLOAD, headers=auth_headers)
    profile_id = profile_resp.json()["id"]
    gen_resp = client.post(f"/portfolios/generate/{profile_id}", headers=auth_headers)
    portfolio_id = gen_resp.json()["id"]

    resp = client.delete(f"/portfolios/{portfolio_id}")
    assert resp.status_code in (401, 403)
