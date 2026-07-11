import logging

import pandas as pd

from data import connector
from data.data_loader import load_daily_bars

log = logging.getLogger("pipeline")

def fetch_universe_history(tickers, years=5):
    """Return {ticker: daily OHLCV DataFrame}, skipping any that fail."""
    history = {}
    for symbol in tickers:
        try:
            df = load_daily_bars(symbol, years=years)
            history[symbol] = df
            last = df.iloc[-1]
            log.info("HISTORY %s: %d bars, last close %.2f, vol %d",
                     symbol, len(df), last["Close"], int(last["Volume"]))
        except Exception as e:
            log.warning("HISTORY %s failed: %s", symbol, e)
    return history

def fetch_live_prices(tickers, feed="iex"):
    """Return {ticker: last trade price}, skipping any that fail."""
    prices = {}
    for symbol in tickers:
        try:
            trade = connector.get_latest_trade(symbol, feed=feed)
            prices[symbol] = trade["price"]
            log.info("LIVE %s: last price %.2f", symbol, trade["price"])
        except Exception as e:
            log.warning("LIVE %s failed: %s", symbol, e)
    return prices

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    universe = ["AAPL", "MSFT", "SPY"]
    hist = fetch_universe_history(universe, years=1)
    print({k: v.shape for k, v in hist.items()})
    print(fetch_live_prices(universe))
