# Covariance Shrinkage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the raw sample covariance in the portfolio engine with a Ledoit-Wolf shrinkage estimator, including a sample-covariance fallback on technical failure, and surface the method + shrinkage intensity through the engine result and API response.

**Architecture:** A new `backend/app/engine/risk.py` module exposes a single `estimate_covariance(returns)` function. The function cleans NaN, validates minimum counts, runs sklearn's `LedoitWolf`, falls back to `clean_returns.cov()` on runtime error, and returns `(cov_matrix, shrinkage, metadata)`. `pipeline.py` swaps its one covariance line to call this function, realigns ticker-ordered structures if cleaning dropped any tickers, and threads two new fields (`covariance_method`, `shrinkage_intensity`) through to the response. `PortfolioResponse` gets two new optional fields. The methodology page gains one plain-language paragraph.

**Tech Stack:** Python 3 + numpy + pandas + scikit-learn 1.5.0 (already a dependency) + FastAPI + Pydantic + pytest. Frontend: React + TypeScript (single `.tsx` edit).

**Spec:** [docs/superpowers/specs/2026-04-17-covariance-shrinkage-design.md](../specs/2026-04-17-covariance-shrinkage-design.md)

**File map:**
- Create: `backend/app/engine/risk.py` — `estimate_covariance()` helper
- Create: `backend/tests/test_risk.py` — unit tests for the helper
- Create: `backend/tests/test_pipeline_integration.py` — end-to-end integration test
- Modify: `backend/app/engine/pipeline.py` — call helper, realign tickers, add result fields
- Modify: `backend/app/schemas/portfolio.py` — add optional fields to `PortfolioResponse`
- Modify: `backend/app/api/portfolios.py` — pass new fields from engine result to response
- Modify: `backend/tests/test_portfolios.py` — extend `MOCK_ENGINE_RESULT` + assertion
- Modify: `frontend/src/methodology/MethodologyPage.tsx` — add shrinkage paragraph

**Test execution:** all backend commands assume the repo root. Use the existing docker compose setup:
```bash
docker compose run --rm backend pytest <path> -v
```

---

## Task 1: Create the `estimate_covariance` helper — happy path (TDD)

**Files:**
- Create: `backend/app/engine/risk.py`
- Create: `backend/tests/test_risk.py`

- [ ] **Step 1: Write the failing happy-path test**

Create `backend/tests/test_risk.py`:

```python
import numpy as np
import pandas as pd
import pytest

from app.engine.risk import estimate_covariance


@pytest.fixture
def synthetic_returns():
    rng = np.random.default_rng(seed=42)
    data = rng.multivariate_normal(
        mean=np.zeros(5),
        cov=np.eye(5) * 0.0004,
        size=200,
    )
    return pd.DataFrame(data, columns=["A", "B", "C", "D", "E"])


def test_happy_path_shape_and_types(synthetic_returns):
    cov, shrinkage, meta = estimate_covariance(synthetic_returns)
    assert cov.shape == (5, 5)
    assert np.allclose(cov, cov.T)
    assert isinstance(shrinkage, float)
    assert 0.0 <= shrinkage <= 1.0
    assert meta["method"] == "ledoit_wolf"
    assert meta["n_tickers"] == 5
    assert meta["n_observations"] == 200
    assert meta["dropped_tickers"] == []
    assert meta["fallback_used"] is False
    assert meta["fallback_reason"] is None


def test_psd_within_tolerance(synthetic_returns):
    cov, _, _ = estimate_covariance(synthetic_returns)
    assert float(np.linalg.eigvalsh(cov).min()) > -1e-8
```

- [ ] **Step 2: Run test and verify it fails**

```bash
docker compose run --rm backend pytest tests/test_risk.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.engine.risk'`.

- [ ] **Step 3: Create the minimal module**

Create `backend/app/engine/risk.py`:

