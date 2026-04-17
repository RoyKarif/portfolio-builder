# Covariance Estimation Upgrade — Design Spec

**Date:** 2026-04-17
**Status:** Approved by user, ready for implementation planning
**Roadmap context:** Phase 1 of the "smarter math" roadmap (P1 of 4). Subsequent phases (P2 return prediction, P3 portfolio construction, P4 simulation) will be specced separately after P1 ships.

## Problem

The pipeline's covariance matrix is currently computed as a raw sample covariance of daily returns:

```python
# pipeline.py
cov_matrix = returns_df.cov().values * 252
```

With roughly 500 daily observations across ~50 tickers, the sample covariance is noisy and ill-conditioned. Mean-variance optimization amplifies errors in its inputs, so small perturbations in the covariance produce large swings in portfolio weights and unstable risk estimates. This is the cheapest credible quality upgrade available in the engine.

## Goals

- Replace raw sample covariance with a shrinkage estimator that stabilizes downstream optimization.
- Keep the change localized: one new module, one line changed in `pipeline.py`, two new fields in the engine output.
- Add minimal observability (log + engine-result fields) so we can inspect behavior in production.
- Add a short plain-language paragraph to the methodology page explaining the technique at a user-appropriate level.

## Non-Goals / Out of Scope

The following are explicitly deferred and MUST NOT be changed as part of this work:

- Return definition (daily simple returns via `pct_change()`).
- Annualization convention (`× 252`).
- Lookback window (currently 2 years daily).
- Alternative covariance estimators (factor-based / PCA, EWMA, GARCH, DCC-GARCH, OAS).
- User-facing choice between estimators.
- Any change to the predictor, optimizer, or simulator.
- Any change to the UI beyond the methodology-page paragraph.

---

## Design

### 1. New module: `backend/app/engine/risk.py`

A single public function:

```python
def estimate_covariance(returns: pd.DataFrame) -> tuple[np.ndarray, float, dict]:
    ...
```

**Input contract:**
- `returns`: a `pandas.DataFrame` of **daily simple returns** (already computed by the caller via `prices.pct_change()`).
- Rows are trading dates, indexed chronologically.
- Columns are tickers, in the order the caller wants them preserved in the output matrix.
- May contain NaN (see NaN handling below).

**Output contract:**
- `cov_matrix`: `np.ndarray` of shape `(N, N)`, where `N` is the number of tickers **after NaN cleaning**. Annualized by ×252. Column/row order matches the cleaned ticker order.
- `shrinkage`: `float` in `[0.0, 1.0]` — the Ledoit-Wolf shrinkage intensity α.
- `metadata`: `dict` with keys:
  - `method`: `"ledoit_wolf"` or `"sample_fallback"`
  - `n_tickers`: int, N after cleaning
  - `n_observations`: int, rows after cleaning
  - `dropped_tickers`: list[str], tickers removed during NaN cleaning
  - `fallback_used`: bool
  - `fallback_reason`: str | None

The caller is responsible for aligning its ticker/weight arrays to the cleaned ticker order. The helper does not reorder or pad.

### 2. NaN handling

Applied in this order inside `estimate_covariance` to produce a single cleaned working frame, `clean_returns`. **All downstream logic — estimation, fallback, metadata counts, and output alignment — operates on `clean_returns` and its column order.** The original input frame is not used again after cleaning.

1. **Validate dtypes up front.** If any column is non-numeric (dtype is not a float/int), raise `ValueError("estimate_covariance requires numeric columns")` immediately. Do **not** coerce silently.
2. **Drop all-NaN columns.** Any ticker whose column is entirely NaN is removed. Its name is recorded in `metadata["dropped_tickers"]`.
3. **Drop rows with any remaining NaN.** After step 2, drop rows where any surviving ticker is NaN. This preserves a consistent observation window across all tickers.
4. **Validate counts.** After cleaning:
   - If `n_tickers < 2` → raise `ValueError("estimate_covariance requires at least 2 tickers after cleaning")`.
   - If `n_observations < 30` → raise `ValueError("estimate_covariance requires at least 30 observations after cleaning")`.

The 30-observation threshold is an **operational guardrail**, not a claim of statistical sufficiency — it only prevents obviously broken inputs from reaching sklearn. Meaningful sample-size concerns remain the caller's responsibility (the broader "not enough historical data" guard upstream in `pipeline.py` covers that).

