# HRP Validation Findings

**Date:** 2026-04-18
**Validation script:** [backend/scripts/validate_hrp.py](../../../backend/scripts/validate_hrp.py)
**Spec:** [2026-04-18-portfolio-construction-design.md](../specs/2026-04-18-portfolio-construction-design.md)
**Plan:** [2026-04-18-portfolio-construction.md](../plans/2026-04-18-portfolio-construction.md)

## Summary

P3 (HRP + MVO hybrid) is **functionally successful** with one **clear UX
limitation** for low-risk profiles. All four routing paths fire correctly
on real-shaped data; one assertion bug was found and fixed mid-validation.
The classical claim that "HRP is more stable than MVO" did not reproduce
in our setup — the real value of HRP here is that it doesn't depend on
noisy expected-return estimates, not raw weight stability.

## Findings

### 1. Assertion bug fixed and locked by regression test

The pipeline's `assert abs(weights_array.sum() - 1.0) < 1e-8` fired in
production whenever HRP overshot the cap and MVO ran on a real-sized
universe. Root cause: `optimize_portfolio` rounds weights to 4 decimals
before returning, so the sum drifts by up to `n × 5e-5` — well above the
1e-8 tolerance for any realistic universe size. The 16/16 test suite
hadn't caught it because every test used a 10-ticker fixture with equal
weights `[0.1] × 10`, which round cleanly to sum=1.0.

**Fix:** renormalize `weights_array = weights_array / weights_array.sum()`
in both MVO branches in [backend/app/engine/pipeline.py](../../../backend/app/engine/pipeline.py).
The post-block assertion stays strict, so any genuinely broken state
still surfaces loudly.

**Regression test:** `test_pipeline_mvo_fallback_weights_sum_to_one_with_large_universe`
in [backend/tests/test_pipeline_integration.py](../../../backend/tests/test_pipeline_integration.py)
forces the cap-overshoot path with a 30-ticker universe — exactly the size
class that exposed the bug. 17/17 tests pass.

### 2. Hybrid routing works as designed

Across 45 synthetic portfolios (5 risk levels × 3 universe sizes ×
3 correlation regimes):

| weighting_method | count | pct |
|---|---|---|
| `hrp` | 26 | 58% |
| `mvo_risk_cap` | 2 | 4% |
| `mvo_fallback_hrp_error` | 0 | 0% |
| `fallback_equal_weight` | 17 | 38% |

The two `mvo_risk_cap` cases both occurred at the largest universe size
(60 tickers), where MVO has enough degrees of freedom to find a
genuinely lower-vol subset rather than degenerate to equal-weight. In
both, MVO solved cleanly and produced a portfolio at-or-just-under the
target cap (`hrp_vol=0.156, mvo_vol=0.120` against a `cap=0.12`; and
`hrp_vol=0.313, mvo_vol=0.249` against a `cap=0.25`). This is exactly
the controlled fallback behavior the spec promised.

The 38% `fallback_equal_weight` rate isn't a bug — it's the legitimate
algorithmic outcome when both HRP overshoots AND MVO can't satisfy the
cap with the available universe. See finding #5.

### 3. HRP is not obviously more stable than capped MVO

On apples-to-apples cases (where both produced real solutions, n=28),
under a ±5% covariance perturbation:

- HRP mean L1 weight delta: **0.069**
- MVO mean L1 weight delta: **0.023**

So **MVO with the 20% per-asset cap was ~3x more stable than HRP**
under perturbation. The likely explanation: the cap forces MVO toward
near-equal-weight when the optimization is loose, and equal-weight is
maximally stable to perturbations. HRP, by contrast, genuinely
re-clusters when correlations shift, producing more weight movement.

This contradicts the textbook framing of HRP as a stability fix for MVO.
But the textbook critique of MVO is about *unconstrained* MVO — once you
add the 20% per-asset cap (which we already do), the worst MVO
pathologies are already mostly defused.

### 4. The actual value of HRP here is robustness to noisy μ

The reason we still picked HRP isn't perturbation stability — it's that
HRP **doesn't depend on expected-return estimates at all**. It builds the
allocation from covariance structure alone. MVO requires a μ vector,
which in our pipeline comes from a single XGBoost regressor with a
limited feature set — the kind of estimate that's well-known to be noisy
and to drive MVO into corner solutions.

That's the value proposition we're actually buying with HRP, and the
perturbation test doesn't measure it. To honestly evaluate HRP vs MVO
in our setup, we'd need a backtest that compares realized risk-adjusted
returns over historical data — see "Recommended next phase" below.

### 5. Low-risk users currently collapse to equal-weight

The real-data spot check at all 5 risk levels with the live tech-only
universe (15 stocks, HRP candidate vol 21.6%):

| risk_level | weighting_method | risk_score |
|---|---|---|
| 1 | `fallback_equal_weight` | 30.88 |
| 2 | `fallback_equal_weight` | 30.88 |
| 3 | `fallback_equal_weight` | 30.88 |
| 4 | `hrp` | 21.61 |
| 5 | `hrp` | 21.61 |

For risk levels 1–3, HRP overshoots the cap (8%, 12%, 18% vs. an HRP
candidate of 21.6%), and MVO can't bring vol low enough either, so the
pipeline falls back to equal-weight (each holding gets ~6.7%). The user
gets the same equal-weight portfolio whether they pick "very
conservative" or "moderate" — which makes the risk-level slider
effectively meaningless for half the user base.

This is a **product limitation, not an algorithm bug**. The root cause
is that the available universe (15 tech stocks) doesn't contain
defensive enough assets to satisfy a low-vol cap. To serve low-risk
users meaningfully, the universe needs to include bonds, treasuries,
defensive sectors, or otherwise lower-vol holdings.

## Recommended next phase

Three reasonable follow-ons surfaced from this validation:

| Option | What it does | Effort | Impact |
|---|---|---|---|
| A. Backtesting / evaluation | Walk-forward simulation comparing HRP vs MVO on realized historical returns | Medium-high (data, framework, metrics) | Validates whether HRP actually pays off in practice — could justify or undermine P3 |
| B. Broader / defensive asset universe | Add bonds, treasuries, defensive sectors so low-risk profiles get tailored portfolios | Low-medium (data ingestion + universe selector tweak) | Fixes a current real user-facing failure (the equal-weight collapse for risk 1–3) |
| C. Predictor improvements | Improve the XGBoost μ estimator (more features, regularization, ensembling) | High and open-ended | Reduces the underlying noise that drove us to HRP in the first place |

**Recommendation: B (broader universe) next.**

Three reasons:

1. **It addresses the only concrete user-facing failure surfaced by this
   validation.** Conservative users currently get a portfolio that
   ignores their risk preference. That's a worse user experience than
   not having those risk levels at all.
2. **It's a prerequisite for A.** A backtest of HRP vs MVO on a universe
   that collapses to equal-weight at half the risk profiles will produce
   noisy, hard-to-interpret results. We want a working risk slider
   before we measure how well it performs.
3. **It's tightly scopable.** Concrete deliverable: add a small set of
   defensive ETFs (e.g. AGG, BND, GLD, VPU) to the universe, verify
   risk_levels 1–3 now produce meaningfully different and tailored
   portfolios. No new infrastructure.

A (backtesting) is the natural follow-up after B — once the risk slider
works, we can evaluate whether HRP actually justifies its place in the
pipeline. C (predictor improvements) can wait until A tells us whether
the predictor is actually the bottleneck.