```python
import logging

import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf

logger = logging.getLogger(__name__)

TRADING_DAYS_PER_YEAR = 252
MIN_OBSERVATIONS = 30
MIN_TICKERS = 2
PSD_TOLERANCE = -1e-8


def estimate_covariance(returns: pd.DataFrame) -> tuple[np.ndarray, float, dict]:
    """Estimate an annualized covariance matrix from daily returns.

    Uses Ledoit-Wolf shrinkage with a sample-covariance fallback on
    technical failure. Cleans NaN from the input frame before estimation;
    all downstream logic operates on the cleaned frame.
    """
    clean_returns = returns.dropna(how="any")
    n_tickers = clean_returns.shape[1]
    n_observations = clean_returns.shape[0]

    metadata = {
        "method": "ledoit_wolf",
        "n_tickers": n_tickers,
        "n_observations": n_observations,
        "dropped_tickers": [],
        "fallback_used": False,
        "fallback_reason": None,
    }

    lw = LedoitWolf().fit(clean_returns.values)
    daily_cov = lw.covariance_
    shrinkage = float(lw.shrinkage_)

    cov_matrix = daily_cov * TRADING_DAYS_PER_YEAR

    logger.info(
        "covariance_estimated method=%s n_tickers=%d n_obs=%d shrinkage=%.4f dropped=0 fallback=False",
        metadata["method"], n_tickers, n_observations, shrinkage,
    )

    return cov_matrix, shrinkage, metadata
```

- [ ] **Step 4: Run tests and verify they pass**

```bash
docker compose run --rm backend pytest tests/test_risk.py -v
```

Expected: both tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/engine/risk.py backend/tests/test_risk.py
git commit -m "feat(risk): add Ledoit-Wolf covariance estimator (happy path)"
```

---

## Task 2: NaN handling and validation errors (TDD)

**Files:**
- Modify: `backend/app/engine/risk.py`
- Modify: `backend/tests/test_risk.py`

- [ ] **Step 1: Write the failing NaN + validation tests**

Append to `backend/tests/test_risk.py`:

```python
def test_drops_all_nan_column(synthetic_returns):
    df = synthetic_returns.copy()
    df["C"] = np.nan
    cov, _, meta = estimate_covariance(df)
    assert cov.shape == (4, 4)
    assert meta["dropped_tickers"] == ["C"]
    assert meta["n_tickers"] == 4
    assert meta["n_observations"] == 200


def test_drops_rows_with_any_nan(synthetic_returns):
    df = synthetic_returns.copy()
    df.iloc[5:10, 2] = np.nan
    cov, _, meta = estimate_covariance(df)
    assert cov.shape == (5, 5)
    assert meta["n_observations"] == 195
    assert meta["dropped_tickers"] == []


def test_raises_on_too_few_tickers(synthetic_returns):
    df = synthetic_returns[["A"]]
    with pytest.raises(ValueError, match="at least 2 tickers"):
        estimate_covariance(df)


def test_raises_on_too_few_observations(synthetic_returns):
    df = synthetic_returns.iloc[:20]
    with pytest.raises(ValueError, match="at least 30 observations"):
        estimate_covariance(df)


def test_raises_on_non_numeric_column(synthetic_returns):
    df = synthetic_returns.copy()
    df["A"] = "not a number"
    with pytest.raises(ValueError, match="numeric columns"):
        estimate_covariance(df)
```

- [ ] **Step 2: Run tests and verify the new ones fail**

```bash
docker compose run --rm backend pytest tests/test_risk.py -v
```

Expected: the two original tests still PASS; `test_drops_all_nan_column` FAILS (the current implementation doesn't detect all-NaN columns separately from row drops, so shape and `dropped_tickers` won't match); the three `test_raises_*` tests FAIL (no validation yet).

- [ ] **Step 3: Extend `estimate_covariance` with dtype check, all-NaN column drop, and validation**

Replace the body of `estimate_covariance` in `backend/app/engine/risk.py` with:

```python
def estimate_covariance(returns: pd.DataFrame) -> tuple[np.ndarray, float, dict]:
    """Estimate an annualized covariance matrix from daily returns.

    Uses Ledoit-Wolf shrinkage with a sample-covariance fallback on
    technical failure. Cleans NaN from the input frame before estimation;
    all downstream logic operates on the cleaned frame.
    """
    # Fail fast on non-numeric columns — no silent coercion.
    for col in returns.columns:
        if not pd.api.types.is_numeric_dtype(returns[col]):
            raise ValueError("estimate_covariance requires numeric columns")

    # Drop all-NaN columns first so dropna(how='any') doesn't erase every row.
    all_nan_cols = [c for c in returns.columns if returns[c].isna().all()]
    clean_returns = returns.drop(columns=all_nan_cols)
    clean_returns = clean_returns.dropna(how="any")

    n_tickers = clean_returns.shape[1]
    n_observations = clean_returns.shape[0]
    dropped_tickers = [str(c) for c in all_nan_cols]

    if n_tickers < MIN_TICKERS:
        raise ValueError(
            f"estimate_covariance requires at least {MIN_TICKERS} tickers after cleaning"
        )
    if n_observations < MIN_OBSERVATIONS:
        raise ValueError(
            f"estimate_covariance requires at least {MIN_OBSERVATIONS} observations after cleaning"
        )

    metadata = {
        "method": "ledoit_wolf",
        "n_tickers": n_tickers,
        "n_observations": n_observations,
        "dropped_tickers": dropped_tickers,
        "fallback_used": False,
        "fallback_reason": None,
    }

    lw = LedoitWolf().fit(clean_returns.values)
    daily_cov = lw.covariance_
    shrinkage = float(lw.shrinkage_)

    cov_matrix = daily_cov * TRADING_DAYS_PER_YEAR

    min_eig = float(np.linalg.eigvalsh(cov_matrix).min())
    if min_eig < PSD_TOLERANCE:
        logger.warning(
            "estimate_covariance produced non-PSD matrix (min eigenvalue %.3e)", min_eig
        )

    logger.info(
        "covariance_estimated method=%s n_tickers=%d n_obs=%d shrinkage=%.4f dropped=%d fallback=%s",
        metadata["method"], n_tickers, n_observations, shrinkage,
        len(dropped_tickers), metadata["fallback_used"],
    )

    return cov_matrix, shrinkage, metadata
