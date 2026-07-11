"""
strategies.py
Three trading strategies, each returning a `Signal` column of target
positions: 1 = fully long, 0 = flat. The backtest engine shifts this by
one day before trading it, so signals here should reflect what you'd
decide to do using information available AS OF the close of that row
(no lookahead is introduced here; the engine handles the lag).
"""

import numpy as np
import pandas as pd

from strategy.indicators import add_all_indicators


def _require_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure indicator columns exist; compute them if the caller hasn't."""
    if "MACD" not in df.columns:
        df = add_all_indicators(df)
    return df


def trend_following_strategy(df: pd.DataFrame) -> pd.DataFrame:
    """
    Strategy 1: Trend Following (MACD + ADX)

    Buy/hold long when:  MACD > Signal  AND  ADX > 25
    Exit to flat when:   MACD < Signal
    """
    df = _require_indicators(df).copy()

    buy = (df["MACD"] > df["MACD_Signal"]) & (df["ADX"] > 25)
    sell = df["MACD"] < df["MACD_Signal"]

    position = pd.Series(np.nan, index=df.index)
    position[buy] = 1
    position[sell] = 0
    position = position.ffill().fillna(0)

    df["Signal"] = position.astype(int)
    df["Buy_Marker"] = buy & (position.diff() == 1)
    df["Sell_Marker"] = sell & (position.diff() == -1)
    return df


def mean_reversion_strategy(df: pd.DataFrame) -> pd.DataFrame:
    """
    Strategy 2: Mean Reversion (RSI + Bollinger Bands)

    Buy when:   RSI < 30  AND  Close < BB_Lower
    Sell when:  RSI > 70  OR   Close > BB_Upper
    """
    df = _require_indicators(df).copy()

    buy = (df["RSI"] < 30) & (df["Close"] < df["BB_Lower"])
    sell = (df["RSI"] > 70) | (df["Close"] > df["BB_Upper"])

    position = pd.Series(np.nan, index=df.index)
    position[buy] = 1
    position[sell] = 0
    position = position.ffill().fillna(0)

    df["Signal"] = position.astype(int)
    df["Buy_Marker"] = buy & (position.diff() == 1)
    df["Sell_Marker"] = sell & (position.diff() == -1)
    return df


def custom_strategy(df: pd.DataFrame) -> pd.DataFrame:
    """
    Strategy 3: Custom "Confirmed Trend" strategy.

    Combines three indicators across three different categories:
      - Trend:    EMA_20 vs EMA_50 (fast/slow crossover)
      - Momentum: RSI as an overbought/overheated filter
      - Volume:   OBV vs its own 20-day SMA, confirming volume supports the move

    Buy when:   EMA_20 > EMA_50  AND  RSI < 70  AND  OBV > OBV_SMA_20
    Sell when:  EMA_20 < EMA_50  OR   RSI > 80

    Rationale: only take the trend trade if it isn't already overheated
    (RSI filter) and if volume flow confirms genuine buying pressure
    (OBV filter), rather than trading the crossover blindly.
    """
    df = _require_indicators(df).copy()

    buy = (df["EMA_20"] > df["EMA_50"]) & (df["RSI"] < 70) & (df["OBV"] > df["OBV_SMA_20"])
    sell = (df["EMA_20"] < df["EMA_50"]) | (df["RSI"] > 80)

    position = pd.Series(np.nan, index=df.index)
    position[buy] = 1
    position[sell] = 0
    position = position.ffill().fillna(0)

    df["Signal"] = position.astype(int)
    df["Buy_Marker"] = buy & (position.diff() == 1)
    df["Sell_Marker"] = sell & (position.diff() == -1)
    return df


STRATEGIES = {
    "Trend Following": trend_following_strategy,
    "Mean Reversion": mean_reversion_strategy,
    "Custom (EMA+RSI+OBV)": custom_strategy,
}
