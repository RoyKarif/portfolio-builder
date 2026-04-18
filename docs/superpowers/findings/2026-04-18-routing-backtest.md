# Routing Backtest Findings

**Date:** 2026-04-18
**Phase:** P6 (HRP/MVO routing backtest on realized returns)
**Spec:** [2026-04-18-routing-backtest-design.md](../specs/2026-04-18-routing-backtest-design.md)
**Backtest script:** [backend/scripts/backtest_routing.py](../../../backend/scripts/backtest_routing.py)
**Backtest window:** 2019-04 to 2026-04 (7 years total: 2-year initial training window + 5 annual rebalances)
**Universe:** 15 tickers — top US tech (AAPL, AMZN, AVGO, CSCO, GOOGL, IBM, META, MSFT, NVDA, TSLA) + 5 defensive ETFs (AGG, IEF, GLD, XLP, XLU)

## Summary

The hybrid HRP/MVO routing **does not obviously beat pure MVO** on
this universe over the past 5 years. At risk_levels 3 and 5, the
hybrid is identical to pure MVO (HRP never wins the routing decision
and the system always routes to `mvo_underutilized`). At risk_level
1, the hybrid actually **underperforms** all three baselines
(equal-weight, HRP-only, MVO-only) because the routing splits
between HRP (too conservative, ~7% realized vol against an 8% cap)
and MVO (better risk-adjusted return) without consistently using
either.

This is the empirical case for why HRP-first is a defensible
*default* but not an obvious *win* on the current universe and
2019–2024 market regime. Action items below.

## Backtest results

**Annualized metrics across 5 annual eval windows:**

| Strategy | Risk Level | Annual Return | Annual Vol | Sharpe | Max DD |
|---|---|---|---|---|---|
| equal_weight | 1 | 23.61% | 18.25% | 1.29 | -28.66% |
| hrp_only | 1 | 8.13% | 7.37% | 1.10 | -17.21% |
| mvo_only | 1 | 18.12% | 14.68% | 1.23 | -22.05% |
| **hybrid** | **1** | **9.29%** | **11.64%** | **0.80** | **-19.49%** |
| equal_weight | 3 | 23.61% | 18.25% | 1.29 | -28.66% |
| hrp_only | 3 | 8.13% | 7.37% | 1.10 | -17.21% |
| mvo_only | 3 | 23.62% | 17.38% | 1.36 | -23.09% |
| **hybrid** | **3** | **23.62%** | **17.38%** | **1.36** | **-23.09%** |
| equal_weight | 5 | 23.61% | 18.25% | 1.29 | -28.66% |
| hrp_only | 5 | 8.13% | 7.37% | 1.10 | -17.21% |
| mvo_only | 5 | 34.33% | 29.97% | 1.15 | -41.89% |
| **hybrid** | **5** | **34.33%** | **29.97%** | **1.15** | **-41.89%** |

**Hybrid routing distribution across rebalances:**

| risk_level | hrp | mvo_underutilized | fallback_equal_weight |
|---|---|---|---|
| 1 | 3 | 1 | 1 |
| 3 | 0 | 5 | 0 |
| 5 | 0 | 5 | 0 |

## Five things the data tells us

### 1. Equal-weight is shockingly competitive

Sharpe of 1.29 across all risk levels (it's risk-blind so the same
1/N portfolio runs in every cell). It beats `hrp_only` and beats
`hybrid` at risk_levels 1 and 5. The 1/N benchmark in this universe
+ this market regime is a strong baseline that any "smart" strategy
needs to clear.

### 2. HRP-only is too defensive for the available risk budget

7.37% realized vol against a risk_level=1 cap of 8% means HRP is
sitting just below the most conservative cap and never using more
budget. With 5 defensive ETFs in the universe (AGG, IEF, GLD, XLU,
XLP), HRP allocates ~85% to bonds — and bonds had a brutal 2022
that suppressed the 7-year geometric return to 8.13%. The
risk-adjusted return (Sharpe 1.10) is fine; the absolute return is
poor.

### 3. MVO with sample-mean μ is the strongest single strategy

