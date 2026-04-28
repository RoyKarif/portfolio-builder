"""Return computation from raw price series.

We use *log-returns*, defined as:

    r_t = ln(P_t / P_{t-1})

Three reasons to prefer log-returns over simple returns ((P_t/P_{t-1}) - 1):

1. **Time-additive.** Total log-return over N days is the sum of daily
   log-returns: ln(P_N / P_0) = sum_t ln(P_t / P_{t-1}). For simple
   returns you have to multiply (1+r_t), which is messier.

2. **Closer to normal distribution.** This is the assumption that
   underlies our Monte Carlo simulator. log-returns are typically more
   symmetric and bell-shaped than simple returns.

3. **Standard in quant finance.** Anything you read in a textbook uses
   log-returns. Familiarity for interviewers.
"""

import numpy as np
import pandas as pd


def daily_log_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Convert a DataFrame of prices into log-returns.

    Input shape:
        index = date
        columns = tickers
        values = closing prices

    Output shape:
        index = date (one shorter than input — first row is NaN, dropped)
        columns = tickers
        values = ln(P_t / P_{t-1})

    Example:
        prices.iloc[0] = [100.0, 50.0]   # day 0
        prices.iloc[1] = [101.0, 49.0]   # day 1
        result.iloc[0] ≈ [0.00995, -0.02020]  # ln(101/100), ln(49/50)
    """
    return np.log(prices / prices.shift(1)).dropna()
