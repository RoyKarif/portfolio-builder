# Risk-Aware Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing HRP/MVO routing rule symmetric — HRP wins only when its candidate vol sits within `[cap × HRP_LOWER_TOLERANCE, cap × HRP_UPPER_TOLERANCE]`. Below the lower bound, route to MVO to use more risk budget; above the upper bound, route to MVO to bring vol down. One unified rule across all 5 risk levels.

**Architecture:** Three new module-level constants (`HRP_LOWER_TOLERANCE = 0.7`, `HRP_TOLERANCE_EPSILON = 1e-9`, plus a rename of the existing `HRP_VOL_TOLERANCE` → `HRP_UPPER_TOLERANCE`). One widened `if` condition in the orchestration block. One new `weighting_method` value (`"mvo_underutilized"`). One log key rename + one log key add. No HRP changes, no optimizer changes, no schema changes.

**Tech Stack:** Python 3.10+, FastAPI, Pydantic v2, pytest, React/TypeScript. No new dependencies.

**Reference spec:** [docs/superpowers/specs/2026-04-18-risk-aware-routing-design.md](../specs/2026-04-18-risk-aware-routing-design.md)

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `backend/app/engine/pipeline.py` | **Modify** | Rename + add 3 routing constants; widen the `if` to two-sided with epsilon; add `mvo_underutilized` branch label; rename one log field, add one |
| `backend/tests/test_pipeline_integration.py` | **Modify** | Update import (`HRP_VOL_TOLERANCE` → `HRP_UPPER_TOLERANCE`); bump `risk_level` in 2 existing tests so they stay on the HRP-win path; add 2 new tests covering the `mvo_underutilized` branch (success + equal-weight fallback) |
| `backend/scripts/validate_hrp.py` | **Modify** | Update import + `hybrid_decision()` to mirror the new symmetric rule (Task 1); add HRP-win-rate calibration guardrail printout + extend criterion 1 to accept `mvo_underutilized` (Task 2) |
| `frontend/src/methodology/MethodologyPage.tsx` | **Modify** | Replace the HRP paragraph with the plain-English two-sided framing |

---

## Task 1: Pipeline routing change end-to-end

**Files:**
- Modify: `backend/app/engine/pipeline.py`
- Modify: `backend/tests/test_pipeline_integration.py`
- Modify: `backend/scripts/validate_hrp.py`

The constant rename `HRP_VOL_TOLERANCE → HRP_UPPER_TOLERANCE` cascades through all three files, so they ship together in one commit. TDD: write the new tests first, watch them fail, then make the production change.

### Step 1: Add the two new `mvo_underutilized` tests

Append to `backend/tests/test_pipeline_integration.py`:

```python
@patch("app.engine.pipeline.select_universe", side_effect=_fake_universe)
@patch("app.engine.pipeline.yf.download", side_effect=_fake_yf_download)
def test_pipeline_mvo_underutilized_routes_to_mvo_optimal(mock_dl, mock_uni):
    """At risk_level=5 with the synthetic 10-ticker universe, HRP candidate
    vol (~7%) sits well below cap × LOWER (0.7 × 35% = 24.5%). The new
    symmetric rule must route to MVO with the underutilized label."""
    result = generate_portfolio(
        country="US", risk_level=5, investment_horizon="3-5y",
        available_amount=10_000.0, target_return=10.0,
        preferred_sectors=["Technology"], include_tickers=[], exclude_tickers=[],
        db=None,
    )

    assert "error" not in result, f"pipeline returned error: {result.get('error')}"
    assert result["weighting_method"] == "mvo_underutilized"
    assert result["optimizer_status"] == "optimal"
    assert result["hrp_candidate_vol"] is not None  # HRP did produce a candidate


@patch("app.engine.pipeline.optimize_portfolio", side_effect=_fake_optimize_equal_weight_fallback)
@patch("app.engine.pipeline.select_universe", side_effect=_fake_universe)
@patch("app.engine.pipeline.yf.download", side_effect=_fake_yf_download)
def test_pipeline_mvo_underutilized_with_optimizer_fallback(mock_dl, mock_uni, mock_opt):
    """Same routing trigger as above, but the mocked optimizer returns its
    equal-weight fallback. Verifies the equal-weight collapse semantics —
    weighting_method reports the final outcome (not the entry path),
    optimizer_status mirrors it, and hrp_candidate_vol stays populated
    since HRP did produce a candidate before MVO was invoked."""
    result = generate_portfolio(
        country="US", risk_level=5, investment_horizon="3-5y",
        available_amount=10_000.0, target_return=10.0,
        preferred_sectors=["Technology"], include_tickers=[], exclude_tickers=[],
        db=None,
    )

    assert "error" not in result, f"pipeline returned error: {result.get('error')}"
    assert result["weighting_method"] == "fallback_equal_weight"
    assert result["optimizer_status"] == "fallback_equal_weight"
    assert result["hrp_candidate_vol"] is not None  # HRP did produce a candidate
```

