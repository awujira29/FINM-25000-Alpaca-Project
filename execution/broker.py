import os
import logging

import requests
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger("broker")

TRADING_BASE = "https://paper-api.alpaca.markets"

HEADERS = {
    "APCA-API-KEY-ID": os.environ["ALPACA_API_KEY"],
    "APCA-API-SECRET-KEY": os.environ["ALPACA_SECRET_KEY"],
}

def safety_check():
    """Refuse to run unless pointed at the paper endpoint."""
    assert "paper" in TRADING_BASE, "TRADING_BASE is not the paper endpoint!"
    r = requests.get(f"{TRADING_BASE}/v2/account", headers=HEADERS)
    r.raise_for_status()
    acct = r.json()
    log.info("Account %s | equity $%.2f | cash $%.2f | buying power $%.2f",
             acct["status"], float(acct["equity"]), float(acct["cash"]),
             float(acct["buying_power"]))
    return acct

def get_account():
    """Return the Alpaca account object."""
    r = requests.get(f"{TRADING_BASE}/v2/account", headers=HEADERS)
    r.raise_for_status()
    return r.json()

def get_position(symbol):
    """Return shares held for a symbol, or 0.0."""
    r = requests.get(f"{TRADING_BASE}/v2/positions/{symbol}", headers=HEADERS)
    if r.status_code == 404:
        return 0.0
    r.raise_for_status()
    return float(r.json()["qty"])

def get_all_positions():
    """Return all open positions with entry, value, and P&L."""
    r = requests.get(f"{TRADING_BASE}/v2/positions", headers=HEADERS)
    r.raise_for_status()
    return [
        {
            "symbol": p["symbol"],
            "qty": float(p["qty"]),
            "avg_entry": float(p["avg_entry_price"]),
            "market_value": float(p["market_value"]),
            "unrealized_pl": float(p["unrealized_pl"]),
        }
        for p in r.json()
    ]

def submit_order(symbol, qty, side):
    """Submit a market order and return the order dict."""
    order = {
        "symbol": symbol, "qty": qty, "side": side,
        "type": "market", "time_in_force": "day",
    }
    r = requests.post(f"{TRADING_BASE}/v2/orders", headers=HEADERS, json=order)
    if r.status_code >= 400:
        log.error("ORDER REJECTED (%s) %s %s %s: %s",
                  r.status_code, side, qty, symbol, r.text)
        r.raise_for_status()
    o = r.json()
    log.info("ORDER %s %s %s | id=%s | status=%s",
             side.upper(), qty, symbol, o["id"], o["status"])
    return o

def get_order_status(order_id):
    """Return the current state of one order."""
    r = requests.get(f"{TRADING_BASE}/v2/orders/{order_id}", headers=HEADERS)
    r.raise_for_status()
    o = r.json()
    return {
        "id": o["id"],
        "symbol": o["symbol"],
        "side": o["side"],
        "qty": o["qty"],
        "filled_qty": o["filled_qty"],
        "status": o["status"],
        "filled_avg_price": o.get("filled_avg_price"),
    }

def recent_orders(limit=20):
    """Return recent orders across all states."""
    r = requests.get(f"{TRADING_BASE}/v2/orders",
                     headers=HEADERS, params={"status": "all", "limit": limit})
    r.raise_for_status()
    return [
        {
            "id": o["id"], "symbol": o["symbol"], "side": o["side"],
            "qty": o["qty"], "filled_qty": o["filled_qty"],
            "status": o["status"], "filled_avg_price": o.get("filled_avg_price"),
        }
        for o in r.json()
    ]

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    safety_check()
    print("Positions:", get_all_positions())
    print("Recent orders:", recent_orders(5))
