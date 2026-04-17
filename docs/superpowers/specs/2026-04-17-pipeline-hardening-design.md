# Pipeline Hardening (P2a) — Design Spec

**Date:** 2026-04-17
**Status:** Approved by user, ready for implementation planning
**Roadmap context:** P2a of the "smarter math" roadmap. Bundles three independent quality fixes into a single backend-only release: liquidity/quality screen on the universe, determinism pass for reproducibility, and small optimizer cleanups. P1 (covariance shrinkage) shipped on `feat/covariance-shrinkage`. Country support (P2b) is deferred to its own spec because a real fix likely requires a non-yfinance data source.

## Problem

The diagnostic identified five weak links in the post-P1 pipeline. Three are addressable with self-contained backend changes that share the same code paths and ship cleanly together:

1. **Universe quality leaks.** `select_universe` returns `yf.Sector(...).top_companies.head(15)` with no liquidity, sparseness, or quality screen. Low-ADV or recently-IPO'd names slip through, get noisy return predictions, and are weighted up by mean-variance optimization.
2. **Hidden non-determinism.** `np.random.seed(None)` in the simulator and `end_date = utcnow().strftime(...)` in the pipeline mean two requests for the same profile minutes apart can produce different portfolios. Users cannot compare or replicate, support becomes painful, and there is no way to verify behavior over time.
3. **Optimizer bugs.** `MIN_STOCKS = 5` is defined but never enforced (CVXPY does not support the cardinality constraint that would express it directly). `target_return` appears in `optimize_portfolio`'s signature but is never referenced in the objective or constraints. `MAX_SINGLE_WEIGHT = 0.30` admits 4-stock concentrations dressed as diversified.

## Goals

- Filter the candidate universe by liquidity (30-day average dollar volume) and history completeness, using only the price/volume batch already downloaded — no new API calls.
- Make the engine deterministic for a fixed UTC day: same profile generated on the same UTC day → same portfolio (subject to the upstream data being stable, which we explicitly anchor by pinning the data snapshot).
- Make the optimizer's stated breadth target (≥5 holdings) actually hold under the math, drop the dead `target_return` parameter, and make the relationship between `MIN_STOCKS` and `MAX_SINGLE_WEIGHT` self-documenting in code.

## Non-Goals / Out of Scope

The following are explicitly deferred and MUST NOT be changed as part of this work:

- **Country filter fix.** The current sector-universe path returns whatever `yf.Sector(...).top_companies` yields and applies the country-to-exchanges mapping only to user-supplied `include_tickers`. This spec preserves that known-broken behavior; a real fix requires a separate spec, likely with a non-yfinance data source per country.
- **Caching the trained predictor model.** The predictor still re-trains XGBoost per request. This is deferred as a performance improvement, **not** a correctness blocker — XGBoost is already seeded with `random_state=42`, so its output is deterministic given identical input data.
- **Implementing `target_return` as a real optimizer constraint.** Field remains on the profile and API request; it is silently ignored by the optimizer until a future feature gives it real meaning.
- **Storing the price snapshot in the DB.** Reproducibility across days is not in scope.
- **Schema migrations of any kind.** No DB changes.
- **Frontend changes.** Pure backend.
- **Other optimizer changes** (turnover penalty, transaction costs, factor caps).
- **Other simulator changes** (Student-t, block bootstrap, regime modeling).
- **Other predictor changes** (Black-Litterman shrinkage, cross-sectional model).

---

## Design

### 1. Quality screen module: `backend/app/engine/screens.py`

A single public function:

```python
def apply_quality_screen(
    batch: pd.DataFrame,
    tickers: list[str],
    cov_cutoff: date,
) -> tuple[dict[str, pd.Series], list[dict]]:
    ...
```

**Inputs:**
- `batch`: the multi-ticker yfinance DataFrame already downloaded by `pipeline.py`. MultiIndex columns of shape `(ticker, field)` where `field` includes at least `Close` and `Volume`.
- `tickers`: the candidate ticker list, in the order produced by `select_universe`. Order is preserved into the surviving set.
- `cov_cutoff`: the start of the covariance estimation window (today: 2 years before `snapshot_date`). Defines the window over which `history_fraction` is measured.

