# Portfolio Construction Upgrade — HRP + MVO Hybrid (Design Spec)

**Date:** 2026-04-18
**Status:** Approved, ready for implementation plan
**Phase:** P3 (portfolio construction)

## Goal

Replace the current "MVO-only" portfolio construction step with a hybrid:
**Hierarchical Risk Parity (HRP)** as the default weighting method, with
mean-variance optimization (MVO) used as a controlled fallback. HRP produces
more stable, diversified weights when expected-return estimates are noisy
(which they are: our predictor is a single XGBoost model with limited
features). MVO remains the safety net when HRP overshoots the user's risk
cap or fails entirely.

## Architecture

### 1 — `hrp.py` module (new)

Create `backend/app/engine/hrp.py` exposing one function:

```python
def hrp_weights(cov_matrix: np.ndarray, tickers: list[str]) -> dict[str, float]:
    """Lopez de Prado 2016 Hierarchical Risk Parity.

    Returns weights summing to 1.0, all strictly positive, keyed by ticker.
    Raises ValueError on zero-variance assets or n < 2.
    """
```

**Algorithm** (standard HRP):

1. Convert covariance → correlation:
   `corr = cov / sqrt(diag(cov) ⊗ diag(cov))`.
2. **Non-positive / near-zero variance guard** (fail fast):
   `if any(np.diag(cov) < 1e-12): raise ValueError("HRP cannot handle non-positive or near-zero variance assets")`.
   The check rejects any asset whose variance is below `1e-12`, which covers
   exact zero, negative (numerical artifact), and degenerate near-zero cases
   that would produce NaN/Inf when normalizing into correlation. The
   pipeline is responsible for screening these out before calling HRP;
   if one slips through, we want a loud failure, not a silent NaN.
3. Distance metric: `d_ij = sqrt(0.5 * (1 - corr_ij))`.
4. Hierarchical clustering: `scipy.cluster.hierarchy.linkage(squareform(d), method="single")`.
   Single linkage with a fixed distance matrix is **deterministic** — no
   tie-breaking randomness. We add an explicit unit test for byte-identical
   weights across two calls with the same input.
5. Quasi-diagonalization: reorder tickers by the linkage tree's leaf order.
6. Recursive bisection: split the ordered list in half, allocate weight
   between the two halves inversely proportional to each half's
   inverse-variance-weighted cluster variance, recurse.
7. Return `{ticker: weight}` in the **original `tickers` order** as passed
   into the function. Even though the algorithm internally reorders assets
   for clustering and recursive bisection (the "quasi-diagonal" sequence),
   that reordering is purely an implementation detail — at the API
   boundary, callers see weights keyed by the same tickers in the same
   order they supplied. Downstream code can iterate `valid_tickers` and
   look up weights without translation.

**No post-cleanup threshold.** HRP weights stay as computed. A hard cutoff
(like the MVO `MIN_WEIGHT_THRESHOLD = 0.02`) would remove legitimate small
allocations and unintentionally reintroduce concentration, defeating the
point of HRP. All weights are strictly positive by construction.

**Tests** (`backend/tests/test_hrp.py`, new):
- Weights sum to 1.0 within 1e-9.
- All weights strictly positive.
- Determinism: two calls with identical input return byte-identical weights.
- Zero-variance asset → `ValueError`.
- `n < 2` → `ValueError`.
- Sanity: on a 4-asset cov where assets 0/1 are highly correlated and 2/3
  are uncorrelated to them, the weight on each high-correlation cluster is
  roughly half the total, not concentrated on the lowest-variance single
  asset.

### 2 — Pipeline orchestration ([backend/app/engine/pipeline.py](backend/app/engine/pipeline.py))

Insert HRP/MVO decision logic between `estimate_covariance` and
`run_monte_carlo`. The optimizer is **not** removed; it sits behind the
fallback branches.

**Units in this block:** `target_vol` (read from `RISK_VOLATILITY_CAP`) and
`hrp_candidate_vol` are both **annualized**, so the cap comparison is
apples-to-apples. `portfolio_vol` (the value handed downstream to the
existing `risk_score = portfolio_volatility * 100` formula) stays
**daily** to preserve the existing MVO-path behavior. See §3a for the full
rationale; this block is where the mismatch matters.

