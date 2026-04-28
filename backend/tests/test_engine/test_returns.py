"""Tests for engine.returns."""

import numpy as np
import pandas as pd
import pytest

from app.engine.returns import daily_log_returns


def test_log_returns_known_input():
    """Hand-computed example."""
    prices = pd.DataFrame({
        "X": [100.0, 110.0, 99.0],  # +10%, then -10%
    }, index=pd.date_range("2026-01-01", periods=3))

    result = daily_log_returns(prices)

    assert result.shape == (2, 1)
    np.testing.assert_allclose(
        result["X"].values,
        [np.log(110/100), np.log(99/110)],
        rtol=1e-10,
    )


def test_log_returns_drops_first_row():
    """The first row has no previous price → must be dropped."""
    prices = pd.DataFrame({"X": [10.0, 11.0]})
    result = daily_log_returns(prices)
    assert len(result) == 1


def test_log_returns_two_assets():
    """Independent series stay independent."""
    prices = pd.DataFrame({
        "A": [100.0, 200.0],
        "B": [50.0, 25.0],
    })
    result = daily_log_returns(prices)
    assert pytest.approx(result["A"].iloc[0]) == np.log(2.0)
    assert pytest.approx(result["B"].iloc[0]) == np.log(0.5)