```

- [ ] **Step 4: Run tests and verify all pass**

```bash
docker compose run --rm backend pytest tests/test_risk.py -v
```

Expected: all seven tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/engine/risk.py backend/tests/test_risk.py
git commit -m "feat(risk): add NaN handling and input validation"
```

---

## Task 3: Fallback on sklearn failure (TDD)

**Files:**
- Modify: `backend/app/engine/risk.py`
- Modify: `backend/tests/test_risk.py`

- [ ] **Step 1: Write the failing fallback test**

Append to `backend/tests/test_risk.py`:

```python
from unittest.mock import patch


def test_fallback_on_sklearn_failure(synthetic_returns):
    with patch("app.engine.risk.LedoitWolf") as mock_lw:
        mock_lw.return_value.fit.side_effect = RuntimeError("boom")
        cov, shrinkage, meta = estimate_covariance(synthetic_returns)
    assert cov.shape == (5, 5)
    assert shrinkage == 0.0
    assert meta["method"] == "sample_fallback"
    assert meta["fallback_used"] is True
    assert "boom" in meta["fallback_reason"]
    expected = synthetic_returns.cov().values * 252
    assert np.allclose(cov, expected)
```

- [ ] **Step 2: Run test and verify it fails**

```bash
docker compose run --rm backend pytest tests/test_risk.py::test_fallback_on_sklearn_failure -v
```

Expected: FAIL — the current code lets `RuntimeError("boom")` propagate rather than falling back.

- [ ] **Step 3: Wrap the Ledoit-Wolf call in try/except with sample-cov fallback**

In `backend/app/engine/risk.py`, replace the block starting at `lw = LedoitWolf().fit(...)` through the `cov_matrix = daily_cov * TRADING_DAYS_PER_YEAR` line with:

```python
    try:
        lw = LedoitWolf().fit(clean_returns.values)
        daily_cov = lw.covariance_
        shrinkage = float(lw.shrinkage_)
        if not np.all(np.isfinite(daily_cov)):
            raise RuntimeError("LedoitWolf produced non-finite covariance")
    except Exception as exc:
        logger.warning(
            "estimate_covariance fallback to sample cov: %s: %s",
            type(exc).__name__, exc,
        )
        daily_cov = clean_returns.cov().values
        shrinkage = 0.0
        metadata["method"] = "sample_fallback"
        metadata["fallback_used"] = True
        metadata["fallback_reason"] = f"{type(exc).__name__}: {exc}"

    cov_matrix = daily_cov * TRADING_DAYS_PER_YEAR
```

- [ ] **Step 4: Run tests and verify all pass**

```bash
docker compose run --rm backend pytest tests/test_risk.py -v
```

