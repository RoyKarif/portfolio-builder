# Defensive Universe for Low-Risk Profiles (Design Spec)

**Date:** 2026-04-18
**Status:** Approved, ready for implementation plan
**Phase:** P4 (defensive universe)

## Goal

Fix the user-facing UX failure surfaced in the
[HRP validation findings](../findings/2026-04-18-hrp-validation.md):
risk levels 1–3 currently collapse to equal-weight portfolios because
the live tech-only universe (HRP candidate vol ~21.6%) overshoots the
caps for those risk levels (8%, 12%, 18%). The risk slider is effectively
meaningless for half the user base.

Auto-inject a small fixed set of defensive ETFs into the universe when
the user's `risk_level <= 3`. Higher risk levels never see them. No
changes to HRP, MVO, or the optimizer — defensives just enter the
universe as additional assets and the existing construction logic
chooses among them.

## Architecture

### 1 — Defensive ETF list (hardcoded in code)

Add a module-level constant in [backend/app/engine/universe.py](../../../backend/app/engine/universe.py):

```python
DEFENSIVE_ETFS: list[dict] = [
    {"ticker": "AGG", "company_name": "iShares Core US Aggregate Bond ETF",
     "sector": "Bonds", "exchange": "", "is_defensive": True},
    {"ticker": "IEF", "company_name": "iShares 7-10 Year Treasury Bond ETF",
     "sector": "Bonds", "exchange": "", "is_defensive": True},
    {"ticker": "GLD", "company_name": "SPDR Gold Trust",
     "sector": "Commodities", "exchange": "", "is_defensive": True},
    {"ticker": "XLU", "company_name": "Utilities Select Sector SPDR Fund",
     "sector": "Utilities", "exchange": "", "is_defensive": True},
    {"ticker": "XLP", "company_name": "Consumer Staples Select Sector SPDR Fund",
     "sector": "Consumer Staples", "exchange": "", "is_defensive": True},
]
```

**Fixed and explicit for v1.** No dynamic discovery, no "best ETF in
category" logic, no API calls to find substitutes. The list is part of
the source code; changing it is a code change. This is intentional: it
keeps the rule transparent and reviewable, and avoids a class of failure
modes (data feed returns garbage, picks a thinly-traded ETF, etc.) we
don't want to debug today.

The five ETFs cover three distinct risk-reduction mechanisms:
- **Duration / fixed income:** AGG (broad investment-grade), IEF (intermediate treasury)
- **Real-asset / inflation hedge:** GLD
- **Defensive equity:** XLU (utilities), XLP (consumer staples)

This gives HRP enough material to form meaningful clusters
(`{AGG, IEF}`, `{XLU, XLP}`, `{GLD}` standalone) at low risk levels.

### 2 — Auto-injection rule

Modify `select_universe` in [backend/app/engine/universe.py](../../../backend/app/engine/universe.py)
to accept a new `risk_level: int` parameter and append the defensive ETFs
when `risk_level <= 3`:

```python
def select_universe(
    country: str,
    sectors: list[str],
    include_tickers: list[str],
    exclude_tickers: list[str],
    risk_level: int,
) -> list[dict]:
    ...existing logic builds `result` from sector picks + include_tickers...

    # Auto-inject defensive ETFs for conservative-to-moderate profiles.
    # Appended to the existing selection, never replaces user's sector picks.
    if risk_level <= 3:
        for etf in DEFENSIVE_ETFS:
            if etf["ticker"] in excluded or etf["ticker"] in seen:
                continue
            seen.add(etf["ticker"])
            result.append(etf)

    return result
```

The pipeline ([backend/app/engine/pipeline.py](../../../backend/app/engine/pipeline.py))
needs the one-line change to pass `risk_level` through:

```python
stocks = select_universe(
    country=country,
    sectors=preferred_sectors,
    include_tickers=include_tickers,
    exclude_tickers=exclude_tickers,
    risk_level=risk_level,
)
```

**Three behavioral guarantees:**

1. **Append, not replace.** Defensives are added to whatever the user
   selected; they don't displace any sector picks or include_tickers.
2. **Dedup on `seen`.** If the user explicitly includes one of the
   defensive ETFs (e.g. `include_tickers=["GLD"]`), it's already in the
   `seen` set by the time the auto-inject loop runs, so the loop skips
   it. No duplicates in the universe. The existing `seen` logic in
   `select_universe` handles this naturally — the auto-inject loop
   reuses the same set.
3. **Honors `exclude_tickers`.** A user who explicitly excludes "AGG"
   doesn't get it back via auto-injection.

### 3 — Transparency

Each defensive ETF dict carries `is_defensive: True`; regular stocks
get `is_defensive: False` (added in `_get_sector_tickers_with_meta` and
in the `include_tickers` branch of `select_universe`). The flag flows
all the way through:

**Engine result** ([backend/app/engine/pipeline.py](../../../backend/app/engine/pipeline.py)):
each holding dict in the `holdings` list gets `is_defensive: bool`,
read from the stock metadata.

**API schema** ([backend/app/schemas/portfolio.py](../../../backend/app/schemas/portfolio.py)):
`HoldingResponse` gains `is_defensive: bool = False`. The default makes
it backward-compatible with portfolios stored before this change.

