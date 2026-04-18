"""Validate the HRP + MVO hybrid portfolio construction.

Runs three pieces:

1. Synthetic sweep (45 portfolios): 5 risk levels x 3 universe sizes x 3
   correlation regimes. Reports routing distribution, stability under a
   small covariance perturbation, and concentration metrics. Compares
   pure-HRP against pure-MVO so we can see whether HRP buys us stability
   on identical inputs.

2. Real-data spot check: calls the actual pipeline once per risk level
   (5 portfolios) with the live universe + yfinance. Prints the
   construction outcome and top holdings for eyeballing.

3. CSV output: one row per (universe_size, corr_regime, risk_level)
   so we can compare runs over time.

Usage:
    cd backend && python scripts/validate_hrp.py

Requires the venv to have numpy, pandas, scipy, sklearn, cvxpy, xgboost,
yfinance, sqlalchemy, python-jose, passlib, bcrypt. Same set the test
suite needs.
"""
import csv
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Make the app/ package importable when running from anywhere.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.engine.hrp import hrp_weights
from app.engine.optimizer import RISK_VOLATILITY_CAP, optimize_portfolio
from app.engine.pipeline import HRP_VOL_TOLERANCE
from app.engine.risk import estimate_covariance


def generate_synthetic_returns(n_tickers: int, corr_regime: str, seed: int) -> pd.DataFrame:
    """Daily returns from a one-factor + idiosyncratic model with
    heterogeneous betas and idio vols across tickers.

    The corr_regime knob tunes the common-factor strength. Per-ticker beta
    in [0.5, 1.5] and per-ticker idio vol in [0.008, 0.020] give MVO room
    to find genuinely lower-vol subsets — without that heterogeneity, every
    ticker has identical variance and MVO can only diversify, not select.
    """
    rng = np.random.default_rng(seed)
    n_days = 520
    common_strength = {"low": 0.005, "medium": 0.012, "high": 0.025}[corr_regime]

    common = rng.normal(0.0003, common_strength, n_days)
    betas = rng.uniform(0.5, 1.5, n_tickers)
    idio_vols = rng.uniform(0.008, 0.020, n_tickers)
    cols = {}
    for i in range(n_tickers):
        idio = rng.normal(0.0, idio_vols[i], n_days)
        cols[f"T{i:02d}"] = betas[i] * common + idio
    return pd.DataFrame(cols)


def perturb_cov_psd(cov: np.ndarray, scale: float = 0.05, seed: int = 999) -> np.ndarray:
    """Apply small symmetric multiplicative noise to a covariance matrix
    and project back to PSD. cvxpy's DCP check is strict, so we clip
    eigenvalues to a small positive floor and explicitly symmetrize."""
    rng = np.random.default_rng(seed)
    n = cov.shape[0]
    noise = rng.normal(0, scale, (n, n))
    noise = (noise + noise.T) / 2
    perturbed = cov * (1 + noise)
    eigvals, eigvecs = np.linalg.eigh(perturbed)
    eigvals = np.maximum(eigvals, 1e-6)  # floor lifted so cvxpy accepts as PSD
    result = eigvecs @ np.diag(eigvals) @ eigvecs.T
    return (result + result.T) / 2  # kill FP asymmetry from the matmul


def annualized_vol(weights: np.ndarray, cov: np.ndarray) -> float:
    return float(np.sqrt(weights @ cov @ weights))


def concentration(weights: np.ndarray) -> dict:
    return {
        "max_weight": float(weights.max()),
        "eff_n": float(1.0 / np.sum(weights ** 2)),
        "n_positions": int((weights >= 0.01).sum()),
    }


def run_hrp(cov: np.ndarray, tickers: list[str]) -> tuple[np.ndarray | None, str | None]:
    try:
        w_dict = hrp_weights(cov, tickers)
        return np.array([w_dict[t] for t in tickers]), None
    except ValueError as e:
        return None, str(e)


def run_mvo(tickers, expected_returns, cov, risk_level) -> tuple[np.ndarray, str]:
    result = optimize_portfolio(tickers, expected_returns, cov, risk_level)
    weights = np.array([result["weights"].get(t, 0) for t in tickers])
    return weights, result["status"]


