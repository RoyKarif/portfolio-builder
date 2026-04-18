from unittest.mock import patch

import numpy as np
import pandas as pd

from app.engine.pipeline import generate_portfolio


def _fake_yf_download(tickers, start, end, **kwargs):
    """Build a deterministic synthetic OHLCV panel matching yfinance's
    multi-ticker output shape (MultiIndex columns: (ticker, field))."""
    rng = np.random.default_rng(seed=7)
    n_days = 520
    dates = pd.bdate_range(end=end, periods=n_days)
    frames = []
    for t in tickers:
        base = 100.0
        returns = rng.normal(0.0003, 0.015, n_days)
        prices = base * np.cumprod(1 + returns)
        df = pd.DataFrame(
            {"Close": prices, "Volume": np.full(n_days, 1_000_000.0)},
            index=dates,
        )
        frames.append(df)
    result = pd.concat(frames, axis=1, keys=tickers)
    return result


def _fake_universe(country, sectors, include_tickers, exclude_tickers, risk_level):
    return [
        {"ticker": f"T{i}", "company_name": f"Co{i}", "sector": "Technology",
         "exchange": "", "is_defensive": False}
        for i in range(10)
    ]


@patch("app.engine.pipeline.select_universe", side_effect=_fake_universe)
@patch("app.engine.pipeline.yf.download", side_effect=_fake_yf_download)
def test_pipeline_end_to_end_includes_covariance_metadata(mock_dl, mock_uni):
    result = generate_portfolio(
        country="US",
        risk_level=3,
        investment_horizon="3-5y",
        available_amount=10_000.0,
        target_return=10.0,
        preferred_sectors=["Technology"],
        include_tickers=[],
        exclude_tickers=[],
        db=None,
    )

    assert "error" not in result, f"pipeline returned error: {result.get('error')}"
    assert result["covariance_method"] == "ledoit_wolf"
    assert 0.0 <= result["shrinkage_intensity"] <= 1.0

    total_alloc = sum(h["allocation_pct"] for h in result["holdings"])
    assert abs(total_alloc - 100.0) < 0.5, f"allocations sum to {total_alloc}"
    assert all(h["allocation_pct"] >= 0 for h in result["holdings"])
    # MAX_SINGLE_WEIGHT in optimizer.py is 0.20 → 20% as a pct
    assert all(h["allocation_pct"] <= 20.01 for h in result["holdings"])


@patch("app.engine.pipeline.select_universe", side_effect=_fake_universe)
@patch("app.engine.pipeline.yf.download", side_effect=_fake_yf_download)
def test_pipeline_is_reproducible(mock_dl, mock_uni):
    a = generate_portfolio(
        country="US", risk_level=3, investment_horizon="3-5y",
        available_amount=10_000.0, target_return=10.0,
        preferred_sectors=["Technology"], include_tickers=[], exclude_tickers=[],
        db=None,
    )

    # Same mocks for both calls — _fake_yf_download builds its panel with
    # a fresh seeded RNG each invocation, so the second call sees identical
    # price data. With a deterministic simulator seed, the two engine
    # results must match within float tolerance.
    b = generate_portfolio(
        country="US", risk_level=3, investment_horizon="3-5y",
        available_amount=10_000.0, target_return=10.0,
        preferred_sectors=["Technology"], include_tickers=[], exclude_tickers=[],
        db=None,
    )

    assert "error" not in a
    assert "error" not in b

    # Tickers and ordering must match exactly.
    assert [h["ticker"] for h in a["holdings"]] == [h["ticker"] for h in b["holdings"]]

    # Numeric fields must match within float tolerance.
    tol = 1e-9
    assert abs(a["risk_score"] - b["risk_score"]) < tol
    assert abs(a["simulation"]["percentile_10"] - b["simulation"]["percentile_10"]) < tol
    assert abs(a["simulation"]["percentile_50"] - b["simulation"]["percentile_50"]) < tol
    assert abs(a["simulation"]["percentile_90"] - b["simulation"]["percentile_90"]) < tol
    for ha, hb in zip(a["holdings"], b["holdings"]):
        assert abs(ha["allocation_pct"] - hb["allocation_pct"]) < tol