The second test reuses the existing `_fake_optimize_equal_weight_fallback` helper (added in P3 Task 5).

### Step 2: Bump `risk_level` in 2 existing tests + update import

In `backend/tests/test_pipeline_integration.py`, update the imports in the 2 existing tests that reference `HRP_VOL_TOLERANCE`. Find the `test_pipeline_hrp_wins_on_synthetic_data` test:

```python
@patch("app.engine.pipeline.select_universe", side_effect=_fake_universe)
@patch("app.engine.pipeline.yf.download", side_effect=_fake_yf_download)
def test_pipeline_hrp_wins_on_synthetic_data(mock_dl, mock_uni):
    from app.engine.optimizer import RISK_VOLATILITY_CAP
    from app.engine.pipeline import HRP_VOL_TOLERANCE

    result = generate_portfolio(
        country="US", risk_level=3, investment_horizon="3-5y",
        ...
    )

    assert "error" not in result, f"pipeline returned error: {result.get('error')}"
    assert result["weighting_method"] == "hrp"
    assert result["optimizer_status"] is None
    assert result["hrp_candidate_vol"] is not None

    target_vol = RISK_VOLATILITY_CAP[3]
    assert 0 < result["hrp_candidate_vol"] <= target_vol * HRP_VOL_TOLERANCE
    ...
```

Replace with (changing `risk_level=3` → `risk_level=1`, the import to `HRP_UPPER_TOLERANCE`, and the cap lookup to `RISK_VOLATILITY_CAP[1]`):

```python
@patch("app.engine.pipeline.select_universe", side_effect=_fake_universe)
@patch("app.engine.pipeline.yf.download", side_effect=_fake_yf_download)
def test_pipeline_hrp_wins_on_synthetic_data(mock_dl, mock_uni):
    # risk_level changed from 3 -> 1 to keep this test on the HRP-win path
    # after P5's symmetric routing rule. The synthetic universe produces
    # ~7% HRP candidate vol; only risk_level=1 (cap 8%) puts that inside
    # the [LOWER × cap, UPPER × cap] HRP-wins band. At risk_level >= 2
    # the new rule (correctly) routes to mvo_underutilized.
    from app.engine.optimizer import RISK_VOLATILITY_CAP
    from app.engine.pipeline import HRP_UPPER_TOLERANCE

    result = generate_portfolio(
        country="US", risk_level=1, investment_horizon="3-5y",
        available_amount=10_000.0, target_return=10.0,
        preferred_sectors=["Technology"], include_tickers=[], exclude_tickers=[],
        db=None,
    )

    assert "error" not in result, f"pipeline returned error: {result.get('error')}"
    assert result["weighting_method"] == "hrp"
    assert result["optimizer_status"] is None
    assert result["hrp_candidate_vol"] is not None

    target_vol = RISK_VOLATILITY_CAP[1]
    assert 0 < result["hrp_candidate_vol"] <= target_vol * HRP_UPPER_TOLERANCE

    # When HRP wins, hrp_candidate_vol equals risk_score / 100 within rounding
    # tolerance. risk_score is rounded to 2 decimals in pipeline.py
    # (see "round(portfolio_vol * 100, 2)"), so the max delta is 5e-5.
    assert abs(result["hrp_candidate_vol"] - result["risk_score"] / 100) < 1e-4
```

