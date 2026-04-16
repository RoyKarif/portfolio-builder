from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from xgboost import XGBRegressor

from app.data.market import fetch_stock_data, fetch_stock_info


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    features = pd.DataFrame(index=df.index)
    features["return_5d"] = df["Close"].pct_change(5)
    features["return_21d"] = df["Close"].pct_change(21)
    features["return_63d"] = df["Close"].pct_change(63)
    features["volatility_21d"] = df["Close"].pct_change().rolling(21).std()
    features["volatility_63d"] = df["Close"].pct_change().rolling(63).std()
    features["momentum_63d"] = df["Close"] / df["Close"].shift(63) - 1
    features["sma_50_ratio"] = df["Close"] / df["Close"].rolling(50).mean()
    features["sma_200_ratio"] = df["Close"] / df["Close"].rolling(200).mean()
    features["volume_ratio_20d"] = df["Volume"] / df["Volume"].rolling(20).mean()
    return features.dropna()


def predict_returns(stocks: list[dict], db) -> list[dict]:
    end_date = datetime.utcnow().strftime("%Y-%m-%d")
    start_date = (datetime.utcnow() - timedelta(days=3 * 365)).strftime("%Y-%m-%d")

    results = []
    for stock in stocks:
        ticker = stock["ticker"]
        try:
            df = fetch_stock_data(ticker, start=start_date, end=end_date)
            if len(df) < 252:
                stock["expected_return"] = 0.0
                results.append(stock)
                continue

            info = fetch_stock_info(ticker)
            features = build_features(df)

            forward_return = df["Close"].pct_change(21).shift(-21)
            forward_return = forward_return.reindex(features.index).dropna()
            features = features.loc[forward_return.index]

            features["pe_ratio"] = info.get("pe_ratio") or 0.0
            features["pb_ratio"] = info.get("pb_ratio") or 0.0
            features["dividend_yield"] = info.get("dividend_yield") or 0.0

            X = features.values
            y = forward_return.values

            if len(X) < 50:
                stock["expected_return"] = 0.0
                results.append(stock)
                continue

            model = XGBRegressor(n_estimators=100, max_depth=4, learning_rate=0.05, random_state=42)
            model.fit(X[:-21], y[:-21])

            latest_features = X[-1:].copy()
            predicted_21d_return = float(model.predict(latest_features)[0])
            annual_return = (1 + predicted_21d_return) ** (252 / 21) - 1
            stock["expected_return"] = round(annual_return, 4)

        except Exception:
            stock["expected_return"] = 0.0

        results.append(stock)

    return results
