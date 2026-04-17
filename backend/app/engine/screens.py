import logging
from datetime import date

import pandas as pd

logger = logging.getLogger(__name__)

MIN_ADV_USD = 10_000_000
MIN_HISTORY_FRACTION = 0.95
ADV_LOOKBACK_DAYS = 30
MIN_RECENT_OBSERVATIONS = 10


def apply_quality_screen(
    batch: pd.DataFrame,
    tickers: list[str],
    cov_cutoff: date,
) -> tuple[dict[str, pd.Series], list[dict]]:
    """Filter `tickers` by liquidity (30d ADV) and history completeness,
    using the already-downloaded yfinance batch. Returns the surviving
    tickers' Close series in input order, plus a list of drop records."""
    price_data: dict[str, pd.Series] = {}
    dropped: list[dict] = []

    # Build the empirical cov-window calendar from the batch's union date
    # index restricted to >= cov_cutoff.
    if isinstance(batch.index, pd.DatetimeIndex):
        cov_window_dates = batch.index[batch.index.date >= cov_cutoff]
    else:
        cov_window_dates = pd.DatetimeIndex([])
    cov_window_size = len(cov_window_dates)

    for ticker in tickers:
        try:
            close = batch[ticker]["Close"]
            volume = batch[ticker]["Volume"]
        except (KeyError, ValueError):
            dropped.append({
                "ticker": ticker,
                "reasons": ["missing_data"],
                "adv_30d_usd": None,
                "history_fraction": 0.0,
            })
            continue

        panel = pd.DataFrame({"close": close, "volume": volume})
        panel = panel[panel.index.date >= cov_cutoff]
        usable = panel.dropna(how="any")

        if cov_window_size == 0:
            dropped.append({
                "ticker": ticker,
                "reasons": ["sparse_history"],
                "adv_30d_usd": None,
                "history_fraction": 0.0,
            })
            continue

        history_fraction = len(usable) / cov_window_size
        reasons: list[str] = []

        # Trailing ADV_LOOKBACK_DAYS calendar rows from the cov window,
        # then keep only the usable (non-NaN) rows within that slice.
        recent_window = panel.tail(ADV_LOOKBACK_DAYS)
        recent = recent_window.dropna(how="any")
        if len(recent) < MIN_RECENT_OBSERVATIONS:
            adv_30d_usd = None
            reasons.append("insufficient_recent_data")
        else:
            adv_30d_usd = float((recent["close"] * recent["volume"]).mean())
            if adv_30d_usd < MIN_ADV_USD:
                reasons.append("low_adv")

        if history_fraction < MIN_HISTORY_FRACTION:
            reasons.append("sparse_history")

        if reasons:
            dropped.append({
                "ticker": ticker,
                "reasons": reasons,
                "adv_30d_usd": adv_30d_usd,
                "history_fraction": history_fraction,
            })
            continue

        price_data[ticker] = usable["close"]

    logger.info(
        "quality_screen kept=%d dropped_low_adv=%d dropped_sparse=%d dropped_recent=%d dropped_missing=%d",
        len(price_data),
        sum(1 for d in dropped if "low_adv" in d["reasons"]),
        sum(1 for d in dropped if "sparse_history" in d["reasons"]),
        sum(1 for d in dropped if "insufficient_recent_data" in d["reasons"]),
        sum(1 for d in dropped if "missing_data" in d["reasons"]),
    )
    for d in dropped:
        logger.debug("quality_screen drop %s", d)

    return price_data, dropped