Expected: all eight tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/engine/risk.py backend/tests/test_risk.py
git commit -m "feat(risk): add sample-covariance fallback on sklearn failure"
```

---

## Task 4: Integrate with the pipeline

**Files:**
- Modify: `backend/app/engine/pipeline.py`

- [ ] **Step 1: Add the import and swap the covariance line**

At the top of `backend/app/engine/pipeline.py`, add the import alongside the other engine imports:

```python
from app.engine.risk import estimate_covariance
```

Then locate this block (currently around lines 74-80):

```python
    prices_df = pd.DataFrame(price_data).dropna()
    returns_df = prices_df.pct_change().dropna()
    cov_matrix = returns_df.cov().values * 252

    ticker_to_stock = {s["ticker"]: s for s in stocks}
    valid_stocks = [ticker_to_stock[t] for t in valid_tickers]
    valid_returns = np.array([s["expected_return"] for s in valid_stocks])
```

Replace it with:

```python
    prices_df = pd.DataFrame(price_data).dropna()
    returns_df = prices_df.pct_change().dropna()

    try:
        cov_matrix, shrinkage, cov_meta = estimate_covariance(returns_df)
    except ValueError:
        return {"error": "Not enough historical data available."}

    # Realign every ticker-ordered structure to the cleaned ticker set
    # before handing anything to the optimizer.
    if cov_meta["dropped_tickers"]:
        dropped = set(cov_meta["dropped_tickers"])
        valid_tickers = [t for t in valid_tickers if t not in dropped]
        if len(valid_tickers) < 5:
            return {"error": "Not enough historical data available."}

    ticker_to_stock = {s["ticker"]: s for s in stocks}
    valid_stocks = [ticker_to_stock[t] for t in valid_tickers]
    valid_returns = np.array([s["expected_return"] for s in valid_stocks])
```

- [ ] **Step 2: Add the two new fields to the engine result dict**

In the final `return { ... }` at the bottom of `generate_portfolio`, add two keys. Replace:

```python
    return {
        "holdings": holdings,
        "risk_score": round(opt_result["portfolio_volatility"] * 100, 2),
        "expected_return_low": round(sim_result["return_low"] * 100, 2),
        "expected_return_high": round(sim_result["return_high"] * 100, 2),
        "portfolio_return": round(opt_result["portfolio_return"] * 100, 2),
        "simulation": sim_result,
        "status": opt_result["status"],
    }
```

with:

```python
    return {
        "holdings": holdings,
        "risk_score": round(opt_result["portfolio_volatility"] * 100, 2),
        "expected_return_low": round(sim_result["return_low"] * 100, 2),
        "expected_return_high": round(sim_result["return_high"] * 100, 2),
        "portfolio_return": round(opt_result["portfolio_return"] * 100, 2),
        "simulation": sim_result,
        "status": opt_result["status"],
        "covariance_method": cov_meta["method"],
        "shrinkage_intensity": round(shrinkage, 4),
    }
```

- [ ] **Step 3: Run the existing portfolio tests to verify no regression**

```bash
docker compose run --rm backend pytest tests/test_portfolios.py tests/test_risk.py -v
```

Expected: all tests PASS. `test_portfolios.py` tests mock `generate_portfolio` at the API boundary, so the pipeline-internal change does not affect them yet.

- [ ] **Step 4: Commit**

```bash
git add backend/app/engine/pipeline.py
git commit -m "feat(pipeline): wire in estimate_covariance with ticker realignment"
```

---

## Task 5: Surface new fields through the schema + API response

**Files:**
- Modify: `backend/app/schemas/portfolio.py`
- Modify: `backend/app/api/portfolios.py`
- Modify: `backend/tests/test_portfolios.py`

- [ ] **Step 1: Add optional fields to `PortfolioResponse`**

In `backend/app/schemas/portfolio.py`, modify `PortfolioResponse` (currently lines 23-34). Replace:

```python
class PortfolioResponse(BaseModel):
    id: str
    status: str
    risk_score: float
    expected_return_low: float
    expected_return_high: float
    portfolio_return: float
    total_value: float
    holdings: list[HoldingResponse]
    simulation: SimulationResponse

    model_config = {"from_attributes": True}
```

with:

```python
class PortfolioResponse(BaseModel):
    id: str
    status: str
    risk_score: float
    expected_return_low: float
    expected_return_high: float
    portfolio_return: float
    total_value: float
    holdings: list[HoldingResponse]
    simulation: SimulationResponse
    covariance_method: str | None = None
    shrinkage_intensity: float | None = None

    model_config = {"from_attributes": True}