### 3. Error vs fallback

Two distinct failure modes, handled differently:

**Data-validation failures → raise `ValueError`.**
- <2 tickers after cleaning
- <30 observations after cleaning
- Non-numeric input

The caller (`pipeline.py`) catches these and returns the same `{"error": "..."}` shape it already uses for "Not enough historical data available."

**Technical/runtime failures → log warning, fall back to sample covariance.**
- `sklearn.covariance.LedoitWolf().fit(...)` raises unexpectedly
- Numerical issues inside sklearn that produce non-finite output

Fallback behavior:
- Compute `clean_returns.cov().values * 252` on the **cleaned** frame (never the original input). Using `clean_returns` keeps the fallback matrix shape-consistent with `metadata["n_tickers"]`, `metadata["dropped_tickers"]`, and the output ticker order, and avoids NaN contamination.
- Set `metadata["method"] = "sample_fallback"`.
- Set `metadata["fallback_used"] = True`.
- Set `metadata["fallback_reason"] = <exception type and message>`.
- Set `shrinkage = 0.0`.
- Log at WARNING level.

Rationale: a sklearn hiccup should not 500 a user request when we have a usable (if noisier) alternative.

### 4. PSD sanity check

After producing the final `cov_matrix` (from either path), run a tolerance-based PSD check:

```python
eigenvalues = np.linalg.eigvalsh(cov_matrix)
min_eig = float(eigenvalues.min())
if min_eig < -1e-8:
    logger.warning(
        "estimate_covariance produced non-PSD matrix (min eigenvalue %.3e)", min_eig
    )
```

This is a **soft check**: log but do not raise. Floating-point noise can push the smallest eigenvalue marginally negative; the tolerance of `-1e-8` absorbs that without masking genuine numerical breakdowns. CVXPY's SCS/ECOS solvers are robust to tiny non-PSD noise.

### 5. Pipeline integration

In `backend/app/engine/pipeline.py`, replace:

```python
cov_matrix = returns_df.cov().values * 252
```

with:

```python
from app.engine.risk import estimate_covariance

cov_matrix, shrinkage, cov_meta = estimate_covariance(returns_df)

# If estimate_covariance dropped any tickers, realign every ticker-ordered
# structure before the optimizer call.
if cov_meta["dropped_tickers"]:
    dropped = set(cov_meta["dropped_tickers"])
    valid_tickers = [t for t in valid_tickers if t not in dropped]
    valid_stocks = [s for s in valid_stocks if s["ticker"] not in dropped]
    valid_returns = np.array([s["expected_return"] for s in valid_stocks])
    if len(valid_tickers) < 5:
        return {"error": "Not enough historical data available."}
```

**Ticker realignment rule:** after `estimate_covariance` returns, any data structure whose ordering or length is indexed by ticker — including `valid_tickers`, `valid_stocks`, `valid_returns`, `price_data`, and any subsequent weight arrays built from these — MUST be filtered to drop entries in `cov_meta["dropped_tickers"]` and re-aligned to the surviving ticker order before reaching the optimizer. The optimizer requires `expected_returns`, `cov_matrix`, and the ticker list to share a single consistent order; the integration test below is the primary guard against this class of bug.

### 6. Engine result fields

Add two fields to the dict returned by `generate_portfolio`:

```python
"covariance_method": cov_meta["method"],          # "ledoit_wolf" or "sample_fallback"
"shrinkage_intensity": round(shrinkage, 4),       # float in [0, 1]
```

**API exposure (resolved):** include both fields in the `PortfolioResponse` Pydantic schema as **optional** (`covariance_method: str | None = None`, `shrinkage_intensity: float | None = None`). Optional typing preserves backward compatibility for any previously persisted portfolio that lacks these fields. No UI surface is added.

**DB persistence (resolved):** persist these fields in the existing portfolio/snapshot record **only if** the current model already carries ad-hoc engine metadata (e.g. a JSON column) that can absorb new keys without migration. If persistence would require a new migration or a schema change, **skip persistence in this phase** and rely on logging only. The writing-plans phase will inspect the model and make the call; no migration is introduced for this work.

### 7. Observability (logging)

Emit one INFO log per call to `estimate_covariance`:

```
covariance_estimated method=ledoit_wolf n_tickers=47 n_obs=498 shrinkage=0.1823 dropped=2 fallback=False
```