Now find `test_pipeline_holdings_carry_is_defensive_flag`:

```python
@patch("app.engine.pipeline.select_universe", side_effect=_fake_universe_with_defensives)
@patch("app.engine.pipeline.yf.download", side_effect=_fake_yf_download)
def test_pipeline_holdings_carry_is_defensive_flag(mock_dl, mock_uni):
    result = generate_portfolio(
        country="US", risk_level=2, investment_horizon="3-5y",
        ...
    )
```

Change `risk_level=2` → `risk_level=1`. Add an inline comment explaining the bump:

```python
@patch("app.engine.pipeline.select_universe", side_effect=_fake_universe_with_defensives)
@patch("app.engine.pipeline.yf.download", side_effect=_fake_yf_download)
def test_pipeline_holdings_carry_is_defensive_flag(mock_dl, mock_uni):
    # risk_level changed from 2 -> 1 to keep this test on the HRP-win path
    # after P5's symmetric routing rule (see test_pipeline_hrp_wins_on_synthetic_data
    # for the same rationale). At risk_level >= 2 the new rule routes to
    # mvo_underutilized, where MVO might or might not preserve defensives
    # depending on the predictor's expected returns.
    result = generate_portfolio(
        country="US", risk_level=1, investment_horizon="3-5y",
        available_amount=10_000.0, target_return=10.0,
        preferred_sectors=["Technology"], include_tickers=[], exclude_tickers=[],
        db=None,
    )

    assert "error" not in result, f"pipeline returned error: {result.get('error')}"
    # Every holding must have the is_defensive field populated.
    for h in result["holdings"]:
        assert "is_defensive" in h, f"holding missing is_defensive: {h}"
        assert isinstance(h["is_defensive"], bool)
    # At least one defensive ETF is in the holdings (the synthetic universe
    # plus risk_level=1 should make HRP put non-trivial weight on bonds).
    defensive_holdings = [h for h in result["holdings"] if h["is_defensive"]]
    assert len(defensive_holdings) > 0, "expected at least one defensive holding at risk_level=1"
```

### Step 3: Run tests to verify the expected failures

```bash
source /Users/roeykarif/Portfolio-Builder/backend/venv/bin/activate
cd /Users/roeykarif/Portfolio-Builder/backend
DYLD_LIBRARY_PATH=$(pwd)/venv/lib/python3.10/site-packages/xgboost/lib pytest --noconftest tests/test_pipeline_integration.py -v
```

Expected:
- The 2 new tests (`test_pipeline_mvo_underutilized_*`) FAIL because `mvo_underutilized` doesn't exist yet — the existing one-sided rule routes risk_level=5 with HRP vol=7% to plain `"hrp"` (HRP wins under the old rule).
- The 2 updated existing tests will fail at import time with `ImportError: cannot import name 'HRP_UPPER_TOLERANCE' from 'app.engine.pipeline'` — they import a constant that doesn't exist yet.

### Step 4: Update `backend/app/engine/pipeline.py` — constants

Find the existing `HRP_VOL_TOLERANCE` constant near the top of the file:

```python
# Product decision, not a mathematical truth — accept HRP if it's within
# 10% of the user's risk cap. Tune after observing real-world drift.
HRP_VOL_TOLERANCE = 1.10
```

Replace with:

```python
# Product decisions, not mathematical truths — calibrated against observed
# real-world routing behavior. HRP wins when its candidate vol sits inside
# the band [cap × LOWER, cap × UPPER]; outside the band, MVO runs to honor
# the cap (above) or to use more of the user's risk budget (below).
HRP_UPPER_TOLERANCE = 1.10
HRP_LOWER_TOLERANCE = 0.7
# Small slack at the boundary so float-precision wobble doesn't produce
# inconsistent routing. Biases toward HRP at the boundary — the default
# behavior wins when the routing decision is genuinely indeterminate.
HRP_TOLERANCE_EPSILON = 1e-9
```

