# Pipeline Hardening (P2a) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Three independent backend quality fixes shipped as one release: a liquidity/sparseness universe screen, a determinism pass (snapshot pin + simulator seeding), and small optimizer cleanups (lower MAX_SINGLE_WEIGHT, drop dead `target_return` parameter, document MIN_STOCKS).

**Architecture:** A new `backend/app/engine/screens.py` module exposes `apply_quality_screen(batch, tickers, cov_cutoff)`. The pipeline replaces its inline ticker-extraction loop with a single call to this helper, derives `valid_tickers` from the screened output, anchors `end_date`/`start_date_3y`/`cov_cutoff` to a `snapshot_date` of yesterday, and drops the dead `target_return` argument when calling the optimizer. The simulator gains a `_deterministic_seed` helper and switches from `np.random.seed(None)` + `np.random.normal(...)` to `np.random.default_rng(seed).normal(...)`. The optimizer lowers `MAX_SINGLE_WEIGHT` from 0.30 to 0.20 and removes the unused `target_return` parameter from its signature; `MIN_STOCKS` stays as documentation.

**Tech Stack:** Python 3 + numpy + pandas + scikit-learn + cvxpy + FastAPI + pytest. No new dependencies. Backend-only.

**Spec:** [docs/superpowers/specs/2026-04-17-pipeline-hardening-design.md](../specs/2026-04-17-pipeline-hardening-design.md)

**File map:**
- Create: `backend/app/engine/screens.py` — `apply_quality_screen` and constants.
- Create: `backend/tests/test_screens.py` — unit tests for the screen.
- Modify: `backend/app/engine/pipeline.py` — central integration point: snapshot pinning, screen call replacing manual extraction loop, dropped `target_return` from optimizer call, explanatory comment.
- Modify: `backend/app/engine/simulator.py` — add `_deterministic_seed`, switch to `np.random.default_rng`.
- Modify: `backend/app/engine/optimizer.py` — lower `MAX_SINGLE_WEIGHT`, remove `target_return` param, add `MIN_STOCKS` documentation comment.
- Modify: `backend/tests/test_engine/test_simulator.py` — add deterministic-seed test.
- Modify: `backend/tests/test_engine/test_optimizer.py` — drop `target_return=...` from existing test calls; tighten `w <= 0.30` to `w <= 0.20`; verify the previously-red `test_minimum_stocks_constraint` goes green.
- Modify: `backend/tests/test_pipeline_integration.py` — update `<= 30.01` assertion to `<= 20.01`; add three new tests (reproducibility, sensitivity, screen-drop downstream).

**Test execution:** Use the existing docker compose harness with the `TEST_DATABASE_URL` env override that the conftest expects:

```bash
docker compose run --rm -e TEST_DATABASE_URL='postgresql://portfolio:portfolio@db:5432/portfolio_builder_test' backend pytest <path> -v
```

---

## Task 1: Quality screen — happy path (TDD)

**Files:**
- Create: `backend/app/engine/screens.py`
- Create: `backend/tests/test_screens.py`

- [ ] **Step 1: Write the failing happy-path test**

Create `backend/tests/test_screens.py`:

```python
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
```

- [ ] **Step 2: Run test and verify it fails**

```bash
docker compose run --rm -e TEST_DATABASE_URL='postgresql://portfolio:portfolio@db:5432/portfolio_builder_test' backend pytest tests/test_screens.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.engine.screens'`.

- [ ] **Step 3: Create the minimal module**

Create `backend/app/engine/screens.py`:

