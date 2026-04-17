import numpy as np
from app.engine.optimizer import optimize_portfolio


def test_basic_optimization():
    expected_returns = np.array([0.12, 0.10, 0.08, 0.15, 0.09])
    cov_matrix = np.array([
        [0.04, 0.006, 0.002, 0.01, 0.003],
        [0.006, 0.03, 0.004, 0.008, 0.002],
        [0.002, 0.004, 0.02, 0.003, 0.001],
        [0.01, 0.008, 0.003, 0.05, 0.005],
        [0.003, 0.002, 0.001, 0.005, 0.025],
    ])
    tickers = ["AAPL", "MSFT", "JNJ", "TSLA", "PG"]

    result = optimize_portfolio(tickers=tickers, expected_returns=expected_returns, cov_matrix=cov_matrix, risk_level=3)

    assert len(result["weights"]) == 5
    assert abs(sum(result["weights"].values()) - 1.0) < 0.01
    assert all(w >= 0 for w in result["weights"].values())
    assert all(w <= 0.20 + 1e-6 for w in result["weights"].values())
    assert "portfolio_return" in result
    assert "portfolio_volatility" in result


def test_minimum_stocks_constraint():
    expected_returns = np.array([0.12, 0.10, 0.08, 0.15, 0.09, 0.11, 0.07])
    cov_matrix = np.eye(7) * 0.03
    tickers = ["A", "B", "C", "D", "E", "F", "G"]

    result = optimize_portfolio(tickers=tickers, expected_returns=expected_returns, cov_matrix=cov_matrix, risk_level=3)

    non_zero = sum(1 for w in result["weights"].values() if w > 0.01)
    assert non_zero >= 5


def test_low_risk_reduces_volatility():
    expected_returns = np.array([0.12, 0.10, 0.08, 0.15, 0.09])
    cov_matrix = np.array([
        [0.04, 0.006, 0.002, 0.01, 0.003],
        [0.006, 0.03, 0.004, 0.008, 0.002],
        [0.002, 0.004, 0.02, 0.003, 0.001],
        [0.01, 0.008, 0.003, 0.05, 0.005],
        [0.003, 0.002, 0.001, 0.005, 0.025],
    ])
    tickers = ["AAPL", "MSFT", "JNJ", "TSLA", "PG"]

    low_risk = optimize_portfolio(tickers, expected_returns, cov_matrix, risk_level=1)
    high_risk = optimize_portfolio(tickers, expected_returns, cov_matrix, risk_level=5)

    assert low_risk["portfolio_volatility"] <= high_risk["portfolio_volatility"]