def hybrid_decision(hrp_vol, mvo_status, target_vol, hrp_error) -> str:
    """Replays the routing logic from app.engine.pipeline so we can label
    each portfolio without invoking the full pipeline machinery."""
    if hrp_error is not None:
        return "fallback_equal_weight" if mvo_status == "fallback_equal_weight" else "mvo_fallback_hrp_error"
    if hrp_vol <= target_vol * HRP_VOL_TOLERANCE:
        return "hrp"
    return "fallback_equal_weight" if mvo_status == "fallback_equal_weight" else "mvo_risk_cap"


def run_synthetic_sweep(out_csv: Path):
    risk_levels = [1, 2, 3, 4, 5]
    universe_sizes = [15, 30, 60]
    corr_regimes = ["low", "medium", "high"]

    rows = []
    routing_counts = {
        "hrp": 0,
        "mvo_risk_cap": 0,
        "mvo_fallback_hrp_error": 0,
        "fallback_equal_weight": 0,
    }

    for n_tickers in universe_sizes:
        for regime in corr_regimes:
            seed = abs(hash((n_tickers, regime))) % (2**32)
            returns = generate_synthetic_returns(n_tickers, regime, seed)
            cov, _, _ = estimate_covariance(returns)  # already annualized
            cov_perturbed = perturb_cov_psd(cov)
            tickers = list(returns.columns)
            expected_returns = returns.mean().values * 252  # naive annualized mean

            hrp_w, hrp_err = run_hrp(cov, tickers)
            hrp_w_p, _ = run_hrp(cov_perturbed, tickers)
            hrp_l1 = (
                float(np.abs(hrp_w - hrp_w_p).sum())
                if hrp_w is not None and hrp_w_p is not None
                else None
            )

            for risk_level in risk_levels:
                mvo_w, mvo_status = run_mvo(tickers, expected_returns, cov, risk_level)
                mvo_w_p, _ = run_mvo(tickers, expected_returns, cov_perturbed, risk_level)
                mvo_l1 = float(np.abs(mvo_w - mvo_w_p).sum())

                target_vol = RISK_VOLATILITY_CAP[risk_level]
                if hrp_err is None:
                    hrp_vol = annualized_vol(hrp_w, cov)
                    method = hybrid_decision(hrp_vol, mvo_status, target_vol, None)
                else:
                    hrp_vol = None
                    method = hybrid_decision(None, mvo_status, target_vol, hrp_err)
                routing_counts[method] += 1

                hrp_metrics = concentration(hrp_w) if hrp_w is not None else {}
                mvo_metrics = concentration(mvo_w)

                rows.append({
                    "n_tickers": n_tickers,
                    "corr_regime": regime,
                    "risk_level": risk_level,
                    "weighting_method": method,
                    "target_vol": round(target_vol, 4),
                    "hrp_vol": round(hrp_vol, 4) if hrp_vol is not None else None,
                    "mvo_vol": round(annualized_vol(mvo_w, cov), 4),
                    "mvo_status": mvo_status,
                    "hrp_l1_under_perturbation": round(hrp_l1, 4) if hrp_l1 is not None else None,
                    "mvo_l1_under_perturbation": round(mvo_l1, 4),
                    "hrp_max_weight": round(hrp_metrics.get("max_weight"), 4) if hrp_metrics else None,
                    "mvo_max_weight": round(mvo_metrics["max_weight"], 4),
                    "hrp_eff_n": round(hrp_metrics.get("eff_n"), 2) if hrp_metrics else None,
                    "mvo_eff_n": round(mvo_metrics["eff_n"], 2),
                    "hrp_n_positions": hrp_metrics.get("n_positions"),
                    "mvo_n_positions": mvo_metrics["n_positions"],
                })

    with open(out_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    return rows, routing_counts


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


def print_stability(rows):
    print("=" * 64)
    print("TABLE 2 — Stability under +/-5% covariance perturbation")
    print("        (mean L1 weight delta; lower = more stable)")
    print("=" * 64)
    df = pd.DataFrame(rows)
    hrp_l1 = df["hrp_l1_under_perturbation"].dropna()
    mvo_l1 = df["mvo_l1_under_perturbation"].dropna()
    print(f"{'method':<10} {'mean':>8} {'p50':>8} {'p90':>8} {'max':>8}")
    print("-" * 64)
    print(f"{'pure HRP':<10} {hrp_l1.mean():>8.3f} {hrp_l1.median():>8.3f} {hrp_l1.quantile(0.9):>8.3f} {hrp_l1.max():>8.3f}")
    print(f"{'pure MVO':<10} {mvo_l1.mean():>8.3f} {mvo_l1.median():>8.3f} {mvo_l1.quantile(0.9):>8.3f} {mvo_l1.max():>8.3f}")
    if mvo_l1.mean() > 0:
        ratio = mvo_l1.mean() / max(hrp_l1.mean(), 1e-9)
        print(f"\nMVO mean L1 is {ratio:.1f}x HRP mean L1.")
    print()


def print_concentration(rows):
    print("=" * 64)
    print("TABLE 3 — Concentration & diversification (means across sweep)")
    print("=" * 64)
    df = pd.DataFrame(rows)
    hrp = df.dropna(subset=["hrp_max_weight"])
    print(f"{'method':<10} {'max_w':>8} {'eff_N':>8} {'n_pos':>8}")
    print("-" * 64)
    print(f"{'pure HRP':<10} {hrp['hrp_max_weight'].mean():>8.3f} {hrp['hrp_eff_n'].mean():>8.1f} {hrp['hrp_n_positions'].mean():>8.1f}")
    print(f"{'pure MVO':<10} {df['mvo_max_weight'].mean():>8.3f} {df['mvo_eff_n'].mean():>8.1f} {df['mvo_n_positions'].mean():>8.1f}")
    print()

    flagged = hrp[
        (hrp["hrp_max_weight"] > 0.30)
        | (hrp["hrp_eff_n"] < 4)
        | (hrp["hrp_n_positions"] < 5)
    ]
    if len(flagged) > 0:
        print(f"FLAGGED HRP portfolios (max_w>0.30 OR eff_N<4 OR n_pos<5): {len(flagged)} of {len(hrp)}")
        for _, r in flagged.head(8).iterrows():
            print(
                f"  n={r['n_tickers']:>2} regime={r['corr_regime']:<6} risk={r['risk_level']} "
                f"max_w={r['hrp_max_weight']:.3f} eff_N={r['hrp_eff_n']:.1f} "
                f"n_pos={int(r['hrp_n_positions'])}"
            )
    else:
        print("FLAGGED HRP portfolios: 0 (all within healthy bounds)")
    print()


def run_real_data_spot_check():
    print("=" * 64)
    print("TABLE 4 — Real-data spot check (live yfinance, 5 portfolios)")
    print("=" * 64)
    from app.engine.pipeline import generate_portfolio

    for risk_level in [1, 2, 3, 4, 5]:
        try:
            result = generate_portfolio(
                country="US",
                risk_level=risk_level,
                investment_horizon="3-5y",
                available_amount=10_000.0,
                target_return=10.0,
                preferred_sectors=["Technology"],
                include_tickers=[],
                exclude_tickers=[],
                db=None,
            )
        except Exception as e:
            print(f"risk_level={risk_level}: EXCEPTION — {type(e).__name__}: {e}")
            continue

        if "error" in result:
            print(f"risk_level={risk_level}: ERROR — {result['error']}")
            continue

        n_holdings = len(result["holdings"])
        top_3 = sorted(result["holdings"], key=lambda h: -h["allocation_pct"])[:3]
        top_str = ", ".join(f"{h['ticker']}({h['allocation_pct']:.1f}%)" for h in top_3)
        hrp_cand = result.get("hrp_candidate_vol")
        hrp_cand_str = f"{hrp_cand:.4f}" if hrp_cand is not None else "n/a"
        print(
            f"risk_level={risk_level} method={result['weighting_method']:<22} "
            f"risk_score={result['risk_score']:>5.2f} "
            f"hrp_cand={hrp_cand_str:>7} n_holdings={n_holdings:>2}"
        )
        print(f"               top 3: {top_str}")
    print()


def main():
    out_csv = Path(__file__).parent / "validate_hrp_results.csv"
    print(f"Writing per-portfolio CSV to: {out_csv}\n")

    rows, routing_counts = run_synthetic_sweep(out_csv)
    total = sum(routing_counts.values())

    print_routing(routing_counts, total)
    print_stability(rows)
    print_concentration(rows)

    run_real_data_spot_check()


if __name__ == "__main__":
    main()