```python
import logging
from datetime import date

import pandas as pd

logger = logging.getLogger(__name__)

MIN_ADV_USD = 10_000_000
MIN_HISTORY_FRACTION = 0.95
ADV_LOOKBACK_DAYS = 30
MIN_RECENT_OBSERVATIONS = 10


def apply_quality_screen(
    batch: pd.DataFrame,
    tickers: list[str],
    cov_cutoff: date,
) -> tuple[dict[str, pd.Series], list[dict]]:
    """Filter `tickers` by liquidity (30d ADV) and history completeness,
    using the already-downloaded yfinance batch. Returns the surviving
    tickers' Close series in input order, plus a list of drop records."""
    price_data: dict[str, pd.Series] = {}
    dropped: list[dict] = []

    # Build the empirical cov-window calendar from the batch's union date
    # index restricted to >= cov_cutoff.
    if isinstance(batch.index, pd.DatetimeIndex):
        cov_window_dates = batch.index[batch.index.date >= cov_cutoff]
    else:
        cov_window_dates = pd.DatetimeIndex([])
    cov_window_size = len(cov_window_dates)

    for ticker in tickers:
        try:
            close = batch[ticker]["Close"]
            volume = batch[ticker]["Volume"]
        except (KeyError, ValueError):
            dropped.append({
                "ticker": ticker,
                "reasons": ["missing_data"],
                "adv_30d_usd": None,
                "history_fraction": 0.0,
            })
            continue

        usable = pd.DataFrame({"close": close, "volume": volume}).dropna(how="any")
        usable = usable[usable.index.date >= cov_cutoff]

        if cov_window_size == 0:
            dropped.append({
                "ticker": ticker,
                "reasons": ["sparse_history"],
                "adv_30d_usd": None,
                "history_fraction": 0.0,
            })
            continue

        history_fraction = len(usable) / cov_window_size
        reasons: list[str] = []

        recent = usable.tail(ADV_LOOKBACK_DAYS)
        if len(recent) < MIN_RECENT_OBSERVATIONS:
            adv_30d_usd = None
            reasons.append("insufficient_recent_data")
        else:
            adv_30d_usd = float((recent["close"] * recent["volume"]).mean())
            if adv_30d_usd < MIN_ADV_USD:
                reasons.append("low_adv")

        if history_fraction < MIN_HISTORY_FRACTION:
            reasons.append("sparse_history")

        if reasons:
            dropped.append({
                "ticker": ticker,
                "reasons": reasons,
                "adv_30d_usd": adv_30d_usd,
                "history_fraction": history_fraction,
            })
            continue

        price_data[ticker] = usable["close"]

    logger.info(
        "quality_screen kept=%d dropped_low_adv=%d dropped_sparse=%d dropped_recent=%d dropped_missing=%d",
        len(price_data),
        sum(1 for d in dropped if "low_adv" in d["reasons"]),
        sum(1 for d in dropped if "sparse_history" in d["reasons"]),
        sum(1 for d in dropped if "insufficient_recent_data" in d["reasons"]),
        sum(1 for d in dropped if "missing_data" in d["reasons"]),
    )
    for d in dropped:
        logger.debug("quality_screen drop %s", d)

    return price_data, dropped
```

- [ ] **Step 4: Run test and verify it passes**

```bash
docker compose run --rm -e TEST_DATABASE_URL='postgresql://portfolio:portfolio@db:5432/portfolio_builder_test' backend pytest tests/test_screens.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/engine/screens.py backend/tests/test_screens.py
git commit -m "feat(screens): add quality screen module with happy-path implementation"
```

---

## Task 2: Quality screen — drop scenarios (TDD)

**Files:**
- Modify: `backend/tests/test_screens.py`
- Verify (no edits expected): `backend/app/engine/screens.py` (the module already covers all branches; this task only adds tests)

- [ ] **Step 1: Add the drop-scenario tests**

Append to `backend/tests/test_screens.py`:

```python
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
```

- [ ] **Step 2: Run all tests in the file and verify pass**

```bash
docker compose run --rm -e TEST_DATABASE_URL='postgresql://portfolio:portfolio@db:5432/portfolio_builder_test' backend pytest tests/test_screens.py -v
```

Expected: 7 tests PASS (the original happy-path + 6 new). The Task 1 implementation already covers every branch these tests exercise; if any test fails, the implementation has a bug — diagnose and fix in `screens.py`, then re-run. Do NOT change the test code to make it pass.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_screens.py
git commit -m "test(screens): add drop scenarios for low ADV, sparse history, missing data, empty cov window"
```

---

## Task 3: Pipeline — snapshot pin (Determinism 2a)

**Files:**
- Modify: `backend/app/engine/pipeline.py`

- [ ] **Step 1: Replace the date computations**

In `backend/app/engine/pipeline.py`, locate the block at lines 43-46:

```python
    tickers = [s["ticker"] for s in stocks]
    end_date = datetime.utcnow().strftime("%Y-%m-%d")
    start_date_3y = (datetime.utcnow() - timedelta(days=3 * 365)).strftime("%Y-%m-%d")
    cov_cutoff = (datetime.utcnow() - timedelta(days=2 * 365)).date()
