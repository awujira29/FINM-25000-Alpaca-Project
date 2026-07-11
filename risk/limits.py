from dataclasses import dataclass

@dataclass
class RiskConfig:
    """Risk limit settings."""
    max_position_pct: float = 0.20
    max_total_exposure_pct: float = 1.0
    stop_loss_pct: float = 0.10
    take_profit_pct: float = 0.20

class RiskManager:
    """Applies position, exposure, and stop/take-profit checks."""
    def __init__(self, config: RiskConfig = None):
        """Store the risk config."""
        self.config = config or RiskConfig()

    def check_new_order(self, symbol, qty, price, equity,
                        current_exposure, existing_position_value=0.0):
        """Approve or reject a proposed buy against the caps."""
        order_value = qty * price

        new_position_value = existing_position_value + order_value
        max_position_value = equity * self.config.max_position_pct
        if new_position_value > max_position_value:
            return False, (f"per-asset cap: {symbol} would be "
                           f"${new_position_value:,.0f} > "
                           f"${max_position_value:,.0f} "
                           f"({self.config.max_position_pct:.0%} of equity)")

        new_total = current_exposure + order_value
        max_total = equity * self.config.max_total_exposure_pct
        if new_total > max_total:
            return False, (f"total exposure cap: ${new_total:,.0f} > "
                           f"${max_total:,.0f} "
                           f"({self.config.max_total_exposure_pct:.0%} of equity)")

        return True, "approved"

    def check_stops(self, entry_price, current_price):
        """Return whether an open position should exit on stop-loss or take-profit."""
        change = current_price / entry_price - 1
        if change <= -self.config.stop_loss_pct:
            return True, f"stop-loss hit ({change:.1%})"
        if change >= self.config.take_profit_pct:
            return True, f"take-profit hit ({change:.1%})"
        return False, "within limits"

    def position_size(self, symbol, price, equity, target_pct=None):
        """Suggest a whole-share quantity sized to a fraction of equity."""
        target_pct = target_pct or self.config.max_position_pct
        budget = equity * target_pct
        return int(budget // price)

if __name__ == "__main__":
    rm = RiskManager()
    equity = 100_000

    ok, why = rm.check_new_order("AAPL", qty=150, price=200, equity=equity,
                                 current_exposure=0)
    print(ok, why)

    print("suggested qty:", rm.position_size("AAPL", price=200, equity=equity))

    print(rm.check_stops(entry_price=200, current_price=178))