**API response wiring** ([backend/app/api/portfolios.py](../../../backend/app/api/portfolios.py)):
the existing `HoldingResponse(**h)` spread already passes the field
through unchanged for the generate endpoint. The `get_portfolio`
endpoint's manual construction needs one new line.

**Stable sector labels.** The defensive ETFs use descriptive sector
strings (`"Bonds"`, `"Commodities"`, `"Utilities"`, `"Consumer
Staples"`) rather than reusing the user-facing sector picker codes.
This means downstream display logic that groups by sector continues to
work correctly — it'll just show new groups for these ETFs instead of
mis-labeling them.

**Methodology page** ([frontend/src/methodology/MethodologyPage.tsx](../../../frontend/src/methodology/MethodologyPage.tsx)):
add one paragraph in the "Choosing Stocks" section:

> *Defensive assets for conservative profiles.* If you pick a
> conservative-to-moderate risk level (1, 2, or 3), we automatically
> add a small set of defensive assets to your portfolio's candidate
> pool: broad investment-grade bonds (AGG), intermediate Treasuries
> (IEF), gold (GLD), and defensive equity (utilities XLU and consumer
> staples XLP). These don't replace your sector choices — they're
> added alongside them, giving the optimizer the option to use them
> when a low risk cap requires reducing volatility. Higher risk
> profiles (4 and 5) don't include them automatically, since they
> conflict with an aggressive growth target.

The frontend can later use `is_defensive` to add a visual badge in
the holdings table; that's a UI iteration, not part of this spec.

## No optimizer or HRP changes

Defensives enter the universe as additional assets and that's it. No
floor weights, no asset-class constraints, no special sector caps, no
HRP changes. The existing pipeline (HRP-first, MVO fallback,
`MAX_SINGLE_WEIGHT = 0.20`) operates on the augmented universe with no
modification. The hypothesis is that with defensives available, HRP
will cluster them naturally and the resulting portfolio vol will fit
under the low-risk caps without intervention.

If this proves wrong (e.g. HRP weights defensives so heavily it
dominates the portfolio at high risk levels — though high risk levels
don't see defensives, so this can't happen), we revisit in a follow-up
phase.

## Success criteria

Five concrete checks. The validation script
[backend/scripts/validate_hrp.py](../../../backend/scripts/validate_hrp.py)
gets a small extension to evaluate them on the live tech universe + auto-defensives.

1. **No more equal-weight collapse on standard inputs.** On the live
   tech-only universe (the same `preferred_sectors=["Technology"]` used
   by today's spot check), risk levels 1, 2, 3 produce
   `weighting_method` ∈ {`"hrp"`, `"mvo_risk_cap"`}. Not
   `"fallback_equal_weight"`.

2. **Risk-level differentiation.** The portfolios at risk_level 1, 2, 3
   are meaningfully different from each other. Concrete numeric
   threshold (L1 weight delta or defensive-share gap) is **calibrated
   empirically during implementation against observed runs** — the
   principle is "the slider has to actually do something different at
   each setting", not a specific number we're committing to up front.
   Today the three are byte-identical, so any non-trivial difference
   is a win; we'll set the threshold once we see what the actual
   spread looks like.

3. **Defensive allocation present at low risk.** The sum of weights on
   `{AGG, IEF, GLD, XLU, XLP}` at risk_level 1 is ≥ 30%. (Below 30%
   would suggest the optimizer isn't actually using the defensives we
   added, which would defeat the point.)

4. **Defensive monotonicity.** Defensive-weight share at risk_level 1
   ≥ risk_level 2 ≥ risk_level 3. Allow small inversions of < 5pp;
   the trend matters more than strict ordering. (Risk_levels 4 and 5
   never see defensives by construction, so this only applies to 1–3.)

5. **No regression at high risk.** Risk_levels 4 and 5 see the **same
   universe composition** as today (no defensive ETFs in their
   candidate pool). We don't promise byte-identical portfolio output —
   upstream price-data noise can shift weights by tiny amounts between
   runs — but the universe-selection step must produce the same
   ticker set it did before this change.

After implementation, the validation script's real-data spot check
table should show four meaningful changes:
- Risk_levels 1, 2, 3 produce different portfolios from each other
  (today they're identical)
- `weighting_method` for those rows shifts off `fallback_equal_weight`
- Some defensive ETFs appear in the holdings tables at low risk
- Risk_levels 4 and 5 rows are unchanged

## Out of scope (this iteration)

- **Explicit "Defensive" sector option** in the picker UI. Auto-injection
  alone fixes the surfaced bug; a sector option adds a second path for
  the same feature with no evidence of demand for finer control. Easy
  to add later if needed.
- **Floor weights or asset-class constraints** in the optimizer. Per
  user constraint #3.
- **Per-country defensive lists.** AGG/IEF/GLD/XLU/XLP are US-listed.
  Non-US users currently get a US universe by default (see
  `country_data.py` fallback) so this works for them too in practice,
  but a properly localized defensive list (e.g. UK gilt ETFs for GB
  users) is a separate phase.
- **Visual defensive badge in the frontend holdings table.** The
  `is_defensive` flag is exposed on the API; rendering it in the UI is
  a follow-up.
- **Backtesting HRP-with-defensives vs HRP-without.** The validation
  spot check confirms the routing/UX fix works; whether the resulting
  portfolios outperform on realized historical returns is the natural
  Phase B-follow-on (option A from the findings note).