@patch("app.engine.pipeline.select_universe", side_effect=_fake_universe)
@patch("app.engine.pipeline.yf.download", side_effect=_fake_yf_download)
def test_pipeline_changes_with_inputs(mock_dl, mock_uni):
    small = generate_portfolio(
        country="US", risk_level=3, investment_horizon="3-5y",
        available_amount=10_000.0, target_return=10.0,
        preferred_sectors=["Technology"], include_tickers=[], exclude_tickers=[],
        db=None,
    )
    large = generate_portfolio(
        country="US", risk_level=3, investment_horizon="3-5y",
        available_amount=20_000.0, target_return=10.0,
        preferred_sectors=["Technology"], include_tickers=[], exclude_tickers=[],
        db=None,
    )

    # Doubling the initial value should roughly double the percentile_50.
    assert abs(small["simulation"]["percentile_50"] - large["simulation"]["percentile_50"]) > 1e-6


def _fake_yf_download_with_low_volume_tickers(tickers, start, end, **kwargs):
    """Like _fake_yf_download but the first ticker has Volume = 1.0
    (ADV << $10M), so the quality screen must drop it."""
    rng = np.random.default_rng(seed=7)
    n_days = 520
    dates = pd.bdate_range(end=end, periods=n_days)
    frames = []
    for i, t in enumerate(tickers):
        returns = rng.normal(0.0003, 0.015, n_days)
        prices = 100.0 * np.cumprod(1 + returns)
        volume = 1.0 if i == 0 else 1_000_000.0
        df = pd.DataFrame(
            {"Close": prices, "Volume": np.full(n_days, volume)},
            index=dates,
        )
        frames.append(df)
    return pd.concat(frames, axis=1, keys=tickers)


@patch("app.engine.pipeline.select_universe", side_effect=_fake_universe)
@patch("app.engine.pipeline.yf.download", side_effect=_fake_yf_download_with_low_volume_tickers)
def test_pipeline_drops_low_volume_ticker_from_holdings(mock_dl, mock_uni):
    result = generate_portfolio(
        country="US", risk_level=3, investment_horizon="3-5y",
        available_amount=10_000.0, target_return=10.0,
        preferred_sectors=["Technology"], include_tickers=[], exclude_tickers=[],
        db=None,
    )

    assert "error" not in result, f"pipeline returned error: {result.get('error')}"

    # T0 is the low-volume ticker (Volume = 1.0 → ADV ≈ $100, far below $10M).
    # The quality screen must drop it; it MUST NOT appear in the final holdings.
    tickers_in_result = {h["ticker"] for h in result["holdings"]}
    assert "T0" not in tickers_in_result
    # The pipeline still produces a valid 5+ holding portfolio from T1..T9.
    assert len(result["holdings"]) >= 5


@patch("app.engine.pipeline.select_universe", side_effect=_fake_universe)
@patch("app.engine.pipeline.yf.download", side_effect=_fake_yf_download)
def test_pipeline_hrp_wins_on_synthetic_data(mock_dl, mock_uni):
    # risk_level changed from 3 -> 1 to keep this test on the HRP-win path
    # after P5's symmetric routing rule. The synthetic universe produces
    # ~7% HRP candidate vol; only risk_level=1 (cap 8%) puts that inside
    # the [LOWER × cap, UPPER × cap] HRP-wins band. At risk_level >= 2
    # the new rule (correctly) routes to mvo_underutilized.
    from app.engine.optimizer import RISK_VOLATILITY_CAP
    from app.engine.pipeline import HRP_UPPER_TOLERANCE

    result = generate_portfolio(
        country="US", risk_level=1, investment_horizon="3-5y",
        available_amount=10_000.0, target_return=10.0,
        preferred_sectors=["Technology"], include_tickers=[], exclude_tickers=[],
        db=None,
    )

    assert "error" not in result, f"pipeline returned error: {result.get('error')}"
    assert result["weighting_method"] == "hrp"
    assert result["optimizer_status"] is None
    assert result["hrp_candidate_vol"] is not None

    target_vol = RISK_VOLATILITY_CAP[1]
    assert 0 < result["hrp_candidate_vol"] <= target_vol * HRP_UPPER_TOLERANCE

    # When HRP wins, hrp_candidate_vol equals risk_score / 100 within rounding
    # tolerance. risk_score is rounded to 2 decimals in pipeline.py
    # (see "round(portfolio_vol * 100, 2)"), so the max delta is 5e-5.
    assert abs(result["hrp_candidate_vol"] - result["risk_score"] / 100) < 1e-4


