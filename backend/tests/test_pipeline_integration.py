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


def _fake_universe(country, sectors, include_tickers, exclude_tickers):
    return [
        {"ticker": f"T{i}", "company_name": f"Co{i}", "sector": "Technology", "exchange": ""}
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
    from app.engine.optimizer import RISK_VOLATILITY_CAP
    from app.engine.pipeline import HRP_VOL_TOLERANCE

    result = generate_portfolio(
        country="US", risk_level=3, investment_horizon="3-5y",
        available_amount=10_000.0, target_return=10.0,
        preferred_sectors=["Technology"], include_tickers=[], exclude_tickers=[],
        db=None,
    )

    assert "error" not in result, f"pipeline returned error: {result.get('error')}"
    assert result["weighting_method"] == "hrp"
    assert result["optimizer_status"] is None
    assert result["hrp_candidate_vol"] is not None

    target_vol = RISK_VOLATILITY_CAP[3]
    assert 0 < result["hrp_candidate_vol"] <= target_vol * HRP_VOL_TOLERANCE

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
    from app.engine.pipeline import HRP_VOL_TOLERANCE

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
    assert result["hrp_candidate_vol"] > RISK_VOLATILITY_CAP[1] * HRP_VOL_TOLERANCE


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