**Outputs:**
- `price_data`: ordered `dict[str, pd.Series]` of surviving tickers → their `Close` series within the cov window. Order matches the original `tickers` argument with rejected tickers removed.
- `dropped`: `list[dict]` with one entry per rejected ticker, each containing:
  - `ticker: str`
  - `reasons: list[str]` — one or more of `"low_adv"`, `"sparse_history"`, `"insufficient_recent_data"`, `"missing_data"`.
  - `adv_30d_usd: float | None` — measured value, `None` only when ADV could not be computed (then `"insufficient_recent_data"` is in `reasons`).
  - `history_fraction: float` — measured fraction in `[0.0, 1.0]`.

**Module-level constants:**
```python
MIN_ADV_USD = 10_000_000          # 30-day average dollar volume floor
MIN_HISTORY_FRACTION = 0.95       # fraction of trading days in the cov window with non-null usable data
ADV_LOOKBACK_DAYS = 30            # trading days for ADV computation
MIN_RECENT_OBSERVATIONS = 10      # minimum non-null rows in last ADV_LOOKBACK_DAYS for ADV to be considered measurable
```

`MIN_ADV_USD = $10M` is a sensible default for the current US-centric universe. When P2b lands and the universe becomes truly multi-country, this threshold likely needs market-specific tuning (TLV, LSE, FRA, etc. all have meaningfully different liquidity baselines). Out of scope here; noted for the next phase.

**Algorithm (per ticker, in `tickers` order):**

