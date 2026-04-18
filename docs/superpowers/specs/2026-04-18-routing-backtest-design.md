# Routing Backtest (Design Spec)

**Date:** 2026-04-18
**Status:** Approved (autonomous), ready for implementation
**Phase:** P6 (backtesting)

## Goal

Measure whether the P5 hybrid HRP/MVO routing actually improves
realized risk-adjusted returns vs simpler baselines on historical
data. Two earlier findings notes flagged this as the natural next
phase — see
[2026-04-18-hrp-validation.md](../findings/2026-04-18-hrp-validation.md)
"Recommended next phase" and
[2026-04-18-risk-aware-routing-validation.md](../findings/2026-04-18-risk-aware-routing-validation.md)
"What ships in P5".

The output is one walk-forward backtest comparing 4 strategies across
3 risk levels on a fixed universe over the last ~5 years of daily
prices. Same lightweight pattern as the validation script — one
script, stdout summary, plain-English findings note. No new
infrastructure.

## Architecture

### 1 — Scope (decisions made autonomously)

- **Universe:** Fixed list of 15 tickers — top 10 US tech (MSFT, AAPL,
  NVDA, GOOGL, AMZN, META, TSLA, AVGO, CSCO, IBM) plus the 5
  defensive ETFs from P4 (AGG, IEF, GLD, XLU, XLP). No point-in-time
  membership; if a ticker has shorter history than the backtest
  window, the script drops it from the universe rather than
  shortening the window.
- **Time period:** Last 5 years for evaluation, with a 2-year
  trailing window for fitting at each rebalance. Total data fetch:
  ~7 years.
- **Rebalance cadence:** Annual (5 rebalance points). Each rebalance
  uses the trailing 2-year window for fit, then evaluates on the
  next 1-year forward window.
- **Risk levels evaluated:** 1, 3, 5 (the three slider extremes —
  enough to see if the slider has a real effect on realized
  outcomes; intermediate levels can come later).
- **Strategies:** 4 per risk level:
  - `equal_weight` — 1/N baseline (independent of risk_level)
  - `hrp_only` — pure HRP, no fallback (independent of risk_level)
  - `mvo_only` — pure MVO at the risk_level cap, no HRP
  - `hybrid` — full P5 routing (HRP within band, MVO outside)
- **Metrics per (strategy, risk_level):**
  - Annualized return (geometric)
  - Annualized vol (realized)
  - Sharpe (rf=0)
  - Max drawdown
  - For hybrid: routing distribution across rebalances

### 2 — Implementation pattern

One script: `backend/scripts/backtest_routing.py`. Uses the existing
engine modules directly (no API call):
- `app.engine.hrp.hrp_weights` for HRP
- `app.engine.optimizer.optimize_portfolio` for MVO
- `app.engine.risk.estimate_covariance` for the cov matrix
- The P5 routing constants from `app.engine.pipeline`
  (`HRP_LOWER_TOLERANCE`, `HRP_UPPER_TOLERANCE`,
  `HRP_TOLERANCE_EPSILON`) for the hybrid path

The script replicates the pipeline's routing logic locally rather
than calling `generate_portfolio` — this avoids the predictor /
yfinance batch / database overhead and keeps the backtest's input
deterministic.

### 3 — Caveats (deliberately accepted for v1)

Documented inline in the script's module docstring and called out
in the findings note:

- **Sample-mean expected returns for MVO**, not the XGBoost
  predictor. Using the production predictor would introduce
  training-data leakage in a backtest (the predictor was trained on
  data the test claims to be evaluating). Sample mean is the
  simplest defensible alternative. HRP doesn't use μ so isn't
  affected.
- **No transaction costs.** Annual rebalancing means costs would be
  small but non-zero. Out of scope for v1.
- **No survivorship adjustment.** The universe is the current set
  of US tech leaders + defensive ETFs. A backtest 5 years ago would
  have looked different (TSLA in 2020 was a different company than
  TSLA in 2025). This biases all four strategies the same way, so
  relative comparisons are still meaningful even though absolute
  numbers are optimistic.
- **Single universe.** Tech + defensives only. Doesn't model
  sector-rotation users or non-US users.
- **Annual rebalancing.** Quarterly or monthly would give more
  observations per strategy. Annual keeps the script simple and the
  total compute small.

### 4 — Output

Two stdout tables:

```
TABLE A — Per-strategy annualized metrics across all eval windows
strategy        risk  annual_ret  annual_vol  sharpe   max_dd
equal_weight    1     X.X%        X.X%        X.XX     X.X%
hrp_only        1     X.X%        X.X%        X.XX     X.X%
mvo_only        1     X.X%        X.X%        X.XX     X.X%
hybrid          1     X.X%        X.X%        X.XX     X.X%
... (repeat for risk_level 3 and 5)

TABLE B — Hybrid routing distribution
risk_level  hrp  mvo_risk_cap  mvo_underutilized  fallback_equal_weight
1           N    N             N                  N
3           N    N             N                  N
5           N    N             N                  N
```

Plus a findings note (`docs/superpowers/findings/2026-04-18-routing-backtest.md`)
summarizing what the numbers tell us about whether the hybrid
routing earns its keep.

### 5 — Success criteria

The backtest is **descriptive, not prescriptive**. There is no
PASS/FAIL — the script prints metrics and the findings note
interprets them. Specifically, the question "is hybrid better than
HRP-only or MVO-only?" doesn't have a clean answer; what we want is
the data so we can decide what (if anything) to change in the
routing constants.

The work is "done" when:
- The script runs end-to-end on the live universe
- Both tables print clean numbers (no NaN, no exceptions in any cell)
- A findings note interprets the result and proposes the next phase
  (or lack thereof)

## Out of scope (this iteration)

- Transaction-cost modeling
- Point-in-time universe membership (delisted/added tickers over the
  backtest window)
- Sub-annual rebalancing
- Multi-universe / multi-country / multi-sector backtests
- Backtest of the predictor's contribution (would need a separate
  walk-forward train/predict cycle — large)
- Statistical significance testing (would need many more
  observations than 5 rebalances per strategy)
- Frontend display of backtest results