### Step 5: Update `backend/app/engine/pipeline.py` — routing block

Find the orchestration block in `generate_portfolio`. The current code is:

```python
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
            # optimize_portfolio rounds weights to 4 decimals before returning,
            # so the sum can drift by up to n × 5e-5. Renormalize so the
            # post-block assertion stays strict.
            weights_array = weights_array / weights_array.sum()
            optimizer_status = opt_result["status"]
            weighting_method = (
                "fallback_equal_weight"
                if optimizer_status == "fallback_equal_weight"
                else "mvo_risk_cap"
            )
            portfolio_vol = opt_result["portfolio_volatility"]
            portfolio_return = opt_result["portfolio_return"]
```

Replace with:

```python
        # Symmetric two-sided routing: HRP wins iff its candidate vol sits
        # in [cap × LOWER, cap × UPPER]. Outside the band, MVO honors the
        # cap (overshoot path) or uses more risk budget (underutilized path).
        # Epsilon expands the band on both sides so FP precision near the
        # boundary doesn't produce inconsistent routing.
        lower_bound = target_vol * HRP_LOWER_TOLERANCE - HRP_TOLERANCE_EPSILON
        upper_bound = target_vol * HRP_UPPER_TOLERANCE + HRP_TOLERANCE_EPSILON

        if lower_bound <= hrp_candidate_vol <= upper_bound:
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
            # optimize_portfolio rounds weights to 4 decimals before returning,
            # so the sum can drift by up to n × 5e-5. Renormalize so the
            # post-block assertion stays strict.
            weights_array = weights_array / weights_array.sum()
            optimizer_status = opt_result["status"]
            # Final routing reason depends on which side of the band we exited:
            # above upper -> mvo_risk_cap, below lower -> mvo_underutilized.
            # If the optimizer itself fell back, both collapse to fallback_equal_weight.
            if optimizer_status == "fallback_equal_weight":
                weighting_method = "fallback_equal_weight"
            elif hrp_candidate_vol > upper_bound:
                weighting_method = "mvo_risk_cap"
            else:
                weighting_method = "mvo_underutilized"
            portfolio_vol = opt_result["portfolio_volatility"]
            portfolio_return = opt_result["portfolio_return"]
```

The `except ValueError` branch (HRP raised) below this block is unchanged — still uses the existing `"mvo_fallback_hrp_error"` label.

### Step 6: Update `backend/app/engine/pipeline.py` — log fields

Find the structured log call:

```python
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

Replace with:

```python
    logger.info(
        "portfolio_construction",
        extra={
            "hrp_candidate_vol": hrp_candidate_vol,
            "hrp_error": hrp_error,
            "target_vol": target_vol,
            "lower_tolerance": HRP_LOWER_TOLERANCE,
            "upper_tolerance": HRP_UPPER_TOLERANCE,
            "weighting_method": weighting_method,
            "optimizer_status": optimizer_status,
        },
    )
```

Two changes: `tolerance` → `upper_tolerance` (rename), `lower_tolerance` (new field).

### Step 7: Update `backend/scripts/validate_hrp.py` — import + `hybrid_decision`

Find the import block:

```python
from app.engine.pipeline import HRP_VOL_TOLERANCE
```

Replace with:

```python
from app.engine.pipeline import (
    HRP_LOWER_TOLERANCE,
    HRP_TOLERANCE_EPSILON,
    HRP_UPPER_TOLERANCE,
)
```

Find the `hybrid_decision` function:

```python
def hybrid_decision(hrp_vol, mvo_status, target_vol, hrp_error) -> str:
    """Replays the routing logic from app.engine.pipeline so we can label
    each portfolio without invoking the full pipeline machinery."""
    if hrp_error is not None:
        return "fallback_equal_weight" if mvo_status == "fallback_equal_weight" else "mvo_fallback_hrp_error"
    if hrp_vol <= target_vol * HRP_VOL_TOLERANCE:
        return "hrp"
    return "fallback_equal_weight" if mvo_status == "fallback_equal_weight" else "mvo_risk_cap"