```python
HRP_VOL_TOLERANCE = 1.10  # Product decision, not a mathematical truth —
                          # accept HRP if it's within 10% of the user's risk
                          # cap. Tune after observing real-world drift.

# After estimate_covariance, before run_monte_carlo:
weighting_method: str
optimizer_status: str | None = None
hrp_candidate_vol: float | None = None
hrp_error: str | None = None

target_vol = RISK_VOLATILITY_CAP[risk_level]

try:
    hrp_w = hrp_weights(cov_matrix, valid_tickers)
    hrp_arr = np.array([hrp_w[t] for t in valid_tickers])
    hrp_vol_daily = float(np.sqrt(hrp_arr @ cov_matrix @ hrp_arr))
    hrp_candidate_vol = hrp_vol_daily * np.sqrt(252)  # annualized

    if hrp_candidate_vol <= target_vol * HRP_VOL_TOLERANCE:
        weights_array = hrp_arr
        weighting_method = "hrp"
        portfolio_vol = hrp_vol_daily  # daily, to match the existing
                                       # risk_score formula in MVO path
        portfolio_return = float(hrp_arr @ valid_returns)
    else:
        # HRP overshot the risk cap — fall back to MVO with predictor μ.
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
    # HRP raised before producing a valid candidate (zero-variance, n < 2).
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

# Defensive sanity check — HRP has no post-processing, MVO is renormalized
# inside the optimizer. Either way the weights must sum to 1 before sim.
assert abs(weights_array.sum() - 1.0) < 1e-8, "weights must sum to 1 before sim"

logger.info("portfolio_construction", extra={
    "hrp_candidate_vol": hrp_candidate_vol,  # annualized; None iff HRP raised
    "hrp_error": hrp_error,                  # str on HRP error path, else None
    "target_vol": target_vol,                # annualized cap from RISK_VOLATILITY_CAP
    "tolerance": HRP_VOL_TOLERANCE,
    "weighting_method": weighting_method,    # final outcome (user-facing)
    "optimizer_status": optimizer_status,    # internal MVO status, None when HRP wins
})
```

The Monte Carlo simulator then runs on the chosen `weights_array`.
`risk_score` is computed from the **final** weights (`portfolio_vol`),
never from the HRP candidate when MVO wins.

### 3 — Result metadata semantics

| Final state | `weighting_method` | `optimizer_status` | `hrp_candidate_vol` |
|---|---|---|---|
| HRP wins | `"hrp"` | `None` | populated |
| HRP overshoots cap → MVO optimal | `"mvo_risk_cap"` | `"optimal"` | populated |
| HRP overshoots cap → MVO equal-weight | `"fallback_equal_weight"` | `"fallback_equal_weight"` | populated |
| HRP raised → MVO optimal | `"mvo_fallback_hrp_error"` | `"optimal"` | `None` |
| HRP raised → MVO equal-weight | `"fallback_equal_weight"` | `"fallback_equal_weight"` | `None` |

**Two semantic distinctions to preserve across API, docs, and tests:**

1. **`hrp_candidate_vol = None` means specifically that HRP failed before
   producing a valid candidate weight vector.** It must never be `None` in
   a path where HRP weights existed and were evaluated against the cap. If
   you see `None`, HRP raised — full stop.
2. **`weighting_method` reflects the final portfolio construction outcome
   shown to the user/operator.** `optimizer_status` reflects the internal
   optimizer outcome. In the equal-weight fallback paths these collapse to
   the same string (`"fallback_equal_weight"`) on purpose: equal-weight is
   the dominant signal for the UI, regardless of why we entered MVO.

**`hrp_candidate_vol` semantics (always):**
- **Annualized** (daily vol × √252). This is the meaningful unit for users
  and for comparing against `RISK_VOLATILITY_CAP` (whose values 0.08–0.35
  read as annualized vol caps).
- Computed from the **raw HRP candidate weights**, before any fallback.

### 3a — Units note (intentional asymmetry, not a bug)

`hrp_candidate_vol` is annualized. `risk_score` (existing field) is reported
in **daily** units × 100, because the existing optimizer returns
`portfolio_volatility` from a daily covariance and the pipeline does
`risk_score = portfolio_volatility * 100`. We deliberately **do not** change
`risk_score` semantics in this spec — that's a separate, broader fix.

Practical consequences:
- `hrp_candidate_vol` and `risk_score` are not directly comparable.
- The internal HRP-vs-cap comparison annualizes `hrp_vol_daily` so that a
  ~1.2% daily vol is correctly checked against an 18% (annualized) cap.
  If we compared in daily units, the cap would be effectively non-binding
  and the fallback would never fire.
