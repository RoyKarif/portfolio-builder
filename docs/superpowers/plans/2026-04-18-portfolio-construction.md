# Portfolio Construction Upgrade — HRP + MVO Hybrid Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Hierarchical Risk Parity (HRP) as the default portfolio weighting method, with MVO retained as a controlled fallback when HRP overshoots the user's risk cap or fails on degenerate input.

**Architecture:** A new pure-function module `app/engine/hrp.py` implements HRP (correlation distance → single-linkage clustering → recursive bisection). The pipeline orchestrates HRP-first with a try/except + risk-cap check that routes to MVO on either failure mode. The covariance matrix is already annualized inside `estimate_covariance` (`daily_cov × 252` at [backend/app/engine/risk.py:71](backend/app/engine/risk.py#L71)), so all vol calculations are in annualized units throughout. New API fields surface the construction outcome and HRP candidate vol; the methodology page gets one explanatory paragraph.

**Tech Stack:** Python 3.11+, NumPy, SciPy (`scipy.cluster.hierarchy.linkage`, `scipy.spatial.distance.squareform`), Pydantic v2, FastAPI, pytest, React/TypeScript.

**Reference spec:** [docs/superpowers/specs/2026-04-18-portfolio-construction-design.md](docs/superpowers/specs/2026-04-18-portfolio-construction-design.md)

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `backend/app/engine/hrp.py` | **Create** | Pure-function HRP implementation: `hrp_weights(cov_matrix, tickers) -> dict[str, float]` |
| `backend/tests/test_hrp.py` | **Create** | Unit tests for the HRP module (shape, determinism, guards, sanity) |
| `backend/app/engine/pipeline.py` | **Modify** | Insert HRP/MVO orchestration block between `estimate_covariance` and `run_monte_carlo`; emit new metadata fields |
| `backend/app/schemas/portfolio.py` | **Modify** | Add `weighting_method`, `optimizer_status`, `hrp_candidate_vol` fields to `PortfolioResponse` |
| `backend/app/api/portfolios.py` | **Modify** | Pass the three new engine result fields through the generate endpoint |
| `backend/tests/test_pipeline_integration.py` | **Modify** | Add HRP-wins, MVO risk-cap fallback, and HRP-error fallback tests |
| `frontend/src/methodology/MethodologyPage.tsx` | **Modify** | Add one HRP paragraph after the existing shrinkage paragraph |

---

## Task 1: HRP module with TDD

**Files:**
- Create: `backend/app/engine/hrp.py`
- Create: `backend/tests/test_hrp.py`

The HRP module is a pure function with no dependencies on the rest of the engine. We build it bottom-up via TDD: shape tests first, then guards, then determinism, then a clustering sanity check.

### Step 1: Write the shape tests

Create `backend/tests/test_hrp.py` with the first two tests:

```python
import numpy as np
import pytest

from app.engine.hrp import hrp_weights


def test_weights_sum_to_one():
    # 4 uncorrelated assets with equal variance -> equal-weight expected
    cov = np.eye(4) * 0.04  # 20% annualized vol each
    tickers = ["A", "B", "C", "D"]

    weights = hrp_weights(cov, tickers)

    assert set(weights.keys()) == set(tickers)
    assert abs(sum(weights.values()) - 1.0) < 1e-9


def test_all_weights_strictly_positive():
    cov = np.eye(4) * 0.04
    tickers = ["A", "B", "C", "D"]

    weights = hrp_weights(cov, tickers)

    assert all(w > 0 for w in weights.values())
```

### Step 2: Run shape tests to verify they fail

Run: `cd backend && pytest tests/test_hrp.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.engine.hrp'`

### Step 3: Implement minimal HRP module

Create `backend/app/engine/hrp.py`:

```python
import numpy as np
from scipy.cluster.hierarchy import linkage
from scipy.spatial.distance import squareform


def hrp_weights(cov_matrix: np.ndarray, tickers: list[str]) -> dict[str, float]:
    """Lopez de Prado 2016 Hierarchical Risk Parity.

    Returns weights summing to 1.0, all strictly positive, keyed by ticker
    in the original input order.

    Raises:
        ValueError: when fewer than 2 tickers are supplied, or when any asset
        has non-positive or near-zero variance (diag < 1e-12).
    """
    n = len(tickers)
    if n < 2:
        raise ValueError("HRP requires at least 2 assets")

    cov = np.asarray(cov_matrix, dtype=float)
    if cov.shape != (n, n):
        raise ValueError(f"cov_matrix shape {cov.shape} does not match {n} tickers")

    variances = np.diag(cov)
    if np.any(variances < 1e-12):
        raise ValueError("HRP cannot handle non-positive or near-zero variance assets")

    # 1. Covariance -> correlation
    std = np.sqrt(variances)
    corr = cov / np.outer(std, std)
    # Numerical guard: clamp into [-1, 1] before distance conversion
    corr = np.clip(corr, -1.0, 1.0)

    # 2. Distance metric and condensed form for scipy
    dist = np.sqrt(0.5 * (1.0 - corr))
    np.fill_diagonal(dist, 0.0)
    condensed = squareform(dist, checks=False)

    # 3. Hierarchical clustering (single linkage; deterministic for fixed input)
    link = linkage(condensed, method="single")

    # 4. Quasi-diagonalization: leaf order from the dendrogram
    sort_ix = _quasi_diag(link, n)

    # 5. Recursive bisection over the sorted index list
    raw = _recursive_bisection(cov, sort_ix)

    # 6. Return in caller's original ticker order
    return {tickers[i]: float(raw[i]) for i in range(n)}


def _quasi_diag(link: np.ndarray, n_leaves: int) -> list[int]:
    """Reorder leaves so that similar items sit next to each other.

    `link` is the (n-1) x 4 linkage matrix from scipy. Internal node ids
    are >= n_leaves; leaves are ids 0..n_leaves-1.
    """
    link = link.astype(int)
    # Start with the root cluster (last row of the linkage matrix)
    ordered = [link[-1, 0], link[-1, 1]]
    while max(ordered) >= n_leaves:
        new_ordered = []
        for cluster_id in ordered:
            if cluster_id < n_leaves:
                new_ordered.append(cluster_id)
            else:
                row = link[cluster_id - n_leaves]
                new_ordered.append(int(row[0]))
                new_ordered.append(int(row[1]))
        ordered = new_ordered
    return ordered


def _inverse_variance_weights(cov_slice: np.ndarray) -> np.ndarray:
    """Inverse-variance weights (the HRP base case for a single cluster)."""
    inv = 1.0 / np.diag(cov_slice)
    return inv / inv.sum()


def _cluster_variance(cov: np.ndarray, indices: list[int]) -> float:
    """Variance of a cluster under inverse-variance weighting."""
    sub = cov[np.ix_(indices, indices)]
    w = _inverse_variance_weights(sub)
    return float(w @ sub @ w)


def _recursive_bisection(cov: np.ndarray, sort_ix: list[int]) -> np.ndarray:
    """Allocate weight across the quasi-diagonal-ordered list via top-down
    splits, sizing each side inversely to its cluster variance."""
    n = cov.shape[0]
    weights = np.ones(n)
    work = [list(sort_ix)]
    while work:
        clusters = []
        for cluster in work:
            if len(cluster) <= 1:
                continue
            mid = len(cluster) // 2
            left, right = cluster[:mid], cluster[mid:]
            var_left = _cluster_variance(cov, left)
            var_right = _cluster_variance(cov, right)
            alpha = 1.0 - var_left / (var_left + var_right)
            for i in left:
                weights[i] *= alpha
            for i in right:
                weights[i] *= 1.0 - alpha
            clusters.append(left)
            clusters.append(right)
        work = clusters
    return weights
```

### Step 4: Run shape tests to verify they pass

Run: `cd backend && pytest tests/test_hrp.py -v`
Expected: PASS for both `test_weights_sum_to_one` and `test_all_weights_strictly_positive`.

### Step 5: Write the guard tests

Append to `backend/tests/test_hrp.py`:

```python
def test_zero_variance_asset_raises():
    cov = np.eye(4) * 0.04
    cov[0, 0] = 0.0  # degenerate asset
    cov[0, 1:] = 0.0
    cov[1:, 0] = 0.0
    tickers = ["A", "B", "C", "D"]

    with pytest.raises(ValueError, match="non-positive or near-zero variance"):
        hrp_weights(cov, tickers)


def test_near_zero_variance_asset_raises():
    cov = np.eye(4) * 0.04
    cov[0, 0] = 1e-15  # below the 1e-12 threshold
    tickers = ["A", "B", "C", "D"]

    with pytest.raises(ValueError, match="non-positive or near-zero variance"):
        hrp_weights(cov, tickers)


def test_too_few_assets_raises():
    cov = np.array([[0.04]])
    tickers = ["A"]

    with pytest.raises(ValueError, match="at least 2 assets"):
        hrp_weights(cov, tickers)


def test_shape_mismatch_raises():
    cov = np.eye(3) * 0.04
    tickers = ["A", "B"]  # length 2 but cov is 3x3

    with pytest.raises(ValueError, match="does not match"):
        hrp_weights(cov, tickers)
```

### Step 6: Run guard tests to verify they pass

Run: `cd backend && pytest tests/test_hrp.py -v`
Expected: PASS for all 6 tests so far. The guards already exist in the implementation from Step 3.

### Step 7: Write the determinism test

Append to `backend/tests/test_hrp.py`:

```python
def test_determinism_byte_identical_weights():
    rng = np.random.default_rng(seed=42)
    raw = rng.standard_normal((300, 8))
    cov = np.cov(raw, rowvar=False)
    tickers = [f"T{i}" for i in range(8)]

    w1 = hrp_weights(cov, tickers)
    w2 = hrp_weights(cov, tickers)

    # Exact equality, not approximate — single linkage is deterministic
    assert w1 == w2
    for t in tickers:
        assert w1[t] == w2[t]
```

### Step 8: Run determinism test to verify it passes

Run: `cd backend && pytest tests/test_hrp.py::test_determinism_byte_identical_weights -v`
Expected: PASS.

### Step 9: Write the clustering sanity test

Append to `backend/tests/test_hrp.py`:

```python
def test_correlated_assets_share_cluster_weight():
    """Assets 0/1 are highly correlated, 2/3 are nearly independent of them.
    HRP should allocate roughly half the total weight to the {0,1} cluster
    and roughly half to the {2,3} cluster, NOT pile everything on the
    lowest-variance single asset."""
    # Build a covariance matrix with a clear two-cluster block structure
    cov = np.array([
        [0.04, 0.038, 0.001, 0.001],
        [0.038, 0.04, 0.001, 0.001],
        [0.001, 0.001, 0.04, 0.001],
        [0.001, 0.001, 0.001, 0.04],
    ])
    tickers = ["A0", "A1", "B0", "B1"]

    weights = hrp_weights(cov, tickers)

    cluster_a = weights["A0"] + weights["A1"]
    cluster_b = weights["B0"] + weights["B1"]

    # Each cluster should hold roughly half the total weight (within 15pp).
    # The exact split depends on cluster variance ratios; we only check
    # that neither cluster gets crushed.
    assert 0.35 < cluster_a < 0.65, f"cluster A weight {cluster_a:.3f} not balanced"
    assert 0.35 < cluster_b < 0.65, f"cluster B weight {cluster_b:.3f} not balanced"

    # And no single asset should receive an extreme allocation
    assert all(w < 0.6 for w in weights.values())
```

### Step 10: Run sanity test to verify it passes

Run: `cd backend && pytest tests/test_hrp.py -v`
Expected: PASS for all 8 tests.

### Step 11: Commit

```bash
cd backend && pytest tests/test_hrp.py -v && cd ..
git add backend/app/engine/hrp.py backend/tests/test_hrp.py
git commit -m "feat(engine): add Hierarchical Risk Parity module

Implements Lopez de Prado 2016 HRP: correlation distance + single-linkage
clustering + recursive bisection. Pure function, no engine dependencies.

Guards: ValueError on n<2, non-positive/near-zero variance, and
shape mismatch between cov_matrix and tickers list. Returns weights
keyed by the caller's original ticker order, preserving call-site
indexing.

Tested for sum-to-1, strictly positive weights, byte-identical
determinism across calls, all guard paths, and clustering sanity on
a synthetic two-cluster covariance."
```

---

## Task 2: Pipeline orchestration

**Files:**
- Modify: `backend/app/engine/pipeline.py`

Wire HRP into the pipeline. HRP runs first; on success, compare its
candidate vol to the user's annualized risk cap (`RISK_VOLATILITY_CAP[risk_level]`).
If HRP exceeds the cap by more than `HRP_VOL_TOLERANCE`, fall back to MVO. If
HRP raises (zero-variance, n<2), also fall back to MVO. Emit three new
metadata fields and a structured log line.

### Step 1: Add imports and the HRP_VOL_TOLERANCE constant

In `backend/app/engine/pipeline.py`, replace the import block at the top with:

```python
import logging
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import yfinance as yf

from app.engine.universe import select_universe
from app.engine.predictor import predict_returns
from app.engine.optimizer import optimize_portfolio, RISK_VOLATILITY_CAP
from app.engine.simulator import run_monte_carlo
from app.engine.risk import estimate_covariance
from app.engine.screens import apply_quality_screen
from app.engine.hrp import hrp_weights

logger = logging.getLogger(__name__)

HORIZON_YEARS = {
    "6m": 0.5,
    "1-3y": 2.0,
    "3-5y": 4.0,
    "5y+": 7.0,
}

# Product decision, not a mathematical truth — accept HRP if it's within
# 10% of the user's risk cap. Tune after observing real-world drift.
HRP_VOL_TOLERANCE = 1.10
```

Do not remove any existing imports beyond what this block already supplies.

### Step 2: Replace the optimizer call with the HRP/MVO orchestration block

In `backend/app/engine/pipeline.py`, locate the section currently
beginning with `# Stage 3: Markowitz Optimization` and ending just
before `# Stage 4: Monte Carlo Simulation`. Replace that whole block
(lines that currently call `optimize_portfolio` and assign
`opt_result`) with:

```python
    # Stage 3: Portfolio construction (HRP default, MVO fallback)
    target_vol = RISK_VOLATILITY_CAP[risk_level]
    weighting_method: str
    optimizer_status: str | None = None
    hrp_candidate_vol: float | None = None
    hrp_error: str | None = None

    try:
        hrp_w = hrp_weights(cov_matrix, valid_tickers)
        hrp_arr = np.array([hrp_w[t] for t in valid_tickers])
        # cov_matrix is annualized inside estimate_covariance, so
        # sqrt(w @ cov_matrix @ w) is annualized vol directly.
        hrp_candidate_vol = float(np.sqrt(hrp_arr @ cov_matrix @ hrp_arr))

        if hrp_candidate_vol <= target_vol * HRP_VOL_TOLERANCE:
            weights_array = hrp_arr
            weighting_method = "hrp"
            portfolio_vol = hrp_candidate_vol
            portfolio_return = float(hrp_arr @ valid_returns)
        else:
            opt_result = optimize_portfolio(
                tickers=valid_tickers,
                expected_returns=valid_returns,
                cov_matrix=cov_matrix,
                risk_level=risk_level,
            )
            weights_array = np.array([opt_result["weights"].get(t, 0) for t in valid_tickers])
            optimizer_status = opt_result["status"]
            weighting_method = (
                "fallback_equal_weight"
                if optimizer_status == "fallback_equal_weight"
                else "mvo_risk_cap"
            )
            portfolio_vol = opt_result["portfolio_volatility"]
            portfolio_return = opt_result["portfolio_return"]
    except ValueError as e:
        hrp_error = str(e)
        opt_result = optimize_portfolio(
            tickers=valid_tickers,
            expected_returns=valid_returns,
            cov_matrix=cov_matrix,
            risk_level=risk_level,
        )
        weights_array = np.array([opt_result["weights"].get(t, 0) for t in valid_tickers])
        optimizer_status = opt_result["status"]
        weighting_method = (
            "fallback_equal_weight"
            if optimizer_status == "fallback_equal_weight"
            else "mvo_fallback_hrp_error"
        )
        portfolio_vol = opt_result["portfolio_volatility"]
        portfolio_return = opt_result["portfolio_return"]

    assert abs(weights_array.sum() - 1.0) < 1e-8, "weights must sum to 1 before sim"

    logger.info(
        "portfolio_construction",
        extra={
            "hrp_candidate_vol": hrp_candidate_vol,
            "hrp_error": hrp_error,
            "target_vol": target_vol,
            "tolerance": HRP_VOL_TOLERANCE,
            "weighting_method": weighting_method,
            "optimizer_status": optimizer_status,
        },
    )
```

### Step 3: Replace the holdings-construction and return blocks

After Stage 3, the existing pipeline rebuilds `holdings`, `risk_score`,
and the result dict from `opt_result`. Update the post-Stage-4 section
to read from the unified locals (`weights_array`, `portfolio_vol`,
`portfolio_return`) and to emit the three new metadata fields.

Locate the `run_monte_carlo` call. The existing line
`weights_array = np.array([opt_result["weights"].get(t, 0) for t in valid_tickers])`
no longer exists (it was absorbed into the orchestration block above).
The Monte Carlo call now reads:

```python
    # Stage 4: Monte Carlo Simulation
    horizon_years = HORIZON_YEARS.get(investment_horizon, 3.0)

    sim_result = run_monte_carlo(
        weights=weights_array,
        expected_returns=valid_returns,
        cov_matrix=cov_matrix,
        initial_value=available_amount,
        horizon_years=horizon_years,
    )

    holdings = []
    for i, ticker in enumerate(valid_tickers):
        w = float(weights_array[i])
        if w < 0.01:
            continue
        stock = ticker_to_stock[ticker]
        holdings.append({
            "ticker": ticker,
            "company_name": stock["company_name"],
            "sector": stock["sector"],
            "allocation_pct": round(w * 100, 2),
            "expected_return": round(stock["expected_return"] * 100, 2),
        })

    return {
        "holdings": holdings,
        "risk_score": round(portfolio_vol * 100, 2),
        "expected_return_low": round(sim_result["return_low"] * 100, 2),
        "expected_return_high": round(sim_result["return_high"] * 100, 2),
        "portfolio_return": round(portfolio_return * 100, 2),
        "simulation": sim_result,
        "status": optimizer_status if optimizer_status is not None else "hrp",
        "covariance_method": cov_meta["method"],
        "shrinkage_intensity": round(shrinkage, 4),
        "weighting_method": weighting_method,
        "optimizer_status": optimizer_status,
        "hrp_candidate_vol": hrp_candidate_vol,
    }
```

Notes:
- `status` (the existing field) keeps the legacy contract: it's the
  optimizer's status when MVO ran, or the literal string `"hrp"` when HRP
  won. This preserves backward compatibility with anything that read
  `status` previously.
- `weighting_method`, `optimizer_status`, and `hrp_candidate_vol` are
  the new fields the API will surface.

### Step 4: Run the existing pipeline integration tests

Run: `cd backend && pytest tests/test_pipeline_integration.py -v`
Expected: PASS for all 4 existing tests. They don't assert on the new
fields, but they do assert on `total_alloc ≈ 100`, no allocation
> 20.01, and reproducibility — all of which still hold under HRP for the
synthetic data the tests use (10 random-walk tickers with similar vol).

If `test_pipeline_end_to_end_includes_covariance_metadata`'s
`<= 20.01` assertion fails on HRP weights, that's a real signal —
investigate whether the synthetic data is producing concentration. Do
not weaken the assertion to make it pass.

### Step 5: Commit

```bash
cd backend && pytest tests/test_pipeline_integration.py tests/test_hrp.py -v && cd ..
git add backend/app/engine/pipeline.py
git commit -m "feat(pipeline): add HRP/MVO hybrid weighting

Default to HRP. Fall back to MVO when (a) the HRP candidate's annualized
vol exceeds the user's risk cap by more than HRP_VOL_TOLERANCE (1.10x),
or (b) HRP raises ValueError on degenerate input.

Emits three new metadata fields:
- weighting_method: final outcome shown to user/operator
- optimizer_status: internal MVO status (None when HRP wins)
- hrp_candidate_vol: annualized vol of the raw HRP candidate (None iff HRP raised)

Logs a structured portfolio_construction entry with all routing decisions.

The existing 'status' field is preserved for backward compatibility
('hrp' when HRP wins, otherwise the optimizer's status)."
```

---

## Task 3: Add new fields to PortfolioResponse

**Files:**
- Modify: `backend/app/schemas/portfolio.py`

### Step 1: Add the three optional fields

Edit `backend/app/schemas/portfolio.py`. Replace the `PortfolioResponse`
class (currently lines 23–36) with:

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
    weighting_method: str | None = None
    optimizer_status: str | None = None
    hrp_candidate_vol: float | None = None

    model_config = {"from_attributes": True}
```

### Step 2: Verify the schema imports cleanly

Run: `cd backend && python -c "from app.schemas.portfolio import PortfolioResponse; print(PortfolioResponse.model_fields.keys())"`
Expected output (order may vary):
```
dict_keys(['id', 'status', 'risk_score', 'expected_return_low', 'expected_return_high', 'portfolio_return', 'total_value', 'holdings', 'simulation', 'covariance_method', 'shrinkage_intensity', 'weighting_method', 'optimizer_status', 'hrp_candidate_vol'])
```

### Step 3: Commit

```bash
git add backend/app/schemas/portfolio.py
git commit -m "feat(schema): add HRP construction fields to PortfolioResponse

weighting_method, optimizer_status, hrp_candidate_vol — all optional
to preserve backward compatibility with portfolios stored before HRP
was introduced."
```

---

## Task 4: Pass new fields through the API

**Files:**
- Modify: `backend/app/api/portfolios.py`

The generate endpoint already passes `covariance_method` and
`shrinkage_intensity` from the engine result through to
`PortfolioResponse`. Extend the same pattern for the three new fields.

### Step 1: Update the generate endpoint return

In `backend/app/api/portfolios.py`, locate the `return PortfolioResponse(...)`
block at the end of the `generate` function (currently lines 76–88).
Replace it with:

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
        weighting_method=result.get("weighting_method"),
        optimizer_status=result.get("optimizer_status"),
        hrp_candidate_vol=result.get("hrp_candidate_vol"),
    )
```

The `get_portfolio` endpoint (lines 111–150) reads from the database,
which doesn't yet store these fields. Leave it unchanged — it will
return `None` for the three new fields, which is correct for portfolios
generated before this change. (Persisting them is out of scope for this
plan; see the spec's "Out of scope" section regarding extended history.)

### Step 2: Smoke-test the import

Run: `cd backend && python -c "from app.api.portfolios import router; print([r.path for r in router.routes])"`
Expected: prints a list of route paths including `/portfolios/generate/{profile_id}`.
A successful import confirms no syntax / type errors were introduced.

### Step 3: Commit

```bash
git add backend/app/api/portfolios.py
git commit -m "feat(api): surface HRP construction fields on /portfolios/generate

The generate endpoint passes weighting_method, optimizer_status, and
hrp_candidate_vol through from the engine result. The get-by-id
endpoint returns None for these (not persisted in the DB this iteration)."
```

---

## Task 5: Integration tests for HRP and fallback paths

**Files:**
- Modify: `backend/tests/test_pipeline_integration.py`

Add three new tests covering the three reachable construction outcomes
that the existing tests don't exercise: HRP wins, MVO fallback on
risk-cap overshoot, and MVO fallback on HRP error (with two
sub-variants for the optimizer's outcome).

### Step 1: Add the HRP-wins test

Append to `backend/tests/test_pipeline_integration.py`:

```python
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

    # When HRP wins, hrp_candidate_vol equals risk_score / 100 within tolerance.
    assert abs(result["hrp_candidate_vol"] - result["risk_score"] / 100) < 1e-6
```

### Step 2: Add the MVO risk-cap fallback test

Append to `backend/tests/test_pipeline_integration.py`:

```python
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
```

### Step 3: Add the HRP-error fallback test (both sub-variants)

Append to `backend/tests/test_pipeline_integration.py`:

```python
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
```

### Step 4: Run the full integration test suite

Run: `cd backend && pytest tests/test_pipeline_integration.py -v`
Expected: PASS for all tests — the 4 existing tests plus the 4 new ones.

If `test_pipeline_mvo_fallback_on_risk_cap_overshoot` doesn't trigger the
expected fallback (i.e. HRP candidate vol stays under the cap × 1.10),
increase the daily vol of the `common` driver in
`_fake_yf_download_high_vol` until it does. The test exists to exercise
the fallback path; tune the synthetic data, not the assertion.

### Step 5: Commit

```bash
cd backend && pytest tests/ -v && cd ..
git add backend/tests/test_pipeline_integration.py
git commit -m "test(pipeline): cover HRP wins + both MVO fallback paths

Adds four integration tests exercising the new construction outcomes:
- HRP wins on benign synthetic data (asserts metadata + risk_score equality)
- MVO risk-cap fallback on high-correlation high-vol synthetic data
- HRP-error fallback with mocked optimizer succeeding (mvo_fallback_hrp_error)
- HRP-error fallback with mocked optimizer falling back (fallback_equal_weight)

The fallback-path tests pin down the metadata contract from §3 of the spec."
```

---

## Task 6: Methodology page paragraph

**Files:**
- Modify: `frontend/src/methodology/MethodologyPage.tsx`

### Step 1: Add the HRP paragraph

In `frontend/src/methodology/MethodologyPage.tsx`, locate the
`#optimization` section. The last paragraph in that section currently
ends with "...This is a well-established technique in professional
portfolio construction."

Add a new paragraph immediately after that one, before the section's
closing `</section>` tag:

```tsx
        <p className="text-gray-700 mb-3">
          By default we use a method called <strong>Hierarchical Risk Parity (HRP)</strong> — a
          clustering-based approach that spreads risk across groups of stocks that tend to
          move together. HRP tends to produce more stable, diversified portfolios than
          classical mean-variance optimization, especially when the per-stock return
          estimates are noisy. We measure the resulting portfolio volatility against your
          risk profile's cap; if HRP overshoots by more than 10%, we fall back to
          mean-variance optimization with the per-stock return estimates as a tighter
          risk control.
        </p>
```

### Step 2: Visual check

Run: `cd frontend && npm run dev` (in the background, then open the browser to `/methodology`).
Expected: the optimization section now has 4 paragraphs (the existing 3 + the new HRP paragraph). The page renders without errors.

If you can't run a browser, at minimum run `cd frontend && npm run build` and confirm it compiles cleanly.

### Step 3: Commit

```bash
git add frontend/src/methodology/MethodologyPage.tsx
git commit -m "docs(methodology): explain HRP weighting and MVO fallback

Adds one paragraph to the Balancing the Portfolio section, in plain
English, describing the default HRP method and the risk-cap fallback
to MVO. Matches the wording approved in the design spec."
```

---

## Final verification

After all tasks complete, run the full backend test suite once more:

```bash
cd backend && pytest tests/ -v
```

Expected: every test passes, including the 4 pre-existing pipeline tests, the 8 new HRP unit tests, and the 4 new pipeline-orchestration tests.

If any pre-existing test fails on HRP behavior, inspect — do not patch the test. The synthetic data in those tests was tuned for MVO; HRP should still satisfy the assertions (sum-to-100, max-allocation-≤-20, reproducibility, low-volume drop), but if it doesn't, the assertion may be revealing a real behavior change worth surfacing.