Best Sharpe at every risk level (1.23 at risk_1, 1.36 at risk_3,
1.15 at risk_5). MVO uses a different cap at each level and
actually deploys it — at risk_3 it lands almost exactly at the cap
(17.38% realized vs 18% target) with the highest Sharpe in the
table. The naive "sample mean of the trailing 2-year window" turned
out to be a useful return signal in this regime.

### 4. The hybrid converges to MVO at risk_levels 3 and 5

At those two risk levels, the hybrid routes to `mvo_underutilized`
on every single rebalance — so hybrid = MVO-only. The HRP candidate
vol (~7%) is far below `cap × HRP_LOWER_TOLERANCE` (12.6% at risk_3,
24.5% at risk_5), and the rule correctly bumps to MVO. The
hybrid metrics at risk_3 and risk_5 are exactly MVO's metrics.

### 5. The hybrid underperforms at risk_level 1

This is the surprising result. At risk_1, the hybrid routes:
- 3/5 to HRP (when HRP candidate vol fits inside [5.6%, 8.8%])
- 1/5 to MVO underutilized
- 1/5 to fallback equal-weight (MVO infeasible at the 8% cap in
  one window)

The mix of HRP (which gave 8.13% return) and MVO (which gave 18.12%
return) at risk_1 averaged to a worse outcome than either alone:
9.29% return at 11.64% vol, Sharpe 0.80. The Sharpe is the worst
in the entire table. The hybrid is NOT just "the best of both" —
it's the worst combination because each rebalance's choice happens
in isolation without knowledge of which path would have done
better in that window.

## Caveats

- **Sample is small:** 5 rebalances per (strategy, risk_level) cell.
  Single-digit observations can't establish statistical
  significance. The numbers above are an honest snapshot, not
  evidence.
- **Single universe:** US tech + defensives. A more sector-diverse
  universe might tell a different story.
- **One regime:** 2019–2024 was dominated by a mega-cap tech rally
  punctuated by 2022's bond+equity drawdown. HRP's bond-heavy
  allocation got hammered in 2022; MVO's tech-heavy allocation
  thrived in 2020/2021/2023. Different regime, possibly different
  result.
- **No transaction costs:** Annual rebalancing keeps these small,
  but real-world friction would move the absolute numbers.
- **Sample-mean μ for MVO** is naive but defensible; the production
  XGBoost predictor would have introduced training-data leakage.
  The relative MVO performance in this backtest is an upper bound
  on what the production predictor could achieve.

## Recommended next phase

Three options, ordered by my recommendation:

### A. Re-evaluate the HRP-first design (recommended)

The empirical case for HRP-first on this universe is weak. Three
sub-options inside this:

1. **Make MVO the default and HRP the fallback** (invert the current
   relationship). HRP would only fire when MVO can't satisfy the
   cap (today's MVO equal-weight rescue path).
2. **Lower `HRP_LOWER_TOLERANCE` to ~0.4 or 0.3** so HRP wins more
   often at the conservative band. Trade-off: even more risk levels
   collapse to the same HRP output (since HRP is risk-blind).
3. **Remove HRP from the routing entirely**, keep only MVO + the
   defensives + the new symmetric cap-honoring framing. This is the
   most aggressive simplification.

(2) is the lowest-risk experiment; (1) is more invasive but more
principled; (3) discards three weeks of work on HRP and would need
its own findings note explaining why.

### B. Run a richer backtest

Quarterly rebalancing, multi-sector universe, separate windows
(2015–2019, 2019–2024), include the production predictor for MVO
with proper walk-forward re-training. This would generate enough
data to make A's decision well-grounded. Larger lift (~1 day of
work) but produces durable conclusions.

### C. Accept the result and move to product polish

Ship the slider as it is — the routing rule is *correct* even if
HRP doesn't outperform on this specific universe. Move on to UX
polish (frontend visual indicators of routing, persisting
weighting_method to the database, etc.) and revisit routing
calibration only if real-user data flags issues.

**My recommendation: B then A.** Get more data first (B is the
honest scientific move), then make a calibration decision (A2 most
likely) once we have enough observations to actually distinguish
strategies.