```

- [ ] **Step 2: Pass the new fields from engine result to response in `generate`**

In `backend/app/api/portfolios.py`, locate the `PortfolioResponse(...)` construction inside the `generate` endpoint (the one that returns a 201). Add the two new fields using `.get(...)` with a `None` default so pre-existing mocks without these keys still deserialize:

Find:

```python
    return PortfolioResponse(
        id=str(portfolio.id),
        status=portfolio.status,
        risk_score=float(portfolio.risk_score),
        expected_return_low=float(portfolio.expected_return_low),
        expected_return_high=float(portfolio.expected_return_high),
        portfolio_return=result["portfolio_return"],
        total_value=float(portfolio.total_value),
        holdings=[HoldingResponse(**h) for h in result["holdings"]],
        simulation=SimulationResponse(**result["simulation"]),
    )
```

Add two lines before the closing `)`:

```python
    return PortfolioResponse(
        id=str(portfolio.id),
        status=portfolio.status,
        risk_score=float(portfolio.risk_score),
        expected_return_low=float(portfolio.expected_return_low),
        expected_return_high=float(portfolio.expected_return_high),
        portfolio_return=result["portfolio_return"],
        total_value=float(portfolio.total_value),
        holdings=[HoldingResponse(**h) for h in result["holdings"]],
        simulation=SimulationResponse(**result["simulation"]),
        covariance_method=result.get("covariance_method"),
        shrinkage_intensity=result.get("shrinkage_intensity"),
    )
