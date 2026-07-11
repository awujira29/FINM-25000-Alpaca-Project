"""
metrics.py
Risk/return performance metrics computed from a backtest's daily
returns and portfolio value series.
"""

import numpy as np
import pandas as pd

TRADING_DAYS_PER_YEAR = 252


def total_return(portfolio_value: pd.Series) -> float:
    return portfolio_value.iloc[-1] / portfolio_value.iloc[0] - 1


def cagr(portfolio_value: pd.Series) -> float:
    n_days = (portfolio_value.index[-1] - portfolio_value.index[0]).days
    n_years = n_days / 365.25
    if n_years <= 0:
        return np.nan
    return (portfolio_value.iloc[-1] / portfolio_value.iloc[0]) ** (1 / n_years) - 1


def annualized_volatility(daily_returns: pd.Series) -> float:
    return daily_returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR)


def sharpe_ratio(daily_returns: pd.Series, risk_free_rate: float = 0.0) -> float:
    excess = daily_returns - risk_free_rate / TRADING_DAYS_PER_YEAR
    vol = daily_returns.std()
    if vol == 0 or np.isnan(vol):
        return np.nan
    return (excess.mean() / vol) * np.sqrt(TRADING_DAYS_PER_YEAR)


def sortino_ratio(daily_returns: pd.Series, risk_free_rate: float = 0.0) -> float:
    excess = daily_returns - risk_free_rate / TRADING_DAYS_PER_YEAR
    downside = daily_returns[daily_returns < 0]
    downside_std = downside.std()
    if downside_std == 0 or np.isnan(downside_std):
        return np.nan
    return (excess.mean() / downside_std) * np.sqrt(TRADING_DAYS_PER_YEAR)


def max_drawdown(portfolio_value: pd.Series) -> float:
    running_max = portfolio_value.cummax()
    drawdown = portfolio_value / running_max - 1
    return drawdown.min()


def win_rate(trades: pd.DataFrame) -> float:
    if trades is None or trades.empty:
        return np.nan
    return trades["Win"].mean()


def compute_all_metrics(daily_returns: pd.Series, portfolio_value: pd.Series,
                         trades: pd.DataFrame = None, risk_free_rate: float = 0.0) -> dict:
    """Returns a dict of all required performance metrics."""
    return {
        "Total Return": total_return(portfolio_value),
        "CAGR": cagr(portfolio_value),
        "Volatility (ann.)": annualized_volatility(daily_returns),
        "Sharpe Ratio": sharpe_ratio(daily_returns, risk_free_rate),
        "Sortino Ratio": sortino_ratio(daily_returns, risk_free_rate),
        "Max Drawdown": max_drawdown(portfolio_value),
        "Win Rate": win_rate(trades) if trades is not None else np.nan,
        "# Trades": len(trades) if trades is not None else np.nan,
    }


def metrics_table(results_by_strategy: dict, risk_free_rate: float = 0.0) -> pd.DataFrame:
    """
    results_by_strategy: {strategy_name: {"daily_returns":..., "portfolio_value":..., "trades":...}}
    Returns a tidy DataFrame, one row per strategy, ready to display.
    """
    rows = {}
    for name, r in results_by_strategy.items():
        rows[name] = compute_all_metrics(
            r["daily_returns"], r["portfolio_value"], r.get("trades"), risk_free_rate
        )
    return pd.DataFrame(rows).T