```

Replace with:

```python
def hybrid_decision(hrp_vol, mvo_status, target_vol, hrp_error) -> str:
    """Replays the routing logic from app.engine.pipeline so we can label
    each portfolio without invoking the full pipeline machinery. Mirrors
    the symmetric two-sided rule from P5."""
    if hrp_error is not None:
        return "fallback_equal_weight" if mvo_status == "fallback_equal_weight" else "mvo_fallback_hrp_error"
    lower_bound = target_vol * HRP_LOWER_TOLERANCE - HRP_TOLERANCE_EPSILON
    upper_bound = target_vol * HRP_UPPER_TOLERANCE + HRP_TOLERANCE_EPSILON
    if lower_bound <= hrp_vol <= upper_bound:
        return "hrp"
    if mvo_status == "fallback_equal_weight":
        return "fallback_equal_weight"
    if hrp_vol > upper_bound:
        return "mvo_risk_cap"
    return "mvo_underutilized"
```

### Step 8: Run all tests to verify they pass

```bash
source /Users/roeykarif/Portfolio-Builder/backend/venv/bin/activate
cd /Users/roeykarif/Portfolio-Builder/backend
DYLD_LIBRARY_PATH=$(pwd)/venv/lib/python3.10/site-packages/xgboost/lib pytest --noconftest tests/test_pipeline_integration.py tests/test_hrp.py tests/test_engine/test_universe.py -v
```

Expected: 25 PASS — 5 universe + 8 HRP + 10 pre-existing pipeline + 2 new pipeline (this task) = 25 total.

If any of the existing pre-existing pipeline tests fail (e.g. one that previously asserted `weighting_method == "hrp"` at risk_level=3 that wasn't in the bumped-list because we missed it), STOP and report.

### Step 9: Smoke-check the validation script imports

```bash
DYLD_LIBRARY_PATH=$(pwd)/venv/lib/python3.10/site-packages/xgboost/lib python -c "
from scripts.validate_hrp import hybrid_decision, HRP_LOWER_TOLERANCE, HRP_UPPER_TOLERANCE
print('LOWER:', HRP_LOWER_TOLERANCE, 'UPPER:', HRP_UPPER_TOLERANCE)
# Smoke-test all 5 routing outcomes:
print('HRP wins:', hybrid_decision(0.10, 'optimal', 0.12, None))  # 0.084 <= 0.10 <= 0.132
print('MVO underutilized:', hybrid_decision(0.05, 'optimal', 0.12, None))  # 0.05 < 0.084
print('MVO risk_cap:', hybrid_decision(0.20, 'optimal', 0.12, None))  # 0.20 > 0.132
print('MVO HRP error:', hybrid_decision(None, 'optimal', 0.12, 'forced'))
print('Equal-weight:', hybrid_decision(0.05, 'fallback_equal_weight', 0.12, None))
"
```

Expected output:
```
LOWER: 0.7 UPPER: 1.1
HRP wins: hrp
MVO underutilized: mvo_underutilized
MVO risk_cap: mvo_risk_cap
MVO HRP error: mvo_fallback_hrp_error
Equal-weight: fallback_equal_weight
```

If any of the 5 lines reports the wrong label, the routing logic in `hybrid_decision` is buggy.

### Step 10: Commit

```bash
cd /Users/roeykarif/Portfolio-Builder
git add backend/app/engine/pipeline.py backend/tests/test_pipeline_integration.py backend/scripts/validate_hrp.py
git commit -m "feat(pipeline): symmetric two-sided HRP/MVO routing