1. Extract `close_series` and `volume_series` from `batch[ticker]["Close"]` and `batch[ticker]["Volume"]`. If either is missing or extraction raises, record `reasons=["missing_data"]`, `adv_30d_usd=None`, `history_fraction=0.0`, and continue.
2. Build a usable per-day frame `usable = DataFrame({"close": close, "volume": volume}).dropna(how="any")`. Both columns must be present for a row to count. Filter to `usable.index.date >= cov_cutoff`.
3. **History fraction:** the denominator is the count of distinct trading dates present in the **batch's union date index restricted to the covariance window** — i.e. the dates from `batch.index` filtered to `date >= cov_cutoff`. This is the empirical trading calendar that yfinance returned for the cov window, so holidays and market-specific closures don't penalize. The numerator is the count of rows in `usable` within the same window. `history_fraction = numerator / denominator`. **Edge case:** if `denominator == 0` (batch is empty, or no dates fall within the cov window), treat as a drop with `reasons=["sparse_history"]`, `history_fraction=0.0`, and skip ADV computation.
4. **ADV:** take the **calendar tail of the cov-window panel first** (the trailing `ADV_LOOKBACK_DAYS` rows of the pre-NaN panel within the cov window), then drop NaN within that slice. The `MIN_RECENT_OBSERVATIONS` check counts non-null rows inside that calendar slice — this is what makes `"insufficient_recent_data"` actually catch tickers whose recent history has gone stale (the spec's prior wording of "tail after NaN filtering" was misleading because dropna-then-tail would silently reach further back into history when the tail was sparse, never tripping the recency check). If fewer than `MIN_RECENT_OBSERVATIONS` non-null rows survive in the calendar slice, set `adv_30d_usd = None` and add `"insufficient_recent_data"` to reasons. Otherwise `adv_30d_usd = (recent["close"] * recent["volume"]).mean()` over those non-null rows.
5. **Decision:**
   - If `adv_30d_usd is None`: ticker drops (the `"insufficient_recent_data"` reason is already in the list).
   - Else if `adv_30d_usd < MIN_ADV_USD`: add `"low_adv"` to reasons.
   - If `history_fraction < MIN_HISTORY_FRACTION`: add `"sparse_history"` to reasons.
   - If `reasons` is non-empty after the above: ticker is dropped (record in `dropped`); the close series is **not** added to `price_data`.
   - Otherwise the ticker survives: `price_data[ticker] = usable["close"]`.

**Logging:**
- One `INFO` line per call: `quality_screen kept=<K> dropped_low_adv=<L> dropped_sparse=<S> dropped_recent=<R> dropped_missing=<M>`.
- One `DEBUG` line per dropped ticker with the full reasons + measured values.

**Downstream contract:** the `valid_tickers` list constructed in `pipeline.py` after `apply_quality_screen` MUST be derived from `price_data.keys()`. All ticker-ordered structures downstream — return predictions, expected-return arrays, covariance inputs, optimizer outputs, the final holdings list — derive from this screened set. The pipeline's existing post-`estimate_covariance` realignment (covariance-shrinkage Task 4) continues to handle the case where the covariance estimator drops additional tickers.

### 2. Determinism

#### 2a. Snapshot pin

In `pipeline.py:43-44`, replace:
```python
end_date = datetime.utcnow().strftime("%Y-%m-%d")
start_date_3y = (datetime.utcnow() - timedelta(days=3 * 365)).strftime("%Y-%m-%d")
```
with:
```python
snapshot_date = (datetime.utcnow() - timedelta(days=1)).date()
end_date = snapshot_date.isoformat()
start_date_3y = (snapshot_date - timedelta(days=3 * 365)).isoformat()
cov_cutoff = snapshot_date - timedelta(days=2 * 365)   # replaces the existing line that used utcnow().date()
```

yfinance's `end` parameter is exclusive, so anchoring to yesterday explicitly removes any ambiguity about whether today's partial bar leaks in. Same-day reruns hit identical, fully-settled bars.

**Trade-off:** predictions become up to one day stale relative to today's intraday quote. For a multi-year-horizon simulator this is irrelevant.

#### 2b. Deterministic simulator seed

In `simulator.py`, replace the current `np.random.seed(None)` + global `np.random.normal(...)` pattern with a per-call `np.random.default_rng(seed)` whose seed is derived from a stable hash of every input that influences the simulation output.

```python
import hashlib
import json

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

    Uses canonical JSON (sort_keys, fixed separators, fixed float
    precision) instead of repr() so the seed contract is easy to inspect
    and stable across Python versions.
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
```

In `run_monte_carlo`:
```python
seed = _deterministic_seed(weights, expected_returns, cov_matrix, initial_value, horizon_years, n_simulations)
rng = np.random.default_rng(seed=seed)
random_returns = rng.normal(daily_return, daily_vol, (n_simulations, trading_days))
```

The function signature of `run_monte_carlo` does **not** change — it already accepts every input the seed function needs.

**Why hash inputs rather than thread `profile_id` from the API:** the simulator does not — and should not — know about profiles. Its output is a function of its inputs; hashing them keeps the abstraction boundary clean and avoids passing identifiers through three layers.

**Why `hashlib.sha256` rather than Python `hash()`:** Python's `hash()` is salt-randomized per process for strings and tuples and is not stable across runs.

**Why include `cov_matrix` and `n_simulations`:** the simulator's `daily_vol` is derived from `cov_matrix @ weights`, and `trading_days` is derived from `horizon_years`. Hashing the underlying inputs covers the derived quantities. Omitting any of them would make the seed insensitive to a real change in the simulation problem.

#### 2c. End-to-end reproducibility — what the change does and does not promise

After 2a + 2b, **the data snapshot and the Monte Carlo stage are deterministic** for a fixed UTC day. End-to-end reproducibility (same profile + same UTC day → same portfolio bytes) additionally relies on:

- The predictor (XGBoost with `random_state=42`) being deterministic for fixed input data — true today.
- The optimizer (CVXPY → SCS/ECOS) being deterministic for a fixed problem — true for these solvers.

We are not formally proving end-to-end reproducibility in this spec; we are removing the two known sources of non-determinism. If a future change introduces randomness elsewhere (a new ML model, a randomized solver, intraday data source), this guarantee weakens at that point and the burden falls on that change.

### 3. Optimizer cleanup

In `backend/app/engine/optimizer.py`:

#### 3a. Lower `MAX_SINGLE_WEIGHT` from 0.30 to 0.20

```python
MAX_SINGLE_WEIGHT = 0.20    # was 0.30
```

**Effect:** the optimizer cannot place more than 20% in any single name, so any feasible solution has at least 5 non-zero pre-cleanup positions (`1 / 0.20 = 5`).

**Important caveat:** the existing post-optimization cleanup logic in `optimize_portfolio` zeroes any weight below `MIN_WEIGHT_THRESHOLD = 0.02`. If the optimizer produces, say, 4 positions at 0.20 plus 5 tiny positions at 0.01 each, those tiny positions get zeroed and the final portfolio has 4 holdings — defeating the intent. The implementation **must verify post-cleanup** that the breadth target survives. If empirical runs show the cleanup threshold pushing portfolios below 5 holdings, the right follow-up is to lower `MIN_WEIGHT_THRESHOLD` (e.g. to 0.01) so the small allocations survive. This is an explicitly anticipated adjustment within this task — not a separate spec.

#### 3b. Drop the `target_return` parameter

`target_return` appears in `optimize_portfolio`'s signature but is never referenced inside the function. Remove it from the signature and update the call site in `pipeline.py` to stop passing it.

The field stays on `InvestmentProfile` (DB model), `ProfileRequest` (API schema), and any UI form that collects it. The pipeline still reads `profile.target_return`; it just does not pass it anywhere meaningful. Add this comment in `pipeline.py` next to where the optimizer is called:

```python
# Note: profile.target_return is collected but not currently consumed by
# the optimizer. Field is preserved on the profile for a future
# "target return" feature.
```

**Why not remove the field entirely:** that would require a schema migration and an API deprecation cycle. Out of scope here.

#### 3c. Self-documenting `MIN_STOCKS`

Keep the constant, with a comment that makes the indirect enforcement explicit:

```python
# Enforced indirectly via MAX_SINGLE_WEIGHT: any feasible solution must
# spread across at least 1 / MAX_SINGLE_WEIGHT = 5 names. CVXPY does not
# support the cardinality constraint that would express this directly.
MIN_STOCKS = 5
```

This documents the intent and binds the two constants together so a future maintainer cannot quietly drift them apart.

#### 3d. Pre-existing optimizer test

`backend/tests/test_engine/test_optimizer.py::test_minimum_stocks_constraint` is currently red on `main` with assertion `4 >= 5`. Lowering `MAX_SINGLE_WEIGHT` to 0.20 is **expected** to turn it green naturally. **Verify explicitly** as part of this task's verification step — do not assume. If it remains red after the constant change, follow the 3a caveat (lower `MIN_WEIGHT_THRESHOLD`) and re-run.

The other 5 pre-existing failures in `tests/test_engine/` (stale mock targets in test_pipeline.py, test_predictor.py, test_universe.py) are out of scope.

---

## Acceptance Criteria

The implementation is complete when ALL of the following hold:

1. **Quality screen unit tests pass** in a new `backend/tests/test_screens.py`:
   - Happy path: 10 well-shaped synthetic tickers all survive.
   - Drop on low ADV: ticker with `(close × volume).tail(30).mean() < 10M` is dropped with reason `"low_adv"`.
   - Drop on sparse history: ticker with <95% of trading days populated is dropped with reason `"sparse_history"`.
   - Drop on insufficient recent data: ticker with <10 non-null rows in last 30 is dropped with reason `"insufficient_recent_data"` and `adv_30d_usd is None`.
   - Drop on missing data: ticker absent from the batch yields `reasons=["missing_data"]`.
   - Drop on empty cov window: a batch whose date index has zero rows in the cov window (or a ticker whose entire usable series falls before `cov_cutoff`) is dropped with `reasons=["sparse_history"]` and `history_fraction == 0.0`.
   - Order preservation: surviving tickers in `price_data` appear in the order they were in the input `tickers` list.

2. **Determinism integration test passes** in `backend/tests/test_pipeline_integration.py` (extension):
   - Running `generate_portfolio` twice with the same inputs produces results that match within a small float tolerance (e.g. `abs(diff) < 1e-9` for `risk_score`, `simulation.percentile_10/50/90`, and per-holding `allocation_pct`). Tickers and ordering must match exactly. Float-bit equality is not required (cross-platform / cross-numpy-version reproducibility is not a goal).
   - Running with a meaningfully changed input (e.g. `available_amount` = 10_000 vs 20_000) produces a `simulation.percentile_50` that differs by more than the tolerance.
   - **Quality-screen downstream contract:** at least one of the integration tests must inject a fake universe where one or more tickers will be dropped by the screen (e.g. low-volume `Volume = 1.0`), then assert that those tickers do not appear in the engine result's `holdings`. This guards against any future regression that bypasses or partially applies the screen.

3. **Optimizer constants updated and verified:**
   - `MAX_SINGLE_WEIGHT == 0.20`.
   - `target_return` no longer in `optimize_portfolio`'s signature.
   - `MIN_STOCKS = 5` retained with the explanatory comment.
   - `tests/test_engine/test_optimizer.py::test_minimum_stocks_constraint` is green when run against the branch (verified explicitly, not assumed). If the post-cleanup count drops below 5, `MIN_WEIGHT_THRESHOLD` is lowered as part of the same task until the test passes.

4. **Pipeline integration:**
   - `pipeline.py` uses `snapshot_date` as the data anchor.
   - `pipeline.py` calls `apply_quality_screen` and derives `valid_tickers` from `price_data.keys()`.
   - `pipeline.py` no longer passes `target_return` to the optimizer.

5. **No regressions:** `tests/test_risk.py` (8/8), `tests/test_pipeline_integration.py` (1/1 + new determinism cases), `tests/test_portfolios.py` (6/6) all pass. The 5 unrelated pre-existing failures in `tests/test_engine/` outside `test_optimizer.py::test_minimum_stocks_constraint` are explicitly out of scope and may remain red.

---

## Files affected (preview)

- **Create:** `backend/app/engine/screens.py` — `apply_quality_screen` and constants.
- **Create:** `backend/tests/test_screens.py` — unit tests (the six cases listed in Acceptance Criteria #1).
- **Modify:** `backend/app/engine/pipeline.py` — **the central integration point for this work:** snapshot pinning (2a), `apply_quality_screen` usage replacing the manual extraction loop (1), deriving `valid_tickers` from screened output, preserving the existing covariance-shrinkage ticker realignment (Task 4 of the prior plan), and updating the optimizer call to drop `target_return` (3b).
- **Modify:** `backend/app/engine/simulator.py` — add `_deterministic_seed`, replace `np.random.seed(None)` + `np.random.normal(...)` with `np.random.default_rng(seed).normal(...)`.
- **Modify:** `backend/app/engine/optimizer.py` — lower `MAX_SINGLE_WEIGHT`, drop `target_return` from signature, add `MIN_STOCKS` documentation comment.
- **Modify:** `backend/tests/test_pipeline_integration.py` — add the two determinism cases from Acceptance Criteria #2.
- **Verify (no edits expected):** `backend/tests/test_engine/test_optimizer.py::test_minimum_stocks_constraint` — currently red on `main`; expected to go green after `MAX_SINGLE_WEIGHT` change. Verify empirically (per Acceptance Criteria #3); adjust `MIN_WEIGHT_THRESHOLD` only if empirically necessary.

---

## Risks / Notes

- **Quality screen may shrink the universe below `MIN_STOCKS`.** If the screen rejects too many of the 15 sector candidates (e.g. user picks one small sector), the existing pipeline guard (`if len(stocks) < 5: return error`) catches this; the user sees the existing "Not enough stocks found" error. Acceptable behavior.
- **`MIN_WEIGHT_THRESHOLD` interaction.** Documented in 3a. If the post-cleanup breadth target needs the threshold lowered, doing so is part of this task, not a follow-up.
- **`MIN_ADV_USD` is US-tuned.** Acceptable today (the universe is effectively US-only). When P2b ships proper country support, this constant will need to be tuned per market. Noted for the P2b spec.
- **Snapshot pin shifts data by one day.** No detectable user impact for multi-year horizons; flagged for completeness.
- **End-to-end reproducibility** is contingent on the predictor and optimizer staying deterministic for fixed inputs (true today). This is a property to defend in future PRs, not something this spec proves.
