"""Integration tests for /api/portfolios."""


def test_build_portfolio_full_flow(authenticated_client, seeded_db):
    """The end-to-end happy path: build → save → list → fetch."""
    r = authenticated_client.post("/api/portfolios/build", json={
        "amount": 10000,
        "risk_level": 3,
        "horizon_years": 5,
        "tickers": ["AAA", "BBB", "CCC"],
    })
    assert r.status_code == 200, r.text
    body = r.json()

    # Weights must be a dict mapping ticker → number, summing to ~1.
    assert isinstance(body["weights"], dict)
    weight_sum = sum(body["weights"].values())
    assert abs(weight_sum - 1.0) < 0.01

    # Sanity-check expected stats are present.
    assert "expected_return" in body
    assert "expected_volatility" in body
    assert "sharpe_ratio" in body

    # MC summary structure.
    assert "mc_summary" in body
    assert all(k in body["mc_summary"] for k in ["p5", "p50", "p95", "var_5", "timeline"])

    pid = body["id"]

    # List endpoint should now show this portfolio.
    r_list = authenticated_client.get("/api/portfolios")
    assert r_list.status_code == 200
    items = r_list.json()
    assert len(items) == 1
    assert items[0]["id"] == pid

    # Detail endpoint returns the full portfolio.
    r_detail = authenticated_client.get(f"/api/portfolios/{pid}")
    assert r_detail.status_code == 200
    assert r_detail.json()["id"] == pid


def test_build_invalid_risk_level_422(authenticated_client, seeded_db):
    r = authenticated_client.post("/api/portfolios/build", json={
        "amount": 10000,
        "risk_level": 99,  # out of [1, 5]
        "horizon_years": 5,
        "tickers": ["AAA", "BBB"],
    })
    assert r.status_code == 422


def test_get_portfolio_of_other_user_404(authenticated_client, seeded_db, db, test_user):
    """Authorization: cannot view another user's portfolio by guessing id."""
    # Build a portfolio as test_user.
    r = authenticated_client.post("/api/portfolios/build", json={
        "amount": 10000, "risk_level": 3, "horizon_years": 5,
        "tickers": ["AAA", "BBB", "CCC"],
    })
    pid = r.json()["id"]

    # Create a second user and authenticate as them.
    from app.auth.password import hash_password
    from app.auth.jwt import create_access_token
    from app.models.user import User
    u2 = User(email="bob@example.com", password_hash=hash_password("Bob12345"))
    db.add(u2); db.commit(); db.refresh(u2)
    token = create_access_token(u2.id)

    r2 = authenticated_client.get(
        f"/api/portfolios/{pid}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 404


def test_universe_endpoint_returns_curated(client, seeded_db):
    r = client.get("/api/universe")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 3  # AAA, BBB, CCC from seeded_db
    tickers = {a["ticker"] for a in body}
    assert tickers == {"AAA", "BBB", "CCC"}
