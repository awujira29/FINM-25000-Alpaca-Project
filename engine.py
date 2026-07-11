import time
import logging
from datetime import datetime

import yaml

from data.pipeline import fetch_universe_history, fetch_live_prices
from strategy.selector import generate_signals
from risk.limits import RiskManager, RiskConfig
from execution import broker

log = logging.getLogger("engine")

def load_config(path="config/config.yaml"):
    """Load the YAML config."""
    with open(path) as f:
        return yaml.safe_load(f)

class TradingEngine:
    """Runs one trading tick: data, signals, risk, execution."""

    def __init__(self, config=None):
        """Set up config, risk manager, and empty state."""
        self.config = config or load_config()
        self.risk = RiskManager(RiskConfig(**self.config["risk"]))
        self.history = {}
        self.last_signals = {}
        self.events = []

    def _log_event(self, msg):
        """Record a timestamped event, keeping the last 50."""
        ts = datetime.now().strftime("%H:%M:%S")
        self.events.insert(0, f"[{ts}] {msg}")
        self.events = self.events[:50]
        log.info(msg)

    def ensure_history(self):
        """Fetch universe history once, then reuse it."""
        if not self.history:
            self.history = fetch_universe_history(
                self.config["universe"], years=self.config["data"]["years"])

    def run_tick(self):
        """Run one full cycle: data to signals to risk to orders."""
        cfg = self.config
        tickers = cfg["universe"]

        self.ensure_history()
        prices = fetch_live_prices(tickers)
        self._log_event(f"Fetched live prices for {len(prices)} tickers")

        scfg = cfg["strategy"]
        self.last_signals = generate_signals(
            self.history,
            strategy_type=scfg["type"],
            rule_name=scfg.get("rule_name", "Trend Following"),
            ml_threshold=scfg.get("ml_threshold", 0.6),
            years=cfg["data"]["years"],
        )

        acct = broker.get_account()
        equity = float(acct["equity"])
        positions = {p["symbol"]: p for p in broker.get_all_positions()}
        current_exposure = sum(p["market_value"] for p in positions.values())

        for symbol, sig in self.last_signals.items():
            price = prices.get(symbol)
            if price is None:
                continue
            held = broker.get_position(symbol)

            if held > 0 and symbol in positions:
                exit_now, reason = self.risk.check_stops(
                    positions[symbol]["avg_entry"], price)
                if exit_now:
                    broker.submit_order(symbol, int(held), "sell")
                    self._log_event(f"EXIT {symbol}: {reason}")
                    continue

            if sig == 1 and held == 0:
                qty = self.risk.position_size(symbol, price, equity)
                existing_val = positions.get(symbol, {}).get("market_value", 0.0)
                ok, why = self.risk.check_new_order(
                    symbol, qty, price, equity, current_exposure, existing_val)
                if ok and qty > 0:
                    broker.submit_order(symbol, qty, "buy")
                    current_exposure += qty * price
                    self._log_event(f"BUY {symbol} x{qty} @ ~${price:.2f}")
                else:
                    self._log_event(f"BLOCKED {symbol}: {why}")
            elif sig == 0 and held > 0:
                broker.submit_order(symbol, int(held), "sell")
                self._log_event(f"SELL {symbol} x{int(held)} (signal flat)")

        return self.snapshot()

    def snapshot(self):
        """Return current signals, positions, orders, and events for a UI."""
        return {
            "signals": self.last_signals,
            "positions": broker.get_all_positions(),
            "orders": broker.recent_orders(10),
            "events": self.events,
        }

def main():
    """Run the loop headless for a few ticks as a smoke test."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s")

    cfg = load_config()
    broker.safety_check()
    engine = TradingEngine(cfg)

    if cfg.get("mode") != "paper":
        log.info("Config mode is not 'paper'; engine loop is for paper mode.")
        return

    ticks = 3
    for i in range(ticks):
        log.info("---- tick %d/%d ----", i + 1, ticks)
        engine.run_tick()
        if i < ticks - 1:
            time.sleep(cfg.get("refresh_seconds", 60))

if __name__ == "__main__":
    main()
