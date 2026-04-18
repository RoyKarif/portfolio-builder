# Risk-Aware Routing (Design Spec)

**Date:** 2026-04-18
**Status:** Approved, ready for implementation plan
**Phase:** P5 (risk-aware routing)

## Goal

Restore meaningful differentiation across the `risk_level` slider. After
P4, the
[defensive-universe validation](../findings/2026-04-18-defensive-universe-validation.md)
confirmed the original equal-weight collapse was fixed but criterion 2
(risk-level differentiation) failed: risk levels 1, 2, and 3 produce
byte-identical portfolios because HRP is risk-blind and the augmented
universe gives an HRP candidate vol (~7%) well below all three caps.
Risk levels 4 and 5 share the same problem on the standard tech
universe.

P5 makes the existing HRP/MVO routing rule symmetric. Today HRP wins
when its vol sits below `cap × HRP_VOL_TOLERANCE` (1.10) — bounded only
on the upside. P5 adds a lower bound: HRP wins only when its vol sits
in the band `[cap × LOWER, cap × UPPER]`. Below the lower bound, MVO
runs to use more of the user's risk budget; above the upper bound, MVO
runs to bring vol down. Both off-ramps already exist in the code as
"go to MVO with the cap"; we're just adding a new reason to take them.

No HRP changes, no optimizer changes, no new optimization mechanisms.
One unified rule across all 5 risk levels.

## Architecture

### 1 — Routing logic and constants

**Current rule** (one-sided, in
[backend/app/engine/pipeline.py](../../../backend/app/engine/pipeline.py)):

```python
HRP_VOL_TOLERANCE = 1.10

if hrp_candidate_vol <= target_vol * HRP_VOL_TOLERANCE:
    use HRP
else:
    use MVO  # bring vol DOWN
```

**New rule** (symmetric):

```python
HRP_UPPER_TOLERANCE = 1.10  # renamed from HRP_VOL_TOLERANCE
HRP_LOWER_TOLERANCE = 0.7   # new

if target_vol * HRP_LOWER_TOLERANCE <= hrp_candidate_vol <= target_vol * HRP_UPPER_TOLERANCE:
    use HRP
else:
    use MVO  # bring vol DOWN if too high, OR UP if HRP underutilizes the budget
```

**Conceptual framing.** Both bounds are about *fit to the user's stated
preference*, not about HRP being right or wrong:

- Above upper bound → HRP too risky for this profile. MVO honors the cap
  by reducing vol.
- Below lower bound → HRP too conservative relative to this profile.
  MVO honors the cap by using more of the budget for return.

**Both constants are product knobs.** `HRP_LOWER_TOLERANCE = 0.7` is an
initial calibrated default, not a theoretical truth — same status as
`HRP_UPPER_TOLERANCE = 1.10`. Both are tunable based on observed
real-world routing behavior. The spec commits to the *symmetric rule
shape*, not to the specific numeric values.

**Walk-through against current observed data:**

| risk_level | cap | HRP vol | ratio | ≥ LOWER (0.7)? | ≤ UPPER (1.10)? | Result |
|---|---|---|---|---|---|---|
| 1 | 0.08 | 0.07 | 0.88 | ✓ | ✓ | **HRP** |
| 2 | 0.12 | 0.07 | 0.58 | ✗ | — | **MVO** (cap 12%) |
| 3 | 0.18 | 0.07 | 0.39 | ✗ | — | **MVO** (cap 18%) |
| 4 | 0.25 | 0.22 | 0.86 | ✓ | ✓ | **HRP** |
| 5 | 0.35 | 0.22 | 0.62 | ✗ | — | **MVO** (cap 35%) |

All five risk levels now produce differentiated portfolios — HRP at
levels 1 and 4 (where its natural output fits the cap), MVO at 2/3/5
honoring different per-level caps.

**Renaming `HRP_VOL_TOLERANCE` → `HRP_UPPER_TOLERANCE`.** Worth doing
for symmetry with the new `HRP_LOWER_TOLERANCE`. Three internal
references update:
- `pipeline.py` (definition + use)
- `backend/scripts/validate_hrp.py` (import)
- `backend/tests/test_pipeline_integration.py` (import in two tests)

The methodology page text mentions "10%" but doesn't reference the
constant by name; it gets updated for the new two-sided framing
(see §3 below).

### 2 — Result metadata and logging

**Five `weighting_method` values** (one new):