```

Replace with:

```python
    tickers = [s["ticker"] for s in stocks]
    snapshot_date = (datetime.utcnow() - timedelta(days=1)).date()
    end_date = snapshot_date.isoformat()
    start_date_3y = (snapshot_date - timedelta(days=3 * 365)).isoformat()
    cov_cutoff = snapshot_date - timedelta(days=2 * 365)
```

This anchors all three date computations to a single `snapshot_date` (yesterday UTC), making same-day reruns hit identical fully-settled bars.

- [ ] **Step 2: Verify the existing integration test still passes**

```bash
docker compose run --rm -e TEST_DATABASE_URL='postgresql://portfolio:portfolio@db:5432/portfolio_builder_test' backend pytest tests/test_pipeline_integration.py -v
```

Expected: PASS. The mocked `yf.download` ignores the date arguments, so behavior is unchanged.

- [ ] **Step 3: Commit**

```bash
git add backend/app/engine/pipeline.py
git commit -m "feat(pipeline): pin data snapshot to yesterday UTC for reproducibility"
```

---

## Task 4: Pipeline — wire in the quality screen

**Files:**
- Modify: `backend/app/engine/pipeline.py`

- [ ] **Step 1: Add the import**

At the top of `backend/app/engine/pipeline.py`, alongside the other engine imports:

```python
from app.engine.screens import apply_quality_screen
```

- [ ] **Step 2: Replace the manual extraction loop with the screen call**

In `backend/app/engine/pipeline.py`, locate the block (currently lines 57-73):

```python
    price_data = {}
    for ticker in tickers:
        try:
            if isinstance(batch.columns, pd.MultiIndex):
                close = batch[ticker]["Close"]
            else:
                close = batch["Close"]
            close = close.dropna()
            close = close[close.index.date >= cov_cutoff]
            if len(close) > 0:
                price_data[ticker] = close
        except (KeyError, ValueError):
            continue

    valid_tickers = [t for t in tickers if t in price_data]
    if len(valid_tickers) < 5:
        return {"error": "Not enough historical data available."}
```

Replace with:

```python
    price_data, dropped_by_screen = apply_quality_screen(batch, tickers, cov_cutoff)
    valid_tickers = list(price_data.keys())
    if len(valid_tickers) < 5:
        return {"error": "Not enough historical data available."}
```

The screen always returns a MultiIndex-shape batch in production (yfinance `group_by="ticker"` with multi-ticker download). The single-ticker branch from the old loop (`batch["Close"]` when columns are not MultiIndex) was a defensive code path that the screen does not need to support — `select_universe` is guaranteed to produce at least 5 tickers (already enforced upstream at line 40).

- [ ] **Step 3: Run the integration test**

```bash
docker compose run --rm -e TEST_DATABASE_URL='postgresql://portfolio:portfolio@db:5432/portfolio_builder_test' backend pytest tests/test_pipeline_integration.py -v
```

Expected: PASS. The synthetic batch in the existing integration test uses `Volume = 1_000_000.0` and `Close ≈ 100.0` → `ADV ≈ $100M` >> `$10M`, full history, so no tickers should be dropped by the screen.

- [ ] **Step 4: Commit**

```bash
git add backend/app/engine/pipeline.py
git commit -m "feat(pipeline): wire in apply_quality_screen, derive valid_tickers from screened set"
```

---

## Task 5: Simulator — deterministic seed (Determinism 2b)

**Files:**
- Modify: `backend/app/engine/simulator.py`
- Modify: `backend/tests/test_engine/test_simulator.py`

- [ ] **Step 1: Write the failing deterministic-seed test**

Append to `backend/tests/test_engine/test_simulator.py`:

```python
def test_monte_carlo_is_deterministic_for_same_inputs():
    weights = np.array([0.25, 0.25, 0.25, 0.25])
    expected_returns = np.array([0.10, 0.12, 0.08, 0.11])
    cov_matrix = np.eye(4) * 0.04

    a = run_monte_carlo(
        weights=weights, expected_returns=expected_returns, cov_matrix=cov_matrix,
        initial_value=10_000.0, horizon_years=3.0, n_simulations=1_000,
    )
    b = run_monte_carlo(
        weights=weights, expected_returns=expected_returns, cov_matrix=cov_matrix,
        initial_value=10_000.0, horizon_years=3.0, n_simulations=1_000,
    )

    assert a["percentile_10"] == b["percentile_10"]
    assert a["percentile_50"] == b["percentile_50"]
    assert a["percentile_90"] == b["percentile_90"]