Adds HRP_LOWER_TOLERANCE = 0.7 alongside HRP_UPPER_TOLERANCE (renamed
from HRP_VOL_TOLERANCE). HRP wins iff its candidate vol sits inside
[cap × LOWER, cap × UPPER]; below the lower bound, MVO runs to use
more risk budget (new mvo_underutilized weighting_method); above the
upper bound, MVO runs to bring vol down (existing mvo_risk_cap).

A small HRP_TOLERANCE_EPSILON = 1e-9 expands the band on both sides
so float-precision wobble doesn't produce inconsistent routing —
biases toward HRP (the default) at the boundary.

Log payload renamed 'tolerance' to 'upper_tolerance' and added
'lower_tolerance' for symmetry. Two existing tests bumped from
risk_level=3/2 to risk_level=1 to stay on the HRP-win path under
the new rule (their original assertions are correct; the rule is
what changed). Two new tests cover the mvo_underutilized branch
including its equal-weight collapse path.

Validation script's hybrid_decision() updated to mirror the new
symmetric rule. Validation feature additions (HRP win-rate
guardrail) are deferred to the next task to keep the diff focused."
```

---

## Task 2: Validation script — HRP win-rate guardrail + criterion 1 update

**Files:**
- Modify: `backend/scripts/validate_hrp.py`

Two updates: add the calibration guardrail printout after TABLE 1, and extend criterion 1 to accept `mvo_underutilized` (since it's a non-collapse outcome at low risk levels — the criterion is "no equal-weight collapse", not "HRP must win").

### Step 1: Extend criterion 1 to accept `mvo_underutilized`

In `backend/scripts/validate_hrp.py`, find the criterion 1 block in `run_real_data_spot_check`:

```python
    # Criterion 1: no equal-weight collapse on risk levels 1-3.
    methods_1_3 = {rl: runs[rl]["weighting_method"] for rl in [1, 2, 3]}
    crit1_pass = all(m in {"hrp", "mvo_risk_cap"} for m in methods_1_3.values())
    print(f"  [1] No equal-weight collapse on risk_level 1-3:  {'PASS' if crit1_pass else 'FAIL'}")
    print(f"      methods: {methods_1_3}")
```

Replace with:

```python
    # Criterion 1: no equal-weight collapse on risk levels 1-3.
    # Accepted outcomes: hrp, mvo_risk_cap, mvo_underutilized — all three
    # are real construction outcomes (not the equal-weight rescue path).
    methods_1_3 = {rl: runs[rl]["weighting_method"] for rl in [1, 2, 3]}
    crit1_pass = all(m in {"hrp", "mvo_risk_cap", "mvo_underutilized"} for m in methods_1_3.values())
    print(f"  [1] No equal-weight collapse on risk_level 1-3:  {'PASS' if crit1_pass else 'FAIL'}")
    print(f"      methods: {methods_1_3}")
```

### Step 2: Add the HRP win-rate calibration guardrail

In `backend/scripts/validate_hrp.py`, find the `print_routing` function (which prints TABLE 1):

```python
def print_routing(routing_counts, total):
    print("=" * 64)
    print("TABLE 1 — Routing distribution (synthetic sweep, n=45)")
    print("=" * 64)
    print(f"{'weighting_method':<28} {'count':>6} {'pct':>6}")
    print("-" * 64)
    for method in ["hrp", "mvo_risk_cap", "mvo_fallback_hrp_error", "fallback_equal_weight"]:
        c = routing_counts[method]
        print(f"{method:<28} {c:>6} {c*100/total:>5.1f}%")
    print()
