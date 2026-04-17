from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from app.engine.screens import apply_quality_screen


def _build_batch(tickers, n_days=520, end=date(2026, 4, 16), volume=1_000_000.0):
    """Build a synthetic yfinance-shaped batch (MultiIndex columns) with a
    deterministic price/volume panel. Each ticker gets identical structure;
    callers can override Close or Volume per ticker via post-processing."""
    rng = np.random.default_rng(seed=42)
    dates = pd.bdate_range(end=end.isoformat(), periods=n_days)
    frames = []
    for t in tickers:
        returns = rng.normal(0.0003, 0.015, n_days)
        prices = 100.0 * np.cumprod(1 + returns)
        df = pd.DataFrame({"Close": prices, "Volume": np.full(n_days, volume)}, index=dates)
        frames.append(df)
    return pd.concat(frames, axis=1, keys=tickers), dates


@pytest.fixture
def cov_cutoff():
    return date(2026, 4, 16) - timedelta(days=2 * 365)


def test_happy_path_all_tickers_survive(cov_cutoff):
    tickers = [f"T{i}" for i in range(10)]
    batch, _ = _build_batch(tickers)

    price_data, dropped = apply_quality_screen(batch, tickers, cov_cutoff)

    assert list(price_data.keys()) == tickers
    assert dropped == []
    for t in tickers:
        assert isinstance(price_data[t], pd.Series)
        assert (price_data[t].index.date >= cov_cutoff).all()


def test_drops_low_adv(cov_cutoff):
    tickers = ["A", "B", "C"]
    batch, _ = _build_batch(tickers, volume=1.0)  # ADV << $10M

    price_data, dropped = apply_quality_screen(batch, tickers, cov_cutoff)

    assert price_data == {}
    assert {d["ticker"] for d in dropped} == {"A", "B", "C"}
    for d in dropped:
        assert "low_adv" in d["reasons"]
        assert d["adv_30d_usd"] is not None
        assert d["adv_30d_usd"] < 10_000_000
        assert d["history_fraction"] >= 0.95


def test_drops_sparse_history(cov_cutoff):
    tickers = ["A", "B"]
    batch, dates = _build_batch(tickers)
    # Knock out a large block of recent rows for A so its history fraction
    # falls below 0.95 but recent data is still measurable.
    holes = dates[(dates.date >= cov_cutoff)][:60]
    for d in holes:
        batch.loc[d, ("A", "Close")] = np.nan

    price_data, dropped = apply_quality_screen(batch, tickers, cov_cutoff)

    assert "A" not in price_data
    assert "B" in price_data
    drop_a = next(d for d in dropped if d["ticker"] == "A")
    assert "sparse_history" in drop_a["reasons"]
    assert drop_a["history_fraction"] < 0.95


def test_drops_insufficient_recent_data(cov_cutoff):
    tickers = ["A"]
    batch, dates = _build_batch(tickers)
    # Knock out the last 25 rows of Close for A, leaving only ~5 usable
    # rows in the trailing 30-row window (< MIN_RECENT_OBSERVATIONS = 10).
    recent_dates = dates[-25:]
    for d in recent_dates:
        batch.loc[d, ("A", "Close")] = np.nan

    price_data, dropped = apply_quality_screen(batch, tickers, cov_cutoff)

    assert price_data == {}
    drop_a = next(d for d in dropped if d["ticker"] == "A")
    assert "insufficient_recent_data" in drop_a["reasons"]
    assert drop_a["adv_30d_usd"] is None


def test_drops_missing_data(cov_cutoff):
    tickers_in_batch = ["A", "B"]
    tickers_to_screen = ["A", "B", "GHOST"]   # GHOST is absent from batch
    batch, _ = _build_batch(tickers_in_batch)

    price_data, dropped = apply_quality_screen(batch, tickers_to_screen, cov_cutoff)

    assert "GHOST" not in price_data
    drop_ghost = next(d for d in dropped if d["ticker"] == "GHOST")
    assert drop_ghost["reasons"] == ["missing_data"]
    assert drop_ghost["adv_30d_usd"] is None
    assert drop_ghost["history_fraction"] == 0.0


def test_drops_when_cov_window_empty():
    # Build a batch whose entire date range is BEFORE the cov_cutoff.
    tickers = ["A"]
    old_end = date(2020, 1, 1)
    batch, _ = _build_batch(tickers, n_days=100, end=old_end)
    cov_cutoff = date(2026, 1, 1)

    price_data, dropped = apply_quality_screen(batch, tickers, cov_cutoff)

    assert price_data == {}
    drop_a = next(d for d in dropped if d["ticker"] == "A")
    assert "sparse_history" in drop_a["reasons"]
    assert drop_a["history_fraction"] == 0.0


def test_preserves_input_order(cov_cutoff):
    tickers = ["Z", "A", "M", "B", "Q"]
    batch, _ = _build_batch(tickers)

    price_data, _ = apply_quality_screen(batch, tickers, cov_cutoff)

    assert list(price_data.keys()) == tickers