def test_monte_carlo_changes_with_inputs():
    weights = np.array([0.25, 0.25, 0.25, 0.25])
    expected_returns = np.array([0.10, 0.12, 0.08, 0.11])
    cov_matrix = np.eye(4) * 0.04

    a = run_monte_carlo(
        weights=weights, expected_returns=expected_returns, cov_matrix=cov_matrix,
        initial_value=10_000.0, horizon_years=3.0, n_simulations=1_000,
    )
    b = run_monte_carlo(
        weights=weights, expected_returns=expected_returns, cov_matrix=cov_matrix,
        initial_value=20_000.0, horizon_years=3.0, n_simulations=1_000,
    )

    assert a["percentile_50"] != b["percentile_50"]
```

- [ ] **Step 2: Run the new tests and verify they fail**

```bash
docker compose run --rm -e TEST_DATABASE_URL='postgresql://portfolio:portfolio@db:5432/portfolio_builder_test' backend pytest tests/test_engine/test_simulator.py::test_monte_carlo_is_deterministic_for_same_inputs -v
```

Expected: FAIL — `np.random.seed(None)` produces different draws on each call, so `percentile_10/50/90` will differ.

- [ ] **Step 3: Replace the simulator implementation**

Replace the entire contents of `backend/app/engine/simulator.py` with:

```python
import hashlib
import json

import numpy as np