```

Replace with (adds the new `mvo_underutilized` row, plus the calibration guardrail printout below the table):

```python
def print_routing(routing_counts, total):
    print("=" * 64)
    print("TABLE 1 — Routing distribution (synthetic sweep, n=45)")
    print("=" * 64)
    print(f"{'weighting_method':<28} {'count':>6} {'pct':>6}")
    print("-" * 64)
    for method in ["hrp", "mvo_risk_cap", "mvo_underutilized", "mvo_fallback_hrp_error", "fallback_equal_weight"]:
        c = routing_counts[method]
        print(f"{method:<28} {c:>6} {c*100/total:>5.1f}%")
    print()

    # Calibration guardrail: if HRP win rate drops materially below 30% on
    # the current synthetic generator, the lower tolerance is over-tight
    # and HRP_LOWER_TOLERANCE should be relaxed (toward 0.6 or 0.5).
    # If it stays well above 50%, the rule isn't biting (consider tightening
    # toward 0.8). This threshold reflects the current synthetic generator;
    # if the generator changes materially, recalibrate alongside.
    hrp_pct = routing_counts["hrp"] * 100 / total
    print(f"HRP win rate on synthetic sweep: {hrp_pct:.1f}%")
    if hrp_pct < 30:
        print("  WARNING: below ~30% — revisit HRP_LOWER_TOLERANCE calibration (consider loosening)")
    elif hrp_pct > 50:
        print("  NOTE: above ~50% — rule may not be biting hard enough (consider tightening)")
    else:
        print("  OK: within expected ~30-50% calibration range")
    print()
```

The new `mvo_underutilized` row needs to be added to the `routing_counts` dict initialization in `run_synthetic_sweep` (it'll currently throw `KeyError` on the increment). Find this block:

```python
    routing_counts = {
        "hrp": 0,
        "mvo_risk_cap": 0,
        "mvo_fallback_hrp_error": 0,
        "fallback_equal_weight": 0,
    }
```

Replace with:

```python
    routing_counts = {
        "hrp": 0,
        "mvo_risk_cap": 0,
        "mvo_underutilized": 0,
        "mvo_fallback_hrp_error": 0,
        "fallback_equal_weight": 0,
    }
```

### Step 3: Run the script and inspect output

```bash
source /Users/roeykarif/Portfolio-Builder/backend/venv/bin/activate
cd /Users/roeykarif/Portfolio-Builder/backend
DYLD_LIBRARY_PATH=$(pwd)/venv/lib/python3.10/site-packages/xgboost/lib python scripts/validate_hrp.py 2>&1 | tail -80
```

Expected output highlights:
- TABLE 1: routing distribution now includes a `mvo_underutilized` row with non-zero count, plus the HRP win-rate guardrail printout (likely "OK: within expected ~30-50% calibration range" — but if it's below 30%, that's a real signal to investigate)
- TABLE 4 (real-data): risk levels 1, 2, 3, 4, 5 should now produce **5 different portfolios** (no more byte-identical rows)
- TABLE 5: criterion 1 PASSES (now accepts `mvo_underutilized`); criterion 2 should now PASS (risk-level differentiation restored); criteria 3, 4, 5 should PASS as before
- OVERALL: 5/5 success criteria passing

If criterion 2 still FAILs, that's a real signal — investigate before committing. The L1 deltas should now be substantially > 0.10 since MVO honors different per-level caps.

If the HRP win-rate guardrail prints the WARNING line (below 30%), that's also a calibration signal — note the actual percentage and report it. This is a separate decision from "should we ship" — see Step 4.

### Step 4: Decide on calibration outcome

Three possible scenarios after Step 3:

1. **5/5 PASS, HRP win rate in 30-50% range** — happy path. Proceed to Step 5.
2. **5/5 PASS, HRP win rate < 30% or > 50%** — the routing works correctly but the calibration is at an extreme. Report the actual percentage. Proceed to Step 5 anyway (the spec said this is a calibration signal, not a hard fail), but flag for follow-up.
3. **< 5/5 PASS** — STOP and report. Investigate which criterion failed and why. Do not commit a script that prints failing criteria as final output unless the user confirms the failure is acceptable.

### Step 5: Commit

```bash
cd /Users/roeykarif/Portfolio-Builder
git add backend/scripts/validate_hrp.py
git commit -m "chore(validation): HRP win-rate calibration guardrail + accept mvo_underutilized

Two updates to the validation script:

1. Criterion 1 (no equal-weight collapse on risk_level 1-3) now accepts
   mvo_underutilized as a passing outcome — the criterion is about
   avoiding the equal-weight rescue, not about which non-collapse
   path was taken.