def _fake_yf_download_high_vol(tickers, start, end, **kwargs):
    """Synthetic prices with very high cross-correlation AND high vol so
    HRP cannot diversify away enough variance — the candidate vol overshoots
    the risk_level=1 cap (8% annualized) by more than HRP_VOL_TOLERANCE."""
    rng = np.random.default_rng(seed=11)
    n_days = 520
    dates = pd.bdate_range(end=end, periods=n_days)
    # One shared driver + tiny idiosyncratic noise => near-perfect correlation
    common = rng.normal(0.0003, 0.05, n_days)  # ~5% daily vol => ~80% annualized
    frames = []
    for t in tickers:
        idio = rng.normal(0.0, 0.001, n_days)
        returns = common + idio
        prices = 100.0 * np.cumprod(1 + returns)
        df = pd.DataFrame(
            {"Close": prices, "Volume": np.full(n_days, 1_000_000.0)},
            index=dates,
        )
        frames.append(df)
    return pd.concat(frames, axis=1, keys=tickers)


@patch("app.engine.pipeline.select_universe", side_effect=_fake_universe)
@patch("app.engine.pipeline.yf.download", side_effect=_fake_yf_download_high_vol)
def test_pipeline_mvo_fallback_on_risk_cap_overshoot(mock_dl, mock_uni):
    from app.engine.optimizer import RISK_VOLATILITY_CAP
    from app.engine.pipeline import HRP_UPPER_TOLERANCE

    result = generate_portfolio(
        country="US", risk_level=1, investment_horizon="3-5y",
        available_amount=10_000.0, target_return=10.0,
        preferred_sectors=["Technology"], include_tickers=[], exclude_tickers=[],
        db=None,
    )

    assert "error" not in result, f"pipeline returned error: {result.get('error')}"
    assert result["weighting_method"] in ("mvo_risk_cap", "fallback_equal_weight")
    assert result["optimizer_status"] in ("optimal", "fallback_equal_weight")
    assert result["hrp_candidate_vol"] is not None
    assert result["hrp_candidate_vol"] > RISK_VOLATILITY_CAP[1] * HRP_UPPER_TOLERANCE


@patch("app.engine.pipeline.hrp_weights", side_effect=ValueError("forced for test"))
@patch("app.engine.pipeline.select_universe", side_effect=_fake_universe)
@patch("app.engine.pipeline.yf.download", side_effect=_fake_yf_download)
def test_pipeline_hrp_error_fallback_to_mvo_optimal(mock_dl, mock_uni, mock_hrp):
    result = generate_portfolio(
        country="US", risk_level=3, investment_horizon="3-5y",
        available_amount=10_000.0, target_return=10.0,
        preferred_sectors=["Technology"], include_tickers=[], exclude_tickers=[],
        db=None,
    )

    assert "error" not in result, f"pipeline returned error: {result.get('error')}"
    assert result["weighting_method"] == "mvo_fallback_hrp_error"
    assert result["optimizer_status"] == "optimal"
    assert result["hrp_candidate_vol"] is None


def _fake_optimize_equal_weight_fallback(tickers, expected_returns, cov_matrix, risk_level):
    """Mock optimizer that always returns the equal-weight fallback path."""
    n = len(tickers)
    equal_w = np.ones(n) / n
    return {
        "weights": {t: round(float(w), 4) for t, w in zip(tickers, equal_w)},
        "portfolio_return": float(expected_returns @ equal_w),
        "portfolio_volatility": float(np.sqrt(equal_w @ cov_matrix @ equal_w)),
        "status": "fallback_equal_weight",
    }


