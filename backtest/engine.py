"""
backtest.py
A small, reusable, long-only backtesting engine.

Assumptions
-----------
- Initial capital: $100,000 (configurable)
- Long-only, no leverage, no short selling
- Signal column (0/1 target position) is shifted forward by one day
  before being traded, so a decision made using information available
  through the close of day T is only acted on at the close of day T+1.
  This avoids lookahead bias.
- Trading is frictionless (no commissions/slippage) unless a
  `commission_bps` is supplied.
"""

import numpy as np
import pandas as pd


class Backtester:
    def __init__(self, df: pd.DataFrame, initial_capital: float = 100_000.0,
                 commission_bps: float = 0.0):
        """
        df must contain a 'Close' column and a 'Signal' column
        (0 = flat, 1 = fully long), indexed by date.
        """
        if "Signal" not in df.columns:
            raise ValueError("df must contain a 'Signal' column (0/1 target position)")

        self.df = df.copy()
        self.initial_capital = initial_capital
        self.commission_bps = commission_bps
        self.results = None
        self.trades = None

    def run(self) -> pd.DataFrame:
        df = self.df.copy()

        # Trade tomorrow on today's decision -> avoid lookahead bias.
        df["Position"] = df["Signal"].shift(1).fillna(0).astype(int)

        daily_return = df["Close"].pct_change().fillna(0)
        strategy_return = df["Position"] * daily_return

        # Commission charged on days the position changes (entry or exit).
        position_change = df["Position"].diff().abs().fillna(0)
        commission_drag = position_change * (self.commission_bps / 10_000)
        strategy_return = strategy_return - commission_drag

        portfolio_value = self.initial_capital * (1 + strategy_return).cumprod()

        df["Daily_Return"] = strategy_return
        df["Portfolio_Value"] = portfolio_value

        running_max = portfolio_value.cummax()
        df["Drawdown"] = portfolio_value / running_max - 1

        self.results = df
        self.trades = self._extract_trades(df)
        return df

    def _extract_trades(self, df: pd.DataFrame) -> pd.DataFrame:
        """Build a trade log from entry/exit points implied by Position."""
        entries = df.index[(df["Position"] == 1) & (df["Position"].shift(1).fillna(0) == 0)]
        exits = df.index[(df["Position"] == 0) & (df["Position"].shift(1).fillna(0) == 1)]

        trades = []
        exits_list = list(exits)
        for entry_date in entries:
            exit_candidates = [d for d in exits_list if d > entry_date]
            exit_date = exit_candidates[0] if exit_candidates else df.index[-1]

            entry_price = df.loc[entry_date, "Close"]
            exit_price = df.loc[exit_date, "Close"]
            pnl_pct = exit_price / entry_price - 1

            trades.append({
                "Entry_Date": entry_date,
                "Exit_Date": exit_date,
                "Entry_Price": entry_price,
                "Exit_Price": exit_price,
                "Return_Pct": pnl_pct,
                "Win": pnl_pct > 0,
            })

        return pd.DataFrame(trades)

    @staticmethod
    def buy_and_hold(df: pd.DataFrame, initial_capital: float = 100_000.0) -> pd.DataFrame:
        """Benchmark: buy on day 1, hold for the whole period."""
        out = df.copy()
        daily_return = out["Close"].pct_change().fillna(0)
        out["Daily_Return"] = daily_return
        out["Portfolio_Value"] = initial_capital * (1 + daily_return).cumprod()
        running_max = out["Portfolio_Value"].cummax()
        out["Drawdown"] = out["Portfolio_Value"] / running_max - 1
        return out