2. After TABLE 1, print HRP's share of the synthetic sweep with a
   calibration hint: WARNING below 30% (loosen HRP_LOWER_TOLERANCE),
   NOTE above 50% (rule may not bite), OK in between. Per spec, this
   is a calibration signal tied to the current synthetic generator,
   not a hard product invariant.

routing_counts dict gains the mvo_underutilized key so the increment
in the synthetic sweep doesn't KeyError."
```

---

## Task 3: Methodology page — replace the HRP paragraph

**Files:**
- Modify: `frontend/src/methodology/MethodologyPage.tsx`

Replace the existing HRP paragraph (added in P3) with the plain-English two-sided framing.

### Step 1: Replace the paragraph

In `frontend/src/methodology/MethodologyPage.tsx`, locate the existing HRP paragraph in the optimization section. The current paragraph (added in P3) is:

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

Replace with:

```tsx
        <p className="text-gray-700 mb-3">
          By default we use a method called <strong>Hierarchical Risk Parity (HRP)</strong> — a
          clustering-based approach that spreads risk across groups of stocks that tend to
          move together. HRP tends to produce more stable, diversified portfolios than
          classical mean-variance optimization, especially when the per-stock return
          estimates are noisy. We then check whether HRP's portfolio matches your chosen
          risk level. If HRP comes out much riskier than your profile allows, we fall back
          to mean-variance optimization to bring volatility down. If HRP comes out much
          more conservative than your profile, we likewise fall back to mean-variance
          optimization so the portfolio better matches the risk level you selected.
        </p>
```

The new wording uses the plain-English two-sided framing approved in the spec. No "risk budget" jargon. Indentation and `className` match the surrounding code.

### Step 2: Verify the file structure is intact

```bash
cd /Users/roeykarif/Portfolio-Builder && python3 -c "
content = open('frontend/src/methodology/MethodologyPage.tsx').read()
assert content.count('<section') == content.count('</section>'), 'mismatched section tags'
assert content.count('<p ') == content.count('</p>'), 'mismatched p tags'
assert 'much more conservative than your profile' in content, 'two-sided HRP paragraph not added'
assert 'overshoots by more than 10%' not in content, 'old one-sided HRP wording still present'
print('OK')
"
```

If the assertion check fails, STOP and report.

If a TypeScript build is available, also run:

```bash
cd /Users/roeykarif/Portfolio-Builder/frontend && npm run build 2>&1 | tail -5
```

### Step 3: Commit

```bash
cd /Users/roeykarif/Portfolio-Builder
git add frontend/src/methodology/MethodologyPage.tsx
git commit -m "docs(methodology): two-sided HRP/MVO routing explanation

Replace the existing HRP paragraph (one-sided framing — only mentioned
fallback when HRP overshoots) with the symmetric two-sided framing
approved in the P5 spec. The new wording explains both fallback paths
in plain English: if HRP comes out much riskier than the profile,
fall back to MVO to bring vol down; if HRP comes out much more
conservative than the profile, fall back to MVO so the portfolio
better matches the chosen risk level."
```

---

## Final verification

After all 3 tasks complete, run the full backend test suite once more:

```bash
source /Users/roeykarif/Portfolio-Builder/backend/venv/bin/activate
cd /Users/roeykarif/Portfolio-Builder/backend
DYLD_LIBRARY_PATH=$(pwd)/venv/lib/python3.10/site-packages/xgboost/lib pytest --noconftest tests/test_pipeline_integration.py tests/test_hrp.py tests/test_engine/test_universe.py -v
```

Expected: **25 tests pass** — 5 universe + 8 HRP + 12 pipeline (10 pre-existing + 2 new from this plan).

Then run the validation script and confirm:
- 5/5 success criteria passing in TABLE 5
- HRP win-rate guardrail printout shows OK or NOTE (not WARNING)
- TABLE 4 shows 5 differentiated portfolios for the 5 risk levels
