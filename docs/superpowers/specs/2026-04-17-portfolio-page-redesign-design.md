# Portfolio Page Redesign — Design Spec

**Date:** 2026-04-17
**Status:** Approved by user, ready for implementation planning

## Problem

The current portfolio experience has three gaps:

1. No way to delete a portfolio. Once created, it stays in the dashboard forever (`PATCH /portfolios/{id}/archive` exists but no UI exposes it).
2. The portfolio results page presents technical numbers (risk score 27%, expected return 53–130%, percentile values) without translation into language a beginner can act on.
3. There is no explanation of how predictions are produced. Beginners have no basis to trust or contextualize the numbers, and no education on what they mean.

## Goals

- Let users delete portfolios from both the dashboard and the portfolio page.
- Redesign the portfolio page so a complete beginner can answer "what do I own, what could I earn, how risky is it" within seconds.
- Add a methodology page that establishes credibility and educates without exposing implementation specifics.

## Non-Goals

- Improving prediction model quality (predictor still produces aggressive returns; that is a separate concern).
- Adding portfolio editing or rebalancing features.
- Per-stock deep dives (clicking a holding does not navigate anywhere new).

---

## Feature 1: Delete Portfolios

### UI

**Dashboard cards:** Each `PortfolioCard` shows a small trash icon button in its top-right corner, visible on hover. Clicking it stops link navigation and opens a confirmation modal.

**Portfolio page header:** Two buttons in the top-right area next to the page title:
- **Archive** — calls existing `PATCH /portfolios/{id}/archive`, returns user to dashboard. Reversible (just hides from active list).
- **Delete** — destructive, opens confirmation modal.

### Confirmation modal

Simple, two-button modal:
- Title: "Delete this portfolio?"
- Body: "This action cannot be undone. Your portfolio data and holdings will be permanently removed."
- Buttons: `Cancel` (gray) | `Delete` (red)

No "type the name" friction. The modal is enough.

### Backend

Add `DELETE /portfolios/{id}` endpoint:
- Authenticated, authorization-checked (user must own portfolio).
- Cascades to `portfolio_holdings` (and `portfolio_snapshots` if relevant).
- Returns 204 No Content.

Add `cascade="all, delete-orphan"` to the `Portfolio.holdings` relationship (and snapshots) so SQLAlchemy handles cleanup.

---

## Feature 2: Beginner-Friendly Portfolio Page Redesign

### Guiding principles

- **Lead with answers in plain English, not raw numbers.** Every numeric stat is accompanied by a one-sentence translation.
- **Tooltips for every technical term.** A small "?" icon next to each label opens a 1–2 sentence explanation. Powered by a shared `<InfoTooltip>` component.
- **Always sort holdings by allocation, descending.** The largest position is first; smallest is last. This applies to the holdings table, allocation chart legend, and any sector breakdown.
- **Display Monte Carlo percentiles, not the raw `expected_return_low/high`.** The optimizer's expected returns currently produce inflated headline numbers (~50–130%). Percentiles from the simulation are more grounded; we lead with those for user-facing scenarios. The raw percent range remains available behind tooltips for transparency.

### Layout (top to bottom)

```
┌──────────────────────────────────────────────────┐
│  ← Back to Dashboard         [Archive] [Delete]  │
├──────────────────────────────────────────────────┤
│  HERO CARD                                        │
│  "If you invest $10,000 today, in ~5 years        │
│   you could have between $7,800 and $15,400.      │
│   Most likely around $11,200."                    │
│   • horizon: 5 years • 10,000 simulations  [?]    │
└──────────────────────────────────────────────────┘

┌────────────────────────┬─────────────────────────┐
│  RISK CARD             │  DIVERSIFICATION CARD   │
│  "Medium risk ⚠️"      │  "Spread across 5       │
│  visual gauge (1-5)    │   sectors and 10 stocks"│
│  [?] tooltip           │  [?] tooltip            │
└────────────────────────┴─────────────────────────┘

┌──────────────────────────────────────────────────┐
│  WHAT YOU OWN                                     │
│  Pie chart (holdings) | Bar chart (sectors)       │
│  Both legends sorted by allocation desc.          │
└──────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────┐
│  YOUR STOCKS — sorted by allocation desc.         │
│  Ticker | Company | Sector | Allocation % | [?]   │
└──────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────┐
│  FUTURE SCENARIOS (Monte Carlo, simplified)       │
│  Three scenario boxes side-by-side:                │
│   "Bad years (10%)"  $X    icon: 📉                │
│   "Typical (50%)"    $Y    icon: 📊                │
│   "Good years (10%)" $Z    icon: 📈                │
│  Plus a horizontal range bar showing the spread.  │
└──────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────┐
│  📚 Want to know how we calculated this?         │
│         [Read the full methodology →]             │
└──────────────────────────────────────────────────┘
```

### Translation rules (technical → plain English)