| Value | Meaning |
|---|---|
| `"hrp"` | HRP candidate vol within `[cap × LOWER, cap × UPPER]` — accepted |
| `"mvo_risk_cap"` | HRP candidate vol > `cap × UPPER` — MVO ran to bring vol DOWN |
| `"mvo_underutilized"` | HRP candidate vol < `cap × LOWER` — MVO ran to use more risk budget UP toward the cap **(new)** |
| `"mvo_fallback_hrp_error"` | HRP raised — MVO ran with no specific routing reason |
| `"fallback_equal_weight"` | MVO ran but fell back to its own equal-weight rescue |

**Updated fallback table** (extends [the P3 spec §3 table](2026-04-18-portfolio-construction-design.md)):

| Final state | `weighting_method` | `optimizer_status` | `hrp_candidate_vol` |
|---|---|---|---|
| HRP wins | `"hrp"` | `None` | populated |
| HRP overshoots cap → MVO optimal | `"mvo_risk_cap"` | `"optimal"` | populated |
| HRP overshoots cap → MVO equal-weight | `"fallback_equal_weight"` | `"fallback_equal_weight"` | populated |
| **HRP underutilizes → MVO optimal** | `"mvo_underutilized"` | `"optimal"` | populated |
| **HRP underutilizes → MVO equal-weight** | `"fallback_equal_weight"` | `"fallback_equal_weight"` | populated |
| HRP raised → MVO optimal | `"mvo_fallback_hrp_error"` | `"optimal"` | `None` |
| HRP raised → MVO equal-weight | `"fallback_equal_weight"` | `"fallback_equal_weight"` | `None` |

**Equal-weight collapse semantics — make this explicit in code reviews
and docs.** `weighting_method = "fallback_equal_weight"` describes the
**final outcome shown to the user/operator**. The pre-fallback routing
reason (cap-overshoot vs underutilized vs HRP-error) is **not preserved
in `weighting_method`** — it's only indirectly inferable from:
- `hrp_candidate_vol` (None ⇒ HRP-error path; populated ⇒ HRP did
  produce a candidate, so the entry path was either cap-overshoot or
  underutilized)
- the structured log (`hrp_error` field, plus the relative position of
  `hrp_candidate_vol` to `target_vol × LOWER` / `target_vol × UPPER`)

Anyone consuming the API who needs the original reason after a fallback
must reconstruct it from those signals or from logs. The API does not
preserve it.

**Schema changes.** None. `weighting_method: str | None` already
accommodates new string values. No frontend impact beyond the
methodology paragraph (§3).

**Logging.** The existing structured `portfolio_construction` log gains
one new field and renames one for symmetry:

```python
logger.info("portfolio_construction", extra={
    "hrp_candidate_vol": ...,
    "hrp_error": ...,
    "target_vol": target_vol,
    "lower_tolerance": HRP_LOWER_TOLERANCE,  # new
    "upper_tolerance": HRP_UPPER_TOLERANCE,  # renamed from "tolerance"
    "weighting_method": ...,
    "optimizer_status": ...,
})
```

The rename `tolerance` → `upper_tolerance` is a breaking change to the
structured log schema. Acceptable because (a) the log is one phase
old, (b) symmetry matters for log analysis going forward, and (c) any
log-consumer code needs updates anyway to surface
`mvo_underutilized`.

### 3 — Tests

**Two new integration tests.** Both go in
[backend/tests/test_pipeline_integration.py](../../../backend/tests/test_pipeline_integration.py)
following the existing pattern (mock `select_universe`, mock
`yf.download`, call `generate_portfolio`, assert metadata).

```python
def test_pipeline_mvo_underutilized_routes_to_mvo_optimal(...):
    """At risk_level=5 with the synthetic universe, HRP candidate vol
    (~7%) sits well below cap × LOWER (0.7 × 35% = 24.5%), so the new
    rule routes to MVO."""
    result = generate_portfolio(..., risk_level=5, ...)
    assert result["weighting_method"] == "mvo_underutilized"
    assert result["optimizer_status"] == "optimal"
    assert result["hrp_candidate_vol"] is not None  # HRP did produce a candidate

def test_pipeline_mvo_underutilized_with_optimizer_fallback(...):
    """Same routing trigger but mocked optimizer falls back. Verifies
    the equal-weight collapse semantics — weighting_method reflects the
    final outcome, optimizer_status mirrors it, and hrp_candidate_vol
    stays populated since HRP did produce a candidate."""
    result = generate_portfolio(..., risk_level=5, ...)
    assert result["weighting_method"] == "fallback_equal_weight"
    assert result["optimizer_status"] == "fallback_equal_weight"
    assert result["hrp_candidate_vol"] is not None
```

**Two existing test updates** to keep them on the intended HRP-win path
after the routing rule changes. **The original assertions are not
wrong** — the synthetic data is unchanged, the rule is what changed.
Without these `risk_level` bumps, the tests would (correctly) trigger
`mvo_underutilized` instead of `hrp`, defeating their purpose of
exercising the HRP-wins branch:

| Test | Current | Update to | Why |
|---|---|---|---|
| `test_pipeline_hrp_wins_on_synthetic_data` | `risk_level=3` | `risk_level=1` | At cap 8%, the synthetic ~7% HRP vol lands inside the [5.6%, 8.8%] HRP-wins band |
| `test_pipeline_holdings_carry_is_defensive_flag` | `risk_level=2` | `risk_level=1` | Same reason — at risk_level=1 HRP wins and defensives stay in the HRP output |

Other existing tests using `risk_level=3`
(`test_pipeline_end_to_end_includes_covariance_metadata`,
`test_pipeline_is_reproducible`, `test_pipeline_changes_with_inputs`,
`test_pipeline_drops_low_volume_ticker_from_holdings`) don't check
`weighting_method` and continue to pass — they exercise pipeline
mechanics that aren't affected by which routing branch wins.

### 4 — Methodology page

Replace the current HRP paragraph in
[frontend/src/methodology/MethodologyPage.tsx](../../../frontend/src/methodology/MethodologyPage.tsx)
with the plain-English two-sided framing. No "risk budget" jargon — the
user just needs to know that the system actively tries to match their
stated risk level:

> *Weighting.* By default we use **Hierarchical Risk Parity (HRP)** —
> a clustering-based method that spreads risk across groups of stocks
> that tend to move together. HRP tends to produce more stable,
> diversified portfolios than classical mean-variance optimization,
> especially when expected-return estimates are noisy. We then check
> whether HRP's portfolio matches your chosen risk level. If HRP comes
> out much riskier than your profile allows, we fall back to
> mean-variance optimization to bring volatility down. If HRP comes
> out much more conservative than your profile, we likewise fall back
> to mean-variance optimization so the portfolio better matches the
> risk level you selected.

### 5 — Validation script and calibration guardrail

Two updates to
[backend/scripts/validate_hrp.py](../../../backend/scripts/validate_hrp.py):

**1. Calibration guardrail check.** After the existing TABLE 1
(routing distribution), report HRP's share of the synthetic sweep.
Phrased as an informational guardrail, not a PASS/FAIL — calibration
trigger, not product invariant:

```
HRP win rate on synthetic sweep: X%
  (If consistently below ~30%, revisit HRP_LOWER_TOLERANCE calibration.
   This threshold reflects the current synthetic data generator;
   if the generator changes materially, recalibrate alongside.)
```

**2. Re-evaluate criterion 2 (TABLE 5).** Should now PASS — risk
levels 1–5 produce meaningfully different portfolios because MVO
honors a different cap at most levels.

**Expected outcomes for the current synthetic generator** (calibration
expectations, not hard invariants — if the generator changes, these
recalibrate too):

- TABLE 1: HRP win rate in the ~30–50% range; both `mvo_underutilized`
  and `mvo_risk_cap` populated
- TABLE 4: 5 meaningfully differentiated portfolios for the 5 risk
  levels — non-trivial L1 deltas between adjacent levels, not
  byte-inequality for its own sake
- TABLE 5: 5/5 PASS

If the HRP win rate falls materially below 30% on the current
generator, the lower tolerance is over-tight and needs loosening
toward 0.6 or 0.5. If it stays well above 50%, the rule isn't
biting — consider tightening LOWER toward 0.8.

## Out of scope (this iteration)

- **Per-risk-level tolerance dicts** (Approach 2 from brainstorming).
  Single `LOWER` and `UPPER` constants for now. If observed routing
  reveals a single value can't satisfy all 5 levels, revisit then.
- **Sharpe-based or utility-based picking between HRP and MVO.** The
  current decision is purely vol-budget-based; we don't compare
  risk-adjusted returns. Adds compute and invites a definition fight
  ("better by what measure?").
- **Continuous interpolation between HRP and MVO weights** (e.g.
  linearly blend by where HRP vol sits in the band). Sharper
  boundaries are easier to debug; blending is a YAGNI lift unless the
  discrete switching produces user-visible artifacts.
- **Backtesting whether the new routing actually improves realized
  outcomes.** Natural P6 — once differentiation is restored we can
  finally measure whether HRP/MVO routing produces better portfolios
  on historical data.
- **Frontend visual indicator of which routing branch fired.** The
  information is in the API (`weighting_method`); a UI badge or
  explanation can come later.
- **Persisting `weighting_method` to the database.** Same status as
  `is_defensive` — exposed on the API for live generations, not
  stored. A user re-fetching a portfolio created before P5 will get
  `weighting_method=None`. Acceptable.
