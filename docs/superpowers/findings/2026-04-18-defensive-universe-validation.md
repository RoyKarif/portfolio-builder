# Defensive Universe Validation Findings

**Date:** 2026-04-18
**Phase:** P4 (defensive universe auto-injection)
**Spec:** [2026-04-18-defensive-universe-design.md](../specs/2026-04-18-defensive-universe-design.md)
**Plan:** [2026-04-18-defensive-universe.md](../plans/2026-04-18-defensive-universe.md)
**Validation script:** [backend/scripts/validate_hrp.py](../../../backend/scripts/validate_hrp.py)

## Summary

P4 ships **successful with one known limitation**. The original
user-facing bug (equal-weight collapse for risk levels 1–3) is fixed.
4 of 5 success criteria from the spec pass. The remaining criterion
(risk-level differentiation within the conservative band) fails by
design — to fix it, we'd need to violate the explicit "no
optimizer/HRP changes" constraint that scoped this phase. The next
phase (option C from the previous findings note) addresses this
through risk-aware routing.

## Validation results

Real-data spot check (live yfinance, tech-only universe + auto-defensives):

| risk_level | weighting_method | risk_score | defensive_share | top 3 |
|---|---|---|---|---|
| 1 | hrp | 6.95 | 85.8% | AGG(33%), IEF(29%), XLP(10%) |
| 2 | hrp | 6.95 | 85.8% | AGG(33%), IEF(29%), XLP(10%) |
| 3 | hrp | 6.95 | 85.8% | AGG(33%), IEF(29%), XLP(10%) |
| 4 | hrp | 21.61 | 0.0% | MSFT(19%), CSCO(19%), IBM(17%) |
| 5 | hrp | 21.61 | 0.0% | MSFT(19%), CSCO(19%), IBM(17%) |

Success criteria from spec §5:

| # | Criterion | Result |
|---|---|---|
| 1 | No equal-weight collapse on risk_level 1–3 | **PASS** — all three produce HRP portfolios |
| 2 | Risk-level differentiation (≥2 of 3 pairs L1>0.10) | **FAIL** — L1 = 0.000 on all three pairs |
| 3 | Defensive share at risk_level=1 ≥ 30% | **PASS** — 85.8% |
| 4 | Defensive monotonicity (1 ≥ 2 ≥ 3) | **PASS** — all 85.8% (trivially) |
| 5 | No defensives in risk_level 4 or 5 | **PASS** — neither contains any |

**Overall: 4/5 PASS.**

## What worked

The original failure mode — risk levels 1, 2, 3 all collapsing to
equal-weight (15 holdings × 6.67%) on the tech-only universe — is
gone. Conservative profiles now get a sensible defensive portfolio
with ~86% in bonds/staples/utilities and ~7% annualized volatility.

The is_defensive flag flows correctly from universe → pipeline →
schema → API. Risk levels 4 and 5 see no defensives (criterion 5),
matching the spec's risk_level <= 3 cutoff.

## Known limitation: criterion 2 fails by design

Risk levels 1, 2, and 3 produce **byte-identical** portfolios. Root
cause: HRP doesn't take risk_level as input. With the augmented
universe (tech + 5 defensive ETFs), HRP naturally allocates ~86% to
bonds (the lowest-vol cluster), giving a portfolio with ~7% vol.
That sits below all three caps × 1.10 (8.8%, 13.2%, 19.8%), so all
three accept HRP and get the identical output.

This collides with two design constraints from the previous phase:

- **Spec §"No optimizer or HRP changes":** "Defensives enter the
  universe as additional assets and that's it. No floor weights,
  no asset-class constraints, no special sector caps, no HRP
  changes."
- **Brainstorming constraint #3:** "No special-casing inside the
  optimizer."

Honoring those constraints meant accepting that universe-level
changes alone can't differentiate the slider when HRP wins on a
risk-blind basis. The criterion 2 failure was foreseeable from the
spec's structure but worth verifying empirically before deciding to
revisit those constraints.

## Decision

Accept criterion 2 as a known limitation for this phase rather than
hack around it. Specifically reject:

- Repurposing `HRP_VOL_TOLERANCE` as a forced-MVO mechanism (would
  obscure the constant's stated purpose)
- Adding post-processing constraints to HRP weights (explicitly
  out of scope)

The next phase (P5) will address differentiation through risk-aware
routing — see [the proposed mini-spec](../specs/2026-04-19-risk-aware-routing-design.md)
when written.

Note: the differentiation problem isn't unique to risk levels 1–3.
Risk levels 4 and 5 also produce identical portfolios in the
real-data spot check (top 3: MSFT/CSCO/IBM both at 19/19/17%) for
the same root reason — HRP's risk-blind output. The proposed P5
spec should consider whether to address the entire slider or just
the conservative band.

## What ships in P4

The 4-out-of-5 result is shipped as the validation outcome. The
script ([backend/scripts/validate_hrp.py](../../../backend/scripts/validate_hrp.py))
honestly prints `OVERALL: 4/5 success criteria passing` rather than
hiding the failing criterion. Future runs will continue to show the
FAIL until P5 lands; that's intentional — the failing line is the
on-ramp to the next conversation about routing.