@patch("app.engine.pipeline.optimize_portfolio", side_effect=_fake_optimize_equal_weight_fallback)
@patch("app.engine.pipeline.hrp_weights", side_effect=ValueError("forced for test"))
@patch("app.engine.pipeline.select_universe", side_effect=_fake_universe)
@patch("app.engine.pipeline.yf.download", side_effect=_fake_yf_download)
def test_pipeline_hrp_error_fallback_to_mvo_equal_weight(mock_dl, mock_uni, mock_hrp, mock_opt):
    result = generate_portfolio(
        country="US", risk_level=3, investment_horizon="3-5y",
        available_amount=10_000.0, target_return=10.0,
        preferred_sectors=["Technology"], include_tickers=[], exclude_tickers=[],
        db=None,
    )

    assert "error" not in result, f"pipeline returned error: {result.get('error')}"
    # When MVO falls back to equal-weight, weighting_method collapses to
    # the equal-weight string regardless of why we entered MVO.
    assert result["weighting_method"] == "fallback_equal_weight"
    assert result["optimizer_status"] == "fallback_equal_weight"
    assert result["hrp_candidate_vol"] is None  # HRP raised before producing weights


def _fake_universe_30(country, sectors, include_tickers, exclude_tickers, risk_level):
    return [
        {"ticker": f"T{i:02d}", "company_name": f"Co{i}", "sector": "Technology",
         "exchange": "", "is_defensive": False}
        for i in range(30)
    ]


@patch("app.engine.pipeline.select_universe", side_effect=_fake_universe_30)
@patch("app.engine.pipeline.yf.download", side_effect=_fake_yf_download_high_vol)
def test_pipeline_mvo_fallback_weights_sum_to_one_with_large_universe(mock_dl, mock_uni):
    """Regression: optimize_portfolio rounds weights to 4 decimals before
    returning, so naively pulling them into weights_array can produce a sum
    that drifts by up to n × 5e-5. With a small (10-ticker) universe and
    equal weights, rounding happens to be exact, so earlier tests didn't
    catch it. This test forces the cap-overshoot path at n=30, which is
    where the assertion `< 1e-8` would have fired before the renormalize fix."""
    result = generate_portfolio(
        country="US", risk_level=1, investment_horizon="3-5y",
        available_amount=10_000.0, target_return=10.0,
        preferred_sectors=["Technology"], include_tickers=[], exclude_tickers=[],
        db=None,
    )

    assert "error" not in result, f"pipeline returned error: {result.get('error')}"
    # Most important: the pipeline didn't blow up on the strict sum assertion.
    # If we got here, weights_array.sum() was within 1e-8 of 1.0.
    assert result["weighting_method"] in (
        "mvo_risk_cap",
        "fallback_equal_weight",
    ), f"unexpected weighting_method: {result['weighting_method']}"

    # Holdings allocations come from the renormalized weights, so the
    # displayed allocation_pcts should sum to ~100 (allowing for the
    # round-to-2-decimals display rounding and the <1% display filter).
    total_alloc = sum(h["allocation_pct"] for h in result["holdings"])
    assert abs(total_alloc - 100.0) < 0.5, f"allocations sum to {total_alloc}"


def _fake_universe_with_defensives(country, sectors, include_tickers, exclude_tickers, risk_level):
    """Mock universe selector that mirrors the real one's auto-inject
    behavior: 10 fake stocks always, plus 5 defensive ETFs when risk_level <= 3."""
    stocks = [
        {"ticker": f"T{i}", "company_name": f"Co{i}", "sector": "Technology",
         "exchange": "", "is_defensive": False}
        for i in range(10)
    ]
    if risk_level <= 3:
        stocks.extend([
            {"ticker": "AGG", "company_name": "iShares Core US Aggregate Bond ETF",
             "sector": "Bonds", "exchange": "", "is_defensive": True},
            {"ticker": "IEF", "company_name": "iShares 7-10 Year Treasury Bond ETF",
             "sector": "Bonds", "exchange": "", "is_defensive": True},
            {"ticker": "GLD", "company_name": "SPDR Gold Trust",
             "sector": "Commodities", "exchange": "", "is_defensive": True},
            {"ticker": "XLU", "company_name": "Utilities Select Sector SPDR Fund",
             "sector": "Utilities", "exchange": "", "is_defensive": True},
            {"ticker": "XLP", "company_name": "Consumer Staples Select Sector SPDR Fund",
             "sector": "Consumer Staples", "exchange": "", "is_defensive": True},
        ])
    return stocks


