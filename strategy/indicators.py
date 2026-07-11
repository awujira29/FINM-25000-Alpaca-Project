"""
indicators.py
Technical indicators used by the backtesting strategies.

Implements 8 indicators spanning all four requested categories:
  Trend:      SMA, EMA, MACD, ADX
  Momentum:   RSI
  Volatility: Bollinger Bands, ATR
  Volume:     OBV

All functions take/return pandas Series (or a DataFrame with OHLCV columns)
and are side-effect free.
"""

import numpy as np
import pandas as pd


# --------------------------------------------------------------------------
# Trend
# --------------------------------------------------------------------------

def sma(series: pd.Series, window: int = 20) -> pd.Series:
    """Simple Moving Average."""
    return series.rolling(window=window, min_periods=window).mean()


def ema(series: pd.Series, window: int = 20) -> pd.Series:
    """Exponential Moving Average."""
    return series.ewm(span=window, adjust=False, min_periods=window).mean()


def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """
    Moving Average Convergence Divergence.
    Returns (macd_line, signal_line, histogram).
    """
    ema_fast = ema(series, fast)
    ema_slow = ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def adx(df: pd.DataFrame, window: int = 14) -> pd.Series:
    """
    Average Directional Index. Requires columns: High, Low, Close.
    Measures trend strength (not direction).
    """
    high, low, close = df["High"], df["Low"], df["Close"]

    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    plus_dm = pd.Series(plus_dm, index=df.index)
    minus_dm = pd.Series(minus_dm, index=df.index)

    tr = true_range(df)
    atr_smooth = tr.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()

    plus_di = 100 * (plus_dm.ewm(alpha=1 / window, adjust=False, min_periods=window).mean() / atr_smooth)
    minus_di = 100 * (minus_dm.ewm(alpha=1 / window, adjust=False, min_periods=window).mean() / atr_smooth)

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    adx_series = dx.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    return adx_series


# --------------------------------------------------------------------------
# Momentum
# --------------------------------------------------------------------------

def rsi(series: pd.Series, window: int = 14) -> pd.Series:
    """Relative Strength Index (Wilder's smoothing)."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    avg_loss = loss.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


# --------------------------------------------------------------------------
# Volatility
# --------------------------------------------------------------------------

def bollinger_bands(series: pd.Series, window: int = 20, num_std: float = 2.0):
    """Returns (upper_band, middle_band, lower_band)."""
    mid = sma(series, window)
    std = series.rolling(window=window, min_periods=window).std()
    upper = mid + num_std * std
    lower = mid - num_std * std
    return upper, mid, lower


def true_range(df: pd.DataFrame) -> pd.Series:
    high, low, close = df["High"], df["Low"], df["Close"]
    prev_close = close.shift(1)
    ranges = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1)
    return ranges.max(axis=1)


def atr(df: pd.DataFrame, window: int = 14) -> pd.Series:
    """Average True Range. Requires columns: High, Low, Close."""
    tr = true_range(df)
    return tr.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()


# --------------------------------------------------------------------------
# Volume
# --------------------------------------------------------------------------

def obv(df: pd.DataFrame) -> pd.Series:
    """On-Balance Volume. Requires columns: Close, Volume."""
    direction = np.sign(df["Close"].diff()).fillna(0)
    return (direction * df["Volume"]).cumsum()


def add_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convenience function: returns a copy of `df` with every indicator
    used by the strategies attached as columns.
    """
    out = df.copy()

    out["SMA_20"] = sma(out["Close"], 20)
    out["SMA_50"] = sma(out["Close"], 50)
    out["EMA_20"] = ema(out["Close"], 20)
    out["EMA_50"] = ema(out["Close"], 50)
    out["EMA_200"] = ema(out["Close"], 200)

    macd_line, signal_line, hist = macd(out["Close"])
    out["MACD"] = macd_line
    out["MACD_Signal"] = signal_line
    out["MACD_Hist"] = hist

    out["ADX"] = adx(out)
    out["RSI"] = rsi(out["Close"])

    bb_upper, bb_mid, bb_lower = bollinger_bands(out["Close"])
    out["BB_Upper"] = bb_upper
    out["BB_Mid"] = bb_mid
    out["BB_Lower"] = bb_lower

    out["ATR"] = atr(out)
    out["OBV"] = obv(out)
    out["OBV_SMA_20"] = sma(out["OBV"], 20)

    return out