| Technical value             | Beginner display                                            |
|-----------------------------|-------------------------------------------------------------|
| `risk_score: 27%`           | "Medium risk" + 1–5 gauge                                   |
| `risk_score < 15%`          | "Low risk"                                                  |
| `risk_score 15–35%`         | "Medium risk"                                               |
| `risk_score > 35%`          | "High risk"                                                 |
| `percentile_10`             | "Bad years (10% chance)" — $ amount                         |
| `percentile_50`             | "Typical scenario" — $ amount                               |
| `percentile_90`             | "Good years (10% chance)" — $ amount                        |
| `horizon_years: 4.0`        | "in about 4 years"                                          |
| `n_simulations: 10000`      | "based on 10,000 simulations"                               |
| `allocation_pct`            | Always shown as `X.X%` and proportional in pie/bar          |

### Sorting rule

`holdings` array MUST be sorted by `allocation_pct` descending in:
- The holdings table
- The allocation pie chart's slice order and legend
- Any tooltips listing positions

This is enforced in the frontend before render (sort once in `PortfolioPage` and pass sorted array to children).

### Components affected

- New: `<InfoTooltip text="..." />` — shared "?" icon with hover/click popover.
- New: `<HeroScenarioCard>` — the top card with plain-English summary.
- New: `<RiskGauge>` — 1–5 visual indicator with text label.
- New: `<DiversificationCard>` — sector + stock count summary.
- New: `<ScenarioGrid>` — three scenario boxes for Monte Carlo display.
- Update: `PortfolioPage` — new layout, sort holdings, add header buttons.
- Update: `AllocationChart`, `HoldingsTable` — accept pre-sorted holdings.
- Remove: `RiskComparison` (replaced by `<RiskGauge>` + hero card), `BacktestChart` (currently passes empty data — defer until real backtest data), `MonteCarloChart` (replaced by `<ScenarioGrid>`).

---

## Feature 3: Methodology Page (`/methodology`)

### Purpose

Establish credibility and educate. Communicate that the system uses real, well-known financial techniques without exposing implementation specifics (no library names, no feature lists, no hyperparameters, no model architecture).

### Tone

Friendly, plain-language, serious but not dry. Use everyday analogies. No academic jargon without inline definition.

### Sections

1. **The Big Picture** — A short overview and a simple flow diagram:
   `Your Profile → Choose Stocks → Predict Returns → Build Portfolio → Simulate Future`
2. **Choosing Stocks** — High-level: filtered to your country, your selected sectors, and large/liquid companies.
3. **Predicting Returns** — High-level: we apply machine learning to historical price patterns to estimate forward returns. Explicitly note this is a forecast, not a guarantee. **Do not mention specific features, model type, lookback window, or training details.**
4. **Building the Portfolio** — Explain the principle of mean-variance optimization in plain terms: balance return against risk, diversify across positions. Use a "don't put all your eggs in one basket" analogy.
5. **Simulating the Future** — Explain Monte Carlo: thousands of randomized future paths produce a distribution of outcomes. Explain what "10th / 50th / 90th percentile" mean.
6. **Important Limitations ⚠️** (prominent, can't-miss styling):
   - Past performance does not guarantee future results.
   - Forecasts can be wrong; markets can behave in unexpected ways.
   - This tool is for educational purposes — not financial advice.
   - Consult a licensed financial advisor before making real investment decisions.
7. **Glossary** — short definitions: Risk Score, Expected Return, Percentile, Sector, Diversification, Monte Carlo, Optimization.

### Integration with portfolio page

- Footer link on `PortfolioPage`: "📚 Want to know how we calculated this? Read the full methodology →"
- Each `<InfoTooltip>` on a technical stat ends with a "Learn more →" link to the relevant section anchor on `/methodology`.
- Header nav (in `Layout`) gains a "How it works" link.

### What we explicitly DO NOT reveal

- Specific Python libraries used (yfinance, cvxpy, xgboost).
- Exact features fed to the model.
- Model hyperparameters or architecture.
- Number of training samples, lookback windows, or rebalance frequencies.
- Exact universe construction (e.g. "top 15 from yfinance Sector").

The page communicates *what we do* and *why it makes sense*, not *how it is implemented*.

---

## Backend changes summary

1. New endpoint: `DELETE /portfolios/{id}` with cascade delete.
2. SQLAlchemy relationship: add `cascade="all, delete-orphan"` to `Portfolio.holdings` (and snapshots if applicable).
3. No new tables, no new columns.

## Frontend changes summary

1. New components: `InfoTooltip`, `HeroScenarioCard`, `RiskGauge`, `DiversificationCard`, `ScenarioGrid`, `ConfirmDeleteModal`.
2. New page: `MethodologyPage` at route `/methodology`.
3. Updated: `PortfolioPage` (new layout, sort, header buttons, footer link), `PortfolioCard` (delete button on hover), `Layout` (nav link to methodology), `App` (new route).
4. API client: add `deletePortfolio(id)` and `archivePortfolio(id)` helpers.

## Out of scope (explicitly)

- Improving prediction model quality.
- Per-stock detail pages.
- Historical backtest visualization (defer until real data).
- Comparing two portfolios side-by-side.
- Sharing or exporting portfolios.
- Notifications or alerts.

## Open risks

- `percentile_10/50/90` are dollar values; we will show them as currency. Confirmed by current `SimulationResponse` shape.
- The hero card numbers depend on `n_simulations > 0` and `horizon_years > 0`. Old portfolios created before the simulation-persistence fix may have nulls — display fallback message: "Simulation data not available for this portfolio."
- Tooltip popover library: prefer a simple custom component over adding a dependency.