@patch("app.engine.pipeline.select_universe", side_effect=_fake_universe_with_defensives)
@patch("app.engine.pipeline.yf.download", side_effect=_fake_yf_download)
def test_pipeline_holdings_carry_is_defensive_flag(mock_dl, mock_uni):
    # risk_level changed from 2 -> 1 to keep this test on the HRP-win path
    # after P5's symmetric routing rule (see test_pipeline_hrp_wins_on_synthetic_data
    # for the same rationale). At risk_level >= 2 the new rule routes to
    # mvo_underutilized, where MVO might or might not preserve defensives
    # depending on the predictor's expected returns.
    result = generate_portfolio(
        country="US", risk_level=1, investment_horizon="3-5y",
        available_amount=10_000.0, target_return=10.0,
        preferred_sectors=["Technology"], include_tickers=[], exclude_tickers=[],
        db=None,
    )

    assert "error" not in result, f"pipeline returned error: {result.get('error')}"
    # Every holding must have the is_defensive field populated.
    for h in result["holdings"]:
        assert "is_defensive" in h, f"holding missing is_defensive: {h}"
        assert isinstance(h["is_defensive"], bool)
    # At least one defensive ETF is in the holdings (the synthetic universe
    # plus risk_level=1 should make HRP put non-trivial weight on bonds).
    defensive_holdings = [h for h in result["holdings"] if h["is_defensive"]]
    assert len(defensive_holdings) > 0, "expected at least one defensive holding at risk_level=1"


@patch("app.engine.pipeline.select_universe", side_effect=_fake_universe)
@patch("app.engine.pipeline.yf.download", side_effect=_fake_yf_download)
def test_pipeline_mvo_underutilized_routes_to_mvo_optimal(mock_dl, mock_uni):
    """At risk_level=5 with the synthetic 10-ticker universe, HRP candidate
    vol (~7%) sits well below cap × LOWER (0.7 × 35% = 24.5%). The new
    symmetric rule must route to MVO with the underutilized label."""
    result = generate_portfolio(
        country="US", risk_level=5, investment_horizon="3-5y",
        available_amount=10_000.0, target_return=10.0,
        preferred_sectors=["Technology"], include_tickers=[], exclude_tickers=[],
        db=None,
    )

    assert "error" not in result, f"pipeline returned error: {result.get('error')}"
    assert result["weighting_method"] == "mvo_underutilized"
    assert result["optimizer_status"] == "optimal"
    assert result["hrp_candidate_vol"] is not None  # HRP did produce a candidate


@patch("app.engine.pipeline.optimize_portfolio", side_effect=_fake_optimize_equal_weight_fallback)
@patch("app.engine.pipeline.select_universe", side_effect=_fake_universe)
@patch("app.engine.pipeline.yf.download", side_effect=_fake_yf_download)
def test_pipeline_mvo_underutilized_with_optimizer_fallback(mock_dl, mock_uni, mock_opt):
    """Same routing trigger as above, but the mocked optimizer returns its
    equal-weight fallback. Verifies the equal-weight collapse semantics —
    weighting_method reports the final outcome (not the entry path),
    optimizer_status mirrors it, and hrp_candidate_vol stays populated
    since HRP did produce a candidate before MVO was invoked."""
    result = generate_portfolio(
        country="US", risk_level=5, investment_horizon="3-5y",
        available_amount=10_000.0, target_return=10.0,
        preferred_sectors=["Technology"], include_tickers=[], exclude_tickers=[],
        db=None,
    )

    assert "error" not in result, f"pipeline returned error: {result.get('error')}"
    assert result["weighting_method"] == "fallback_equal_weight"
    assert result["optimizer_status"] == "fallback_equal_weight"
    assert result["hrp_candidate_vol"] is not None  # HRP did produce a candidate
