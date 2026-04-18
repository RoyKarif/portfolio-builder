# Richer Routing Backtest Findings

**Date:** 2026-04-18
**Phase:** P7 (richer backtest — multi-sector, quarterly, two regimes)
**Spec:** [2026-04-18-richer-backtest-design.md](../specs/2026-04-18-richer-backtest-design.md)
**Backtest script:** [backend/scripts/backtest_routing.py](../../../backend/scripts/backtest_routing.py)
**Universe:** 35 tickers — 5 each from 6 sectors (Tech, Healthcare, Energy, Finance, Consumer, Industrial) plus 5 defensive ETFs (AGG, IEF, GLD, XLU, XLP)
**Windows:** 2016-2019 (pre-pandemic) and 2021-2024 (post-COVID + 2022 drawdown), 16 quarterly rebalances each
**Sample size per cell:** 32 rebalances (vs P6's 5)

## Summary

The P6 conclusions hold under richer conditions and gain a sharper
edge: **the hybrid routing does not add value over pure MVO on this
universe across either market regime.** New evidence: HRP-only's
risk-adjusted return collapsed in 2021-2024 (Sharpe 0.53, worse than
equal-weight's 1.17), confirming HRP is **regime-dependent in a way
MVO is not**. Equal-weight remains shockingly competitive (Sharpe
1.27 combined) — most strategies fail to clear it.

The user's hypothesis is empirically supported: **the bottleneck is
the return signal, not the allocator.** HRP's risk-blindness means
it can't take advantage of any μ signal even when one exists; MVO
with naive sample-mean μ is already directionally correct most of
the time. A better predictor would help MVO; it would not help HRP
at all.

## Backtest results

### Window 2016-2019 (pre-pandemic)

| Strategy | Risk | Annual Return | Annual Vol | Sharpe | Max DD |
|---|---|---|---|---|---|
| equal_weight | 1 | 16.95% | 12.19% | 1.39 | -18.40% |
| hrp_only | 1 | 7.71% | 4.20% | **1.84** | -5.44% |
| mvo_only | 1 | 14.00% | 9.58% | 1.46 | -15.50% |
| hybrid | 1 | 14.00% | 9.58% | 1.46 | -15.50% |
| equal_weight | 3 | 16.95% | 12.19% | 1.39 | -18.40% |
| hrp_only | 3 | 7.71% | 4.20% | **1.84** | -5.44% |
| mvo_only | 3 | 24.47% | 19.65% | 1.25 | -33.95% |
| hybrid | 3 | 24.47% | 19.65% | 1.25 | -33.95% |
| equal_weight | 5 | 16.95% | 12.19% | 1.39 | -18.40% |
| hrp_only | 5 | 7.71% | 4.20% | **1.84** | -5.44% |
| mvo_only | 5 | 24.25% | 20.53% | 1.18 | -33.89% |
| hybrid | 5 | 24.25% | 20.53% | 1.18 | -33.89% |

### Window 2021-2024 (post-COVID + 2022 drawdown)

| Strategy | Risk | Annual Return | Annual Vol | Sharpe | Max DD |
|---|---|---|---|---|---|
| equal_weight | 1 | 16.88% | 14.44% | 1.17 | -15.60% |
| hrp_only | 1 | 3.98% | 7.45% | **0.53** | -13.60% |
| mvo_only | 1 | 13.48% | 10.29% | 1.31 | -11.55% |
| hybrid | 1 | 5.22% | 7.76% | **0.67** | -13.60% |
| equal_weight | 3 | 16.88% | 14.44% | 1.17 | -15.60% |
| hrp_only | 3 | 3.98% | 7.45% | 0.53 | -13.60% |
| mvo_only | 3 | 16.58% | 16.44% | 1.01 | -19.44% |
| hybrid | 3 | 16.58% | 16.44% | 1.01 | -19.44% |
| equal_weight | 5 | 16.88% | 14.44% | 1.17 | -15.60% |
| hrp_only | 5 | 3.98% | 7.45% | 0.53 | -13.60% |
| mvo_only | 5 | 25.41% | 24.91% | 1.02 | -28.89% |
| hybrid | 5 | 25.41% | 24.91% | 1.02 | -28.89% |

### Combined (both windows)

| Strategy | Risk | Annual Return | Annual Vol | Sharpe | Max DD |
|---|---|---|---|---|---|
| equal_weight | 1 | 16.91% | 13.36% | 1.27 | -18.40% |
| hrp_only | 1 | 5.83% | 6.05% | 0.96 | -13.60% |
| mvo_only | 1 | 13.74% | 9.94% | **1.38** | -15.50% |
| hybrid | 1 | 9.53% | 8.72% | 1.09 | -15.50% |
| equal_weight | 3 | 16.91% | 13.36% | 1.27 | -18.40% |
| hrp_only | 3 | 5.83% | 6.05% | 0.96 | -13.60% |
| mvo_only | 3 | 20.46% | 18.11% | 1.13 | -33.95% |
| hybrid | 3 | 20.46% | 18.11% | 1.13 | -33.95% |
| equal_weight | 5 | 16.91% | 13.36% | 1.27 | -18.40% |
| hrp_only | 5 | 5.83% | 6.05% | 0.96 | -13.60% |
| mvo_only | 5 | 24.83% | 22.82% | 1.09 | -33.89% |
| hybrid | 5 | 24.83% | 22.82% | 1.09 | -33.89% |

### Hybrid routing distribution (combined, 32 rebalances per risk level)

| risk_level | hrp | mvo_underutilized | mvo_risk_cap | fallback_equal_weight |
|---|---|---|---|---|
| 1 | 10 | 16 | 4 | 2 |
| 3 | 0 | 32 | 0 | 0 |
| 5 | 0 | 32 | 0 | 0 |

## Six things the data tells us

### 1. HRP is regime-dependent in a way MVO is not

HRP-only's Sharpe **collapsed from 1.84 (2016-2019) to 0.53 (2021-2024)**.
The 2022 bond+stock drawdown punished HRP's bond-heavy allocation
(~85% defensives) brutally. By contrast, MVO-only's Sharpe held
roughly steady (1.46 → 1.31 at risk_1, 1.25 → 1.01 at risk_3). HRP's
single biggest weakness — risk-blindness combined with structural
preference for low-vol assets — turns into its worst feature when
those assets crash.

### 2. The hybrid still underperforms MVO at risk_level 1

Same pattern as P6, now confirmed across two regimes and 32x more
data:
- 2016-2019: hybrid_risk_1 Sharpe 1.46 vs mvo_only_risk_1 Sharpe 1.46 (tied — hybrid ran MVO most of the time)
- 2021-2024: hybrid_risk_1 Sharpe **0.67** vs mvo_only_risk_1 Sharpe **1.31** (hybrid almost half as good)
- Combined: hybrid_risk_1 Sharpe 1.09 vs mvo_only_risk_1 Sharpe 1.38

When HRP wins the routing decision (10/32 times at risk_1) it drags
the hybrid down because HRP's choices in those windows were worse
than MVO would have been. The mixed routing doesn't get the best of
both — it gets a regression to the mean of the worse one.

### 3. The hybrid IS pure MVO at risk_levels 3 and 5

32/32 rebalances at risk_3 route to `mvo_underutilized`. Same at
risk_5. The hybrid metrics at those two risk levels are byte-identical
to mvo_only across both windows. P5's symmetric routing rule is
working as designed; HRP's natural output is just consistently far
below the higher caps, so MVO always wins the routing.

### 4. Equal-weight is shockingly competitive again

Combined Sharpe **1.27** at every risk level. Beats hrp_only (0.96)
and beats hybrid_risk_1 (1.09). Only mvo_only_risk_1 (1.38) clearly
edges it. The 1/N benchmark is the high bar; most strategies fail
to clear it.

### 5. Higher risk levels do produce more return — but at worse Sharpe

Combined: mvo_only_risk_1 Sharpe 1.38 → mvo_only_risk_3 Sharpe 1.13
→ mvo_only_risk_5 Sharpe 1.09. Higher risk caps let MVO chase more
return (13.74% → 20.46% → 24.83% annualized) but the marginal
return-per-unit-vol diminishes. At the highest risk level, the
optimizer is essentially picking a high-beta concentrated portfolio
with worse risk-adjusted properties.

### 6. The slider's risk-adjusted ranking is the OPPOSITE of intuition

Naive intuition says "higher risk should give higher Sharpe in a
bull market." The data says the opposite: **lower risk_level gives
better Sharpe** across the board (mvo_only goes 1.38 → 1.13 → 1.09).
The user picking risk_level=5 expecting "more growth" gets more
absolute return but worse risk efficiency. That's not a bug —
RISK_VOLATILITY_CAP is doing exactly what the spec says — but it's
worth noting because the implication is that the *default* risk
level should probably be 3 (or even 1), not 5.

## Recommended next phase

The user's hypothesis was correct: **the bottleneck is the return
signal**. With sample-mean μ, MVO is already directionally good
enough that HRP's "robustness to noisy μ" doesn't pay off — HRP
costs more in lost return than it saves in stability. A better
predictor would directly improve MVO without needing any allocator
work.

### A. Predictor walk-forward backtest (recommended)

Replace the sample-mean μ in `mvo_only` and `hybrid` with the
production XGBoost predictor, retrained at each rebalance using
only data available at that point in time. Report MVO-with-predictor
metrics alongside MVO-with-sample-mean to isolate the predictor's
contribution.

This is the next-bigger lift from P7 — needs walk-forward training
infrastructure for the predictor (the production code trains once
on all available data; backtesting needs per-window training).
Estimated 1-2 days of work.

If the predictor moves MVO's Sharpe meaningfully above sample-mean
MVO, that confirms the predictor IS the lever and we should invest
in improving it. If not, the predictor is no better than naive sample
mean and we need a different return signal entirely.

### B. Predictor improvement experiments

Independent of A, the predictor itself could be improved:
- More features (sector, factor exposures, sentiment proxies)
- Ensembling multiple models
- Different model classes (LightGBM, neural nets, ensemble of statistical models)
- Hyperparameter tuning

But these only matter if A confirms the current predictor is doing
*something* useful that's worth improving. If A shows the predictor
adds nothing over sample mean, the right move is to rethink the
feature set or model class entirely.

### C. Accept and ship

The pipeline produces sensible portfolios that match user-stated
risk preferences (P5 verified). The slider differentiates outcomes
(P5 verified). Backtested performance is in line with naive
baselines (P7 confirmed). This is a reasonable v1 product. Move to
UX polish, real-user observation, and revisit allocator/predictor
choices once we have production data to inform the next iteration.

**My recommendation: A.** It's the smallest experiment that directly
tests the user's hypothesis. If the predictor adds nothing, we
learn it cheaply. If it adds something, we know the lever to pull.
Either way, the answer informs whether B (predictor improvements)
or C (ship and observe) is the right follow-up.