def _deterministic_seed(
    weights,
    expected_returns,
    cov_matrix,
    initial_value: float,
    horizon_years: float,
    n_simulations: int,
) -> int:
    """Derive a 32-bit seed from the simulator's actual inputs.

    Assumes weights, expected_returns, and cov_matrix are aligned to a
    single, deterministically ordered ticker set. The pipeline guarantees
    this via its post-estimate_covariance realignment step
    (see covariance-shrinkage Task 4).
    """
    payload = json.dumps(
        {
            "weights":          [round(float(w), 6) for w in weights],
            "expected_returns": [round(float(r), 6) for r in expected_returns],
            "cov_matrix":       [[round(float(c), 8) for c in row] for row in cov_matrix],
            "initial_value":    round(float(initial_value), 4),
            "horizon_years":    round(float(horizon_years), 4),
            "n_simulations":    int(n_simulations),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return int.from_bytes(hashlib.sha256(payload.encode()).digest()[:4], "big")


def run_monte_carlo(
    weights: np.ndarray,
    expected_returns: np.ndarray,
    cov_matrix: np.ndarray,
    initial_value: float,
    horizon_years: float,
    n_simulations: int = 10_000,
) -> dict:
    trading_days = int(252 * horizon_years)
    port_annual_return = float(weights @ expected_returns)
    port_annual_vol = float(np.sqrt(weights @ cov_matrix @ weights))
    daily_return = port_annual_return / 252
    daily_vol = port_annual_vol / np.sqrt(252)

    seed = _deterministic_seed(
        weights, expected_returns, cov_matrix,
        initial_value, horizon_years, n_simulations,
    )
    rng = np.random.default_rng(seed=seed)
    random_returns = rng.normal(daily_return, daily_vol, (n_simulations, trading_days))
    cumulative = np.cumprod(1 + random_returns, axis=1)
    final_values = initial_value * cumulative[:, -1]

    p10 = float(np.percentile(final_values, 10))
    p50 = float(np.percentile(final_values, 50))
    p90 = float(np.percentile(final_values, 90))

    return_low = (p10 / initial_value) ** (1 / horizon_years) - 1
    return_high = (p90 / initial_value) ** (1 / horizon_years) - 1

    return {
        "percentile_10": round(p10, 2),
        "percentile_50": round(p50, 2),
        "percentile_90": round(p90, 2),
        "return_low": round(return_low, 4),
        "return_high": round(return_high, 4),
        "initial_value": initial_value,
        "horizon_years": horizon_years,
        "n_simulations": n_simulations,
    }
```

- [ ] **Step 4: Run the full simulator test file**

```bash
docker compose run --rm -e TEST_DATABASE_URL='postgresql://portfolio:portfolio@db:5432/portfolio_builder_test' backend pytest tests/test_engine/test_simulator.py -v
```

Expected: 4 tests PASS — the 2 original (`test_monte_carlo_output_shape`, `test_monte_carlo_reasonable_values`) and the 2 new ones. The original tests don't assert specific numeric values that would be affected by seeding, so they continue to pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/engine/simulator.py backend/tests/test_engine/test_simulator.py
git commit -m "feat(simulator): seed Monte Carlo deterministically from input hash"
```

---

## Task 6: Optimizer cleanup

**Files:**
- Modify: `backend/app/engine/optimizer.py`
- Modify: `backend/app/engine/pipeline.py`
- Modify: `backend/tests/test_engine/test_optimizer.py`

- [ ] **Step 1: Update the optimizer constants and signature**

Replace the entire contents of `backend/app/engine/optimizer.py` with:

```python
import numpy as np
import cvxpy as cp

RISK_VOLATILITY_CAP = {
    1: 0.08,
    2: 0.12,
    3: 0.18,
    4: 0.25,
    5: 0.35,
}

MAX_SINGLE_WEIGHT = 0.20

# Enforced indirectly via MAX_SINGLE_WEIGHT: any feasible solution must
# spread across at least 1 / MAX_SINGLE_WEIGHT = 5 names. CVXPY does not
# support the cardinality constraint that would express this directly.
MIN_STOCKS = 5

MIN_WEIGHT_THRESHOLD = 0.02


def optimize_portfolio(
    tickers: list[str],
    expected_returns: np.ndarray,
    cov_matrix: np.ndarray,
    risk_level: int,
) -> dict:
    n = len(tickers)
    max_vol = RISK_VOLATILITY_CAP.get(risk_level, 0.18)

    weights = cp.Variable(n)
    ret = expected_returns @ weights
    risk = cp.quad_form(weights, cov_matrix)

    constraints = [
        cp.sum(weights) == 1,
        weights >= 0,
        weights <= MAX_SINGLE_WEIGHT,
    ]
    constraints.append(risk <= max_vol ** 2)

    objective = cp.Maximize(ret)
    problem = cp.Problem(objective, constraints)

    try:
        problem.solve(solver=cp.SCS)
    except cp.SolverError:
        problem.solve(solver=cp.ECOS)

    if problem.status not in ("optimal", "optimal_inaccurate"):
        equal_w = np.ones(n) / n
        return {
            "weights": {t: round(float(w), 4) for t, w in zip(tickers, equal_w)},
            "portfolio_return": float(expected_returns @ equal_w),
            "portfolio_volatility": float(np.sqrt(equal_w @ cov_matrix @ equal_w)),
            "status": "fallback_equal_weight",
        }

    raw_weights = weights.value
    clean_weights = np.where(raw_weights < MIN_WEIGHT_THRESHOLD, 0, raw_weights)
    if clean_weights.sum() > 0:
        clean_weights = clean_weights / clean_weights.sum()
    else:
        clean_weights = np.ones(n) / n

    port_return = float(expected_returns @ clean_weights)
    port_vol = float(np.sqrt(clean_weights @ cov_matrix @ clean_weights))

    return {
        "weights": {t: round(float(w), 4) for t, w in zip(tickers, clean_weights)},
        "portfolio_return": round(port_return, 4),
        "portfolio_volatility": round(port_vol, 4),
        "status": "optimal",
    }
```

Key changes from the previous version:
- `MAX_SINGLE_WEIGHT = 0.20` (was `0.30`).
- `MIN_STOCKS = 5` retained with explanatory comment.
- `target_return` removed from the function signature.

- [ ] **Step 2: Update the pipeline to stop passing `target_return`**

In `backend/app/engine/pipeline.py`, locate the call to `optimize_portfolio` (currently around line 96-102):

```python
    # Stage 3: Markowitz Optimization
    opt_result = optimize_portfolio(
        tickers=valid_tickers,
        expected_returns=valid_returns,
        cov_matrix=cov_matrix,
        risk_level=risk_level,
        target_return=target_return,
    )
```

Replace with:

```python
    # Stage 3: Markowitz Optimization
    # Note: profile.target_return is collected but not currently consumed
    # by the optimizer. Field is preserved on the profile for a future
    # "target return" feature.
    opt_result = optimize_portfolio(
        tickers=valid_tickers,
        expected_returns=valid_returns,
        cov_matrix=cov_matrix,
        risk_level=risk_level,
    )
```

The `target_return` parameter remains on `generate_portfolio`'s signature (line 26) — the API still passes it, the pipeline just no longer forwards it to the optimizer.

- [ ] **Step 3: Update the existing optimizer tests**

In `backend/tests/test_engine/test_optimizer.py`, three tests currently pass `target_return=...` to `optimize_portfolio`. Remove that argument from each:

Replace the file's contents with:

```python
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
```

Changes from the previous version:
- All three `target_return=...` arguments removed.
- `test_basic_optimization` tightens its weight bound from `<= 0.30` to `<= 0.20 + 1e-6` (the small tolerance absorbs solver-precision noise around the cap).

- [ ] **Step 4: Run the optimizer tests and verify all 3 pass**

```bash
docker compose run --rm -e TEST_DATABASE_URL='postgresql://portfolio:portfolio@db:5432/portfolio_builder_test' backend pytest tests/test_engine/test_optimizer.py -v
```

Expected: 3 tests PASS, including `test_minimum_stocks_constraint` which was previously red on `main` with `4 >= 5`.

If `test_minimum_stocks_constraint` is still red (post-cleanup count below 5 because `MIN_WEIGHT_THRESHOLD = 0.02` zeroed a position), apply the spec 3a follow-up: in `backend/app/engine/optimizer.py`, change `MIN_WEIGHT_THRESHOLD = 0.02` to `MIN_WEIGHT_THRESHOLD = 0.01`, then re-run. Document the change in the commit message.

- [ ] **Step 5: Run the full pipeline integration test to verify the optimizer-call change didn't break anything**

```bash
docker compose run --rm -e TEST_DATABASE_URL='postgresql://portfolio:portfolio@db:5432/portfolio_builder_test' backend pytest tests/test_pipeline_integration.py -v
```

Expected: PASS. The existing integration test asserts `h["allocation_pct"] <= 30.01` which is still satisfied by the new `0.20` cap (0.20 × 100 = 20 ≤ 30.01). Task 7 will tighten this assertion.

- [ ] **Step 6: Commit**

```bash
git add backend/app/engine/optimizer.py backend/app/engine/pipeline.py backend/tests/test_engine/test_optimizer.py
git commit -m "feat(optimizer): lower MAX_SINGLE_WEIGHT to 0.20, drop dead target_return param"
```

If `MIN_WEIGHT_THRESHOLD` was lowered in Step 4, use this commit message instead:
```bash
git commit -m "feat(optimizer): lower MAX_SINGLE_WEIGHT to 0.20, MIN_WEIGHT_THRESHOLD to 0.01, drop dead target_return param"
```

---

## Task 7: Integration tests — determinism + screen-drop downstream

**Files:**
- Modify: `backend/tests/test_pipeline_integration.py`

- [ ] **Step 1: Tighten the existing weight bound and add three new tests**

Open `backend/tests/test_pipeline_integration.py`. The file currently contains:
- `_fake_yf_download` (helper)
- `_fake_universe` (helper)
- `test_pipeline_end_to_end_includes_covariance_metadata` (existing test)

Make TWO changes:

**1.** In the existing `test_pipeline_end_to_end_includes_covariance_metadata`, replace:
```python
    # MAX_SINGLE_WEIGHT in optimizer.py is 0.30 → 30% as a pct
    assert all(h["allocation_pct"] <= 30.01 for h in result["holdings"])
```
with:
```python
    # MAX_SINGLE_WEIGHT in optimizer.py is 0.20 → 20% as a pct
    assert all(h["allocation_pct"] <= 20.01 for h in result["holdings"])
```

**2.** Append three new tests at the end of the file:

```python
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
```

- [ ] **Step 2: Run the pipeline integration tests**

```bash
docker compose run --rm -e TEST_DATABASE_URL='postgresql://portfolio:portfolio@db:5432/portfolio_builder_test' backend pytest tests/test_pipeline_integration.py -v
```

Expected: 4 tests PASS — the existing `test_pipeline_end_to_end_includes_covariance_metadata` plus the 3 new tests.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_pipeline_integration.py
git commit -m "test(pipeline): add reproducibility, sensitivity, and screen-drop assertions"
```

---

## Task 8: Full-suite verification

**Files:** none (verification only).

- [ ] **Step 1: Run the full backend test suite**

```bash
docker compose run --rm -e TEST_DATABASE_URL='postgresql://portfolio:portfolio@db:5432/portfolio_builder_test' backend pytest -v
```

Expected pass set:
- `tests/test_screens.py` — 7/7 (Tasks 1-2)
- `tests/test_engine/test_simulator.py` — 4/4 (2 original + 2 from Task 5)
- `tests/test_engine/test_optimizer.py` — 3/3 including `test_minimum_stocks_constraint` (previously red, expected green per Task 6)
- `tests/test_pipeline_integration.py` — 4/4 (1 original + 3 from Task 7)
- `tests/test_risk.py` — 8/8 (unchanged from P1)
- `tests/test_portfolios.py` — 6/6 (unchanged from P1)
- `tests/test_auth.py`, `tests/test_profiles.py` — unchanged

Expected pre-existing failures (unrelated to this branch, must remain unchanged):
- `tests/test_engine/test_pipeline.py::test_generate_portfolio` — stale `fetch_stock_info` mock target.
- `tests/test_engine/test_predictor.py::test_predict_returns` — same stale mock target.
- `tests/test_engine/test_universe.py::test_filter_by_country_us` — stale `_get_sector_tickers` mock target.
- `tests/test_engine/test_universe.py::test_include_exclude_tickers` — same.
- `tests/test_engine/test_universe.py::test_filter_by_sector` — same.

If any of these 5 unrelated failures changes pass/fail status compared to `main` → investigate before proceeding.

- [ ] **Step 2: Confirm the screen log line fires on integration**

```bash
docker compose run --rm -e TEST_DATABASE_URL='postgresql://portfolio:portfolio@db:5432/portfolio_builder_test' backend pytest tests/test_pipeline_integration.py::test_pipeline_drops_low_volume_ticker_from_holdings -v --log-cli-level=INFO
```

Look for a log line of the form:
```
quality_screen kept=9 dropped_low_adv=1 dropped_sparse=0 dropped_recent=0 dropped_missing=0
```

Capture the exact line in the verification report. If it does not appear, check pytest's log capture configuration and re-run.

- [ ] **Step 3: Document post-deploy operator checks**

The following are explicitly post-deploy operator checks, not pre-merge gates. They require a live stack with real yfinance data:

- Run the integration test twice on a real-data path with the same profile and the same UTC day, confirm the resulting portfolios match.
- After deployment, generate one portfolio with the same profile that was used to test on `main` and on `feat/covariance-shrinkage`; confirm `risk_score` and the holdings list look qualitatively similar (lower MAX_SINGLE_WEIGHT will spread allocations more, which is expected).

These are noted in the verification report; the human user runs them after merge + deploy.

---

## Out of scope (do NOT add to this plan)

- Country filter fix (P2b — separate spec).
- Caching the trained predictor model.
- Implementing `target_return` as a real optimizer constraint.
- DB persistence of the price snapshot.
- Migrations of any kind.
- Frontend changes.
- Any other optimizer / simulator / predictor changes (turnover penalty, transaction costs, Student-t, regime modeling, Black-Litterman, etc.).
- Fixing the 5 pre-existing failures in `tests/test_engine/{test_pipeline,test_predictor,test_universe}.py`.