Use the standard `logging` module with the `app.engine.risk` logger. No structured logging changes are in scope.

On fallback, also emit a WARNING log with the exception details.

---

## Methodology page update

Add one paragraph to the existing "Building the Portfolio" section on `/methodology`. No new section, no new glossary term, no library names.

> *To measure how different stocks move together, we use a shrinkage technique. Raw correlations between stocks can be misleading when the data is noisy. Shrinkage nudges those correlations toward a more reliable baseline, which makes the resulting portfolio less sensitive to random quirks in the historical data. This is a well-established technique in professional portfolio construction.*

Insertion point is at the end of the existing "Building the Portfolio" section, **after** the "don't put all your eggs in one basket" paragraph in [frontend/src/methodology/MethodologyPage.tsx](../../../frontend/src/methodology/MethodologyPage.tsx). Narrative flow: explain mean-variance → diversification analogy → then the shrinkage paragraph as a refinement to the inputs. The paragraph should feel like part of the existing explanation.

---

## Testing

### Unit tests — `backend/tests/test_risk.py` (new)

Fixture: a small synthetic returns DataFrame (e.g., 200 rows × 5 tickers) generated from a known multivariate normal with a fixed seed.

1. **Happy path shape + types**
   - Output `cov_matrix` has shape `(5, 5)`.
   - Output is symmetric: `np.allclose(cov, cov.T)`.
   - `shrinkage` is a float in `[0.0, 1.0]`.
   - `metadata["method"] == "ledoit_wolf"`.
   - `metadata["n_tickers"] == 5` and `metadata["n_observations"] == 200`.

2. **PSD within tolerance**
   - `np.linalg.eigvalsh(cov).min() > -1e-8`.

3. **NaN handling: all-NaN column dropped**
   - Inject one column entirely NaN → that ticker appears in `dropped_tickers`, output shape is `(4, 4)`, no error.

4. **NaN handling: partial NaNs drop rows**
   - Scatter NaNs across rows → those rows are dropped, `n_observations` reflects it.

5. **Validation error: too few tickers**
   - DataFrame with 1 ticker → raises `ValueError`.

6. **Validation error: too few observations**
   - DataFrame with 20 rows → raises `ValueError`.

7. **Fallback path**
   - Monkeypatch `sklearn.covariance.LedoitWolf.fit` to raise `RuntimeError("boom")`.
   - Call the function → no exception raised to caller.
   - `metadata["method"] == "sample_fallback"`, `metadata["fallback_used"] is True`, `metadata["fallback_reason"]` contains `"boom"`.
   - `shrinkage == 0.0`.
   - `cov_matrix` still has correct shape and is annualized.

*(Explicitly dropped: monotonicity test "more noise → higher shrinkage." The behavior is real but the test is flaky at small sample sizes; not worth the maintenance burden. If we want a property check later, it belongs in a separate benchmark script, not the unit suite.)*

### Integration test — extend `backend/tests/test_portfolios.py`

Extend the existing portfolio-generation smoke test (or add one alongside it):

- Run `generate_portfolio` end-to-end with mocked `yf.download` returning a fixed-seed synthetic price panel.
- Assert the response includes `covariance_method` and `shrinkage_intensity`.
- Assert `covariance_method == "ledoit_wolf"` on the happy path.
- Assert weights still sum to ~1.0 (within 1e-4), no NaN weights, and all weights in `[0, MAX_SINGLE_WEIGHT]`.

---

## Risks / Notes

- **Sample-mean centering.** `sklearn.covariance.LedoitWolf` uses `assume_centered=False` by default, which subtracts the per-column sample mean before estimation. Daily returns are close to zero-mean but not exactly. The default behavior is correct for our use case; no change needed, just documenting the assumption.
- **Risk score may drift.** Shrunk covariance typically produces slightly lower portfolio-variance estimates than raw sample covariance (it pulls off-diagonal correlations toward a structured target, which reduces extreme concentration effects). The `risk_score` shown to users may nudge downward for the same inputs after this ships. Acceptable and expected; eyeball the first few live portfolios post-deploy to confirm no pathological shift.
- **Ticker realignment bug surface.** The most likely implementation mistake is forgetting to realign `valid_tickers` / `valid_returns` when `estimate_covariance` drops a ticker. The integration test above is the primary guard; the implementation plan should call this out explicitly.
