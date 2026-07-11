import os 
import requests
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone

Base = "https://data.alpaca.markets/v2/stocks"

load_dotenv()

HEADERS = {
    "APCA-API-KEY-ID": os.environ["ALPACA_API_KEY"],
    "APCA-API-SECRET-KEY": os.environ["ALPACA_SECRET_KEY"],
}

def get_bars(symbol, timeframe="1day", days=1825, feed='iex'):
    start = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    params = {
        "symbols": symbol,
        "timeframe": timeframe,
        "start": start,
        "feed": feed,  
    }

    bars=[]
    page_token = None

    while True:
        if page_token:
            params["page_token"] = page_token

        r = requests.get(f"{Base}/bars", headers=HEADERS, params=params)
        r.raise_for_status()
        data = r.json()
        bars.extend(data.get("bars", {}).get(symbol, []))
        page_token = data.get("next_page_token")
        if not page_token:
            break
    return bars




if __name__ == "__main__":
    bars = get_bars('AAPL', '1Min')
    print(bars[0])
    print(bars[77])


# ---------------------------------------------------------------------------
# Live quote / trade helpers (used by the live pipeline for current prices)
# ---------------------------------------------------------------------------

def get_latest_quote(symbol, feed="iex"):
    """Latest best bid/ask for a symbol."""
    r = requests.get(f"{Base}/{symbol}/quotes/latest",
                     headers=HEADERS, params={"feed": feed})
    r.raise_for_status()
    q = r.json()["quote"]
    return {"bid": q["bp"], "ask": q["ap"], "time": q["t"]}


def get_latest_trade(symbol, feed="iex"):
    """Latest trade (last price) for a symbol."""
    r = requests.get(f"{Base}/{symbol}/trades/latest",
                     headers=HEADERS, params={"feed": feed})
    r.raise_for_status()
    t = r.json()["trade"]
    return {"price": t["p"], "time": t["t"]}
