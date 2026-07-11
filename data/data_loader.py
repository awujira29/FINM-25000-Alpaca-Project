"""
data_loader.py
Wraps connector.get_bars to pull multi-year daily OHLCV history for a
user-selected ticker and return it as a clean, indexed Pandas DataFrame.
"""

import pandas as pd
from data import connector

DEFAULT_TICKERS = ["AAPL", "MSFT", "SPY", "QQQ", "NVDA"]


def load_daily_bars(symbol: str, years: int = 5, feed: str = "iex") -> pd.DataFrame:
    """
    Download `years` years of daily OHLCV bars for `symbol` from Alpaca
    and return a DataFrame indexed by date with columns:
    Open, High, Low, Close, Volume.
    """
    symbol = symbol.strip().upper()
    days = int(years * 365.25)

    bars = connector.get_bars(symbol, timeframe="1Day", days=days, feed=feed)
    if not bars:
        raise ValueError(
            f"No bars returned for {symbol}. Check the ticker symbol, your "
            f"Alpaca API keys, and that the market has traded in this window."
        )

    df = pd.DataFrame(bars)
    df["t"] = pd.to_datetime(df["t"], utc=True).dt.tz_convert("America/New_York")
    df = df.set_index("t").sort_index()
    df = df.rename(columns={"o": "Open", "h": "High", "l": "Low", "c": "Close", "v": "Volume"})
    df = df[["Open", "High", "Low", "Close", "Volume"]]

    # Alpaca sometimes returns duplicate bars across pagination boundaries.
    df = df[~df.index.duplicated(keep="first")]

    return df