```

**Do NOT add these fields to the `get_portfolio` retrieval endpoint.** The Portfolio DB model does not persist these fields in this phase, so on retrieval they would always be `None` — which `Optional` already handles via the default. Leave that endpoint untouched.

- [ ] **Step 3: Update `MOCK_ENGINE_RESULT` in `test_portfolios.py`**

In `backend/tests/test_portfolios.py`, locate `MOCK_ENGINE_RESULT` (top of file) and add two keys to the dict:

```python
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
```

- [ ] **Step 4: Add an assertion to `test_generate_portfolio`**

Still in `backend/tests/test_portfolios.py`, extend `test_generate_portfolio` (currently near line 30). Replace:

```python
@patch("app.api.portfolios.generate_portfolio", return_value=MOCK_ENGINE_RESULT)
def test_generate_portfolio(mock_engine, client, auth_headers):
    profile_resp = client.post("/profiles", json=PROFILE_PAYLOAD, headers=auth_headers)
    profile_id = profile_resp.json()["id"]
    resp = client.post(f"/portfolios/generate/{profile_id}", headers=auth_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert len(data["holdings"]) == 5
    assert data["risk_score"] == 18.5
```

with:

```python
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
```

- [ ] **Step 5: Run tests and verify pass**

```bash
docker compose run --rm backend pytest tests/test_portfolios.py -v
```

Expected: all `test_portfolios.py` tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/portfolio.py backend/app/api/portfolios.py backend/tests/test_portfolios.py
git commit -m "feat(api): expose covariance_method and shrinkage_intensity in generate response"
```

---

## Task 6: End-to-end pipeline integration test

**Files:**
- Create: `backend/tests/test_pipeline_integration.py`

This test exercises the real pipeline (no mocking of `generate_portfolio`) with a deterministic synthetic price panel injected at the `yfinance.download` boundary. It is the primary guard against the ticker-realignment bug and confirms the new fields flow end-to-end through the engine.

- [ ] **Step 1: Write the integration test**

Create `backend/tests/test_pipeline_integration.py`:

```python
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
    # MAX_SINGLE_WEIGHT in optimizer.py is 0.30 → 30% as a pct
    assert all(h["allocation_pct"] <= 30.01 for h in result["holdings"])
```

- [ ] **Step 2: Run the integration test**

```bash
docker compose run --rm backend pytest tests/test_pipeline_integration.py -v
```

Expected: test PASSES. If it fails, the most likely causes in order:
1. `predict_returns` is still calling `yf.download` despite the pipeline passing `batch=batch` — inspect `app/engine/predictor.py` to confirm the `batch` branch is taken.
2. Ticker realignment missed a structure — check that `valid_tickers`, `valid_stocks`, `valid_returns` all reflect drops from `cov_meta["dropped_tickers"]`.
3. Synthetic prices produce an infeasible optimizer problem — widen `n_days` or loosen the random seed.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_pipeline_integration.py
git commit -m "test(pipeline): add end-to-end integration test for covariance metadata"
```

---

## Task 7: Methodology page paragraph

**Files:**
- Modify: `frontend/src/methodology/MethodologyPage.tsx`

- [ ] **Step 1: Add the shrinkage paragraph**

In `frontend/src/methodology/MethodologyPage.tsx`, locate the `<section id="optimization">` block (currently lines 43-54). Its current last paragraph is the "eggs in one basket" paragraph (lines 49-53). Add one new paragraph immediately after it, still inside the same `<section>`:

Replace:

```tsx
      <section id="optimization" className="bg-white p-6 rounded-xl shadow mb-6">
        <h2 className="text-2xl font-bold mb-3">Balancing the Portfolio</h2>
        <p className="text-gray-700 mb-3">
          Once we have per-stock estimates, we solve an optimization problem: how much of each stock
          should you hold to get the best expected return at your chosen risk level?
        </p>
        <p className="text-gray-700 mb-3">
          This is based on a well-established technique called <strong>mean-variance optimization</strong>.
          The intuition: don't put all your eggs in one basket. Spreading across multiple stocks and
          sectors reduces the damage any single bad pick can cause.
        </p>
      </section>
```

with:

```tsx
      <section id="optimization" className="bg-white p-6 rounded-xl shadow mb-6">
        <h2 className="text-2xl font-bold mb-3">Balancing the Portfolio</h2>
        <p className="text-gray-700 mb-3">
          Once we have per-stock estimates, we solve an optimization problem: how much of each stock
          should you hold to get the best expected return at your chosen risk level?
        </p>
        <p className="text-gray-700 mb-3">
          This is based on a well-established technique called <strong>mean-variance optimization</strong>.
          The intuition: don't put all your eggs in one basket. Spreading across multiple stocks and
          sectors reduces the damage any single bad pick can cause.
        </p>
        <p className="text-gray-700 mb-3">
          To measure how different stocks move together, we use a shrinkage technique. Raw
          correlations between stocks can be misleading when the data is noisy. Shrinkage nudges
          those correlations toward a more reliable baseline, which makes the resulting portfolio
          less sensitive to random quirks in the historical data. This is a well-established
          technique in professional portfolio construction.
        </p>
      </section>
```

- [ ] **Step 2: Type-check the frontend**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors (the change is a pure-JSX addition with no new props or types).

- [ ] **Step 3: Manually verify in the browser**

Start the dev server and visit the methodology page to confirm the paragraph renders inline with the existing "Balancing the Portfolio" section and the rest of the page is unchanged:

```bash
# from repo root — or use the existing run script if one is set up
cd frontend && npm run dev
```

Navigate to `/methodology`, scroll to "Balancing the Portfolio", confirm the new paragraph appears as the third paragraph of that section, and that the "Important Limitations" callout and glossary below render unchanged.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/methodology/MethodologyPage.tsx
git commit -m "docs(methodology): add shrinkage paragraph to Balancing the Portfolio"
```

---

## Task 8: Full-suite verification

**Files:** none.

- [ ] **Step 1: Run the full backend test suite**

```bash
docker compose run --rm backend pytest -v
```

Expected: all tests PASS, including the three new/modified files (`test_risk.py`, `test_pipeline_integration.py`, `test_portfolios.py`).

- [ ] **Step 2: Confirm the log line appears when the pipeline runs**

Trigger a real portfolio generation (via the UI or a direct API call against a local stack) and confirm a log line of the form:

```
covariance_estimated method=ledoit_wolf n_tickers=<N> n_obs=<K> shrinkage=<α> dropped=<D> fallback=False
```

appears in the backend logs. This verifies observability end-to-end and catches any wiring issue that tests might miss.

- [ ] **Step 3: Eyeball risk_score on a test portfolio**

Generate one portfolio with the same profile before and after this change (two separate deployed states or a side-by-side branch comparison). The post-change `risk_score` should be the same order of magnitude as the pre-change value and should **not** change by more than ~20–30% in either direction. A larger swing indicates the shrinkage is doing something pathological rather than stabilizing — investigate before shipping broadly.

---

## Out of scope (do NOT add to this plan)

- Changes to predictor, optimizer, or simulator
- Alembic migration to persist `covariance_method` / `shrinkage_intensity`
- Factor / PCA / EWMA / GARCH covariance estimators
- UI-level choice of estimator
- Changing the 2-year lookback window, return definition, or annualization constant

These belong to future phases (P2–P4 in the roadmap) or are deferred by explicit decision in the spec.