- The MVO path's `port_vol` continues to be daily; this is pre-existing
  behavior, preserved to avoid scope creep.

A future phase should annualize `risk_score` consistently across both
paths. See "Out of scope".

### 4 — API exposure ([backend/app/schemas/portfolio.py](backend/app/schemas/portfolio.py))

Add three optional fields to `PortfolioResponse`:

```python
weighting_method: str | None = None
optimizer_status: str | None = None
hrp_candidate_vol: float | None = None
```

All three are populated by the engine and passed through unchanged in
[backend/app/api/portfolios.py](backend/app/api/portfolios.py), matching
the existing pattern for `covariance_method` and `shrinkage_intensity`.

### 5 — Methodology page ([frontend/src/methodology/MethodologyPage.tsx](frontend/src/methodology/MethodologyPage.tsx))

Add one paragraph after the existing shrinkage paragraph:

> *Weighting.* By default we use **Hierarchical Risk Parity (HRP)** — a
> clustering-based method that spreads risk across groups of stocks that
> tend to move together. HRP tends to produce more stable, diversified
> portfolios than classical mean-variance optimization, especially when
> expected-return estimates are noisy. We measure the resulting portfolio
> volatility against your risk profile's cap; if HRP overshoots by more
> than 10%, we fall back to mean-variance optimization with the
> predictor's expected returns as a tighter risk control.

## Integration tests

Extend [backend/tests/test_pipeline_integration.py](backend/tests/test_pipeline_integration.py):

- **HRP wins path:** assert `weighting_method == "hrp"`,
  `optimizer_status is None`, `hrp_candidate_vol is not None`,
  `0 < hrp_candidate_vol <= target_vol * 1.10`. (Do not assert
  `hrp_candidate_vol == risk_score` — they are in different units; see §3a.)
- **MVO risk-cap fallback:** construct synthetic returns with high
  cross-correlation and high variance so HRP overshoots the cap. Assert
  `weighting_method == "mvo_risk_cap"`, `optimizer_status == "optimal"`,
  `hrp_candidate_vol > target_vol * 1.10`.
- **HRP error fallback:** monkeypatch `hrp_weights` to raise. Assert
  `weighting_method == "mvo_fallback_hrp_error"`, `hrp_candidate_vol is None`,
  `hrp_error` is logged, **and** `optimizer_status` is populated with one
  of `"optimal"` or `"fallback_equal_weight"` depending on the mocked
  optimizer outcome — `optimizer_status` must never be `None` on this
  fallback path. (Run two variants of the test: one where the mocked MVO
  succeeds → `optimizer_status == "optimal"`; one where it falls back →
  `optimizer_status == "fallback_equal_weight"` and `weighting_method`
  collapses to `"fallback_equal_weight"`.)
- **Reproducibility:** existing `test_pipeline_is_reproducible` continues
  to pass — HRP determinism plus simulator seeding means two identical
  calls produce byte-identical results.

## Out of scope (this iteration)

- **Black-Litterman / posterior blending** of HRP weights with predictor
  expected returns. HRP currently ignores the predictor entirely; MVO uses
  it. This asymmetry is intentional for v1.
- **Correlation distance variants.** Sticking with classical
  `sqrt(0.5 * (1 - corr))` and single linkage. No experimentation with
  average/ward linkage or alternate distance metrics.
- **Sector / country constraints inside HRP.** HRP has no constraint
  mechanism in this iteration; constraints would force a switch back to MVO.
- **Per-asset weight caps for HRP.** No `MAX_SINGLE_WEIGHT` enforcement on
  HRP output. The hierarchical bisection already prevents extreme
  concentration in practice; a hard cap would distort the algorithm's
  natural risk-budgeting.
- **Tunable `HRP_VOL_TOLERANCE` via API/config.** Hardcoded constant in v1;
  revisit only after observing real-world behavior.
- **A/B comparison endpoint** returning both HRP and MVO side-by-side.
  Useful diagnostic, but not in this iteration.
- **Annualizing `risk_score`** across both HRP and MVO paths. Today
  `risk_score = port_vol * 100` where `port_vol` is daily. This makes the
  reported "risk score" a small number (~1–2%) that doesn't match users'
  intuition for portfolio volatility, and creates the unit asymmetry
  documented in §3a. Fixing requires touching the existing MVO path and
  the frontend's interpretation of the field — out of scope here.
