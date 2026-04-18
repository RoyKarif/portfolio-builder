# Richer Routing Backtest (Design Spec)

**Date:** 2026-04-18
**Status:** Approved (autonomous), ready for implementation
**Phase:** P7 (richer backtest)

## Goal

The P6 backtest left ambiguous whether the hybrid routing's
underperformance reflects the routing rule itself, the small sample
size (5 obs per cell), the single tech-heavy universe, or the
single 2019–2024 market regime. P7 widens the test along all three
axes — multi-sector universe, quarterly rebalancing, two distinct
4-year windows — to see if the conclusion holds.

The user's explicit direction:
> "I do NOT want to continue tuning the routing logic at this stage.
> The issue is not in the routing — it's that we don't yet have a
> strong enough source of alpha to justify more complex allocation.
> Next step should be focus on improving the return signal
> (predictor), not the allocator. Before that, agree we should run
> a more realistic backtest (Phase B): larger universe, multiple
> sectors, periodic rebalancing, proper walk-forward."

P7 is the "more realistic backtest" piece. The predictor improvement
work that follows it is a separate phase.

## Architecture

### 1 — Scope (decisions made autonomously)

- **Universe:** 35 tickers across 6 sectors plus the 5 defensive
  ETFs from P4. Curated for liquidity and history-back-to-2014:
  - **Tech (5):** MSFT, AAPL, NVDA, GOOGL, AMZN
  - **Healthcare (5):** JNJ, UNH, LLY, MRK, PFE
  - **Energy (5):** XOM, CVX, COP, SLB, OXY
  - **Finance (5):** JPM, BAC, WFC, GS, BLK
  - **Consumer (5):** HD, NKE, MCD, SBUX, LOW
  - **Industrial (5):** BA, CAT, HON, UPS, RTX
  - **Defensives (5):** AGG, IEF, GLD, XLU, XLP

- **Rebalance cadence:** **Quarterly** (4× per year). Weights from
  one rebalance are held until the next; the strategy's daily
  return stream is the concatenation of (held weights × asset
  returns) over the entire window.

- **Time windows:** Two distinct 4-year evaluation windows so we
  can see if results are regime-dependent:
  - **Window 1: 2016-01-01 to 2019-12-31** (pre-pandemic, "normal"
    rates + tech leadership)
  - **Window 2: 2021-01-01 to 2024-12-31** (post-COVID recovery,
    2022 bond/stock drawdown, 2023–2024 mega-cap rally)
  - Each window has 16 quarterly rebalances.
  - 2020 is deliberately excluded (anomalous COVID crash + recovery
    in a single year).
  - 2-year trailing window for fitting at each rebalance, so the
    full data fetch is 2014-01-01 to 2024-12-31 (~11 years).

- **Strategies:** Same 4 as P6 (`equal_weight`, `hrp_only`,
  `mvo_only`, `hybrid`) at same 3 risk levels (1, 3, 5).

- **Metrics:** Same as P6 (annualized return, vol, Sharpe, max
  drawdown), but reported **per window** so we can compare
  regime-by-regime.

### 2 — What's deliberately NOT changed from P6

- **Sample-mean μ for MVO.** Production XGBoost predictor
  walk-forward retraining is the next phase (P8 if the user picks
  that direction). For P7, we want to isolate the universe / cadence
  / regime variables from the μ-source variable.
- **Same 4 strategies, same 3 risk levels.** No new strategies
  introduced; the goal is to test the existing comparison on
  richer data.
- **No transaction costs.** Quarterly rebalancing makes costs
  larger than P6's annual but still small in relative terms.

### 3 — Implementation

Same script `backend/scripts/backtest_routing.py`, modified rather
than duplicated. The P6 version is preserved in git history; the
script's "current behavior" is the richer P7 backtest. Re-running
will produce P7 numbers, not P6 numbers.

Key code changes from P6:
- `UNIVERSE` constant expanded from 15 to 35 tickers.
- New `WINDOWS` constant: list of `(start, end)` date pairs.
- Rebalance cadence: `pd.DateOffset(months=3)` instead of
  `pd.DateOffset(years=1)`.
- Eval pattern: hold-until-next-rebalance, concat daily returns
  per strategy across the entire window. Replaces the P6 pattern
  where each rebalance had its own independent 1-year forward
  window.
- `main()` loops over windows; TABLE A is printed per-window plus
  a combined-windows aggregate row at the bottom.

### 4 — Output

```
Window 1 (2016-2019):
TABLE A — Per-strategy annualized metrics
[same format as P6]

Window 2 (2021-2024):
TABLE A — Per-strategy annualized metrics
[same format as P6]

Combined (both windows):
TABLE A — Per-strategy annualized metrics
[same format as P6]

TABLE B — Hybrid routing distribution (counts across rebalances, both windows combined)
```

### 5 — Success criteria

Same as P6 — descriptive, no PASS/FAIL. The goal is to see whether
the P6 conclusions hold under richer conditions.

Specifically, the findings note should answer:

1. **Does hybrid still underperform pure MVO at risk_level 1** when
   the universe is sector-diversified instead of tech-heavy?
2. **Does the conclusion change between regimes?** Pre-pandemic vs
   post-COVID windows might tell different stories.
3. **Does HRP-only still under-utilize the risk budget** at higher
   risk levels with a richer universe? With non-tech sectors and
   defensives, HRP's diversification logic has more material to
   work with.
4. **Does equal-weight still dominate** on risk-adjusted basis?

The answers determine the next phase:
- If hybrid still doesn't add value across both regimes and richer
  universe: confirms the user's hypothesis that the allocator is
  not the bottleneck and we should move to predictor improvements.
- If hybrid suddenly looks much better: evidence that universe
  composition matters, and routing recalibration becomes worth
  revisiting before predictor work.

## Out of scope

- **Predictor walk-forward retraining for MVO** — separate phase.
- **Transaction-cost modeling** — accept the assumption.
- **More than 2 windows** — 2 is enough to detect regime-dependence;
  more would be diminishing returns.
- **Sub-quarterly rebalancing** — would dramatically increase
  rebalance count but signal-to-noise ratio per rebalance drops.
- **Survivorship adjustment** — the universe is fixed throughout
  the backtest, biased toward currently-known names. Same caveat
  as P6.
- **Statistical significance testing** — even at 32 rebalances per
  strategy/risk-level cell (16 × 2 windows), formal hypothesis
  testing on Sharpe ratios would need much more data. Continue to
  treat numbers as descriptive, not conclusive.
