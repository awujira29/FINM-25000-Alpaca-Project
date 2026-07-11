# Alpaca Systematic Trading System

An end-to-end systematic trading system that uses Alpaca for market data and
order routing in **paper trading mode only**. It continuously pulls daily data
for a universe of tickers, generates signals from either a rule-based strategy
or an ML model, filters orders through a risk layer, routes them to Alpaca's
paper account, and monitors everything from a Streamlit dashboard.

**Paper trading only. No real money is used. No credit card or live account required.**

## Overview and goals

The system turns a systematic strategy into live paper trades with proper risk
controls and monitoring. It supports two run modes: **backtest** (historical
evaluation) and **paper** (live paper trading against Alpaca). The strategy is
selectable per run: rule-based (trend-following, mean-reversion, or a custom
multi-indicator rule) or model-based (PCA + logistic regression).

## Architecture

```
                    ┌──────────────────────────────────────┐
                    │   UI  (built separately — Streamlit/  │
                    │        Dash/TUI): reads engine state, │
                    │        renders positions/P&L/orders,  │
                    │        start/stop, mode switch        │
                    └───────────────┬──────────────────────┘
                                    │ imports + calls
                    ┌───────────────▼──────────────────────┐
                    │              engine.py                 │
                    │   TradingEngine.run_tick()             │
                    │   orchestrates one loop cycle          │
                    └───────────────┬────────────────────────┘
              ┌─────────────────────┼─────────────────────┐
              ▼                     ▼                     ▼
     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
     │ data/        │     │ strategy/    │     │ risk/        │
     │ pipeline     │──►  │ selector     │──►  │ limits       │
     │ (multi-      │     │ (rule OR ml) │     │ (caps, stops)│
     │  ticker)     │     └──────────────┘     └──────┬───────┘
     └──────────────┘                                 │ approved
              │ connector / data_loader                ▼
              │ (Alpaca Market Data API)      ┌──────────────┐
              │                               │ execution/   │
              │                               │ broker       │
              │                               │ (Alpaca      │
              │                               │  Trading API,│
              │                               │  PAPER)      │
              │                               └──────────────┘
              ▼
     ┌──────────────┐
     │ backtest/    │   engine + metrics (backtest mode)
     └──────────────┘
```

Each loop tick: **pipeline** fetches data → **selector** generates signals →
**risk** approves/blocks each order → **broker** submits approved paper orders →
results are recorded in the engine's state.

The **backend engine is UI-agnostic**: a UI imports `TradingEngine`, calls
`run_tick()` on a timer, and renders `engine.snapshot()`. The UI layer is built
separately.

## Folder structure

```
alpaca-trading-system/
├── engine.py               # headless orchestration loop (UI-free)
├── config/config.yaml      # tickers, strategy, risk limits, mode
├── data/
│   ├── connector.py        # Alpaca Market Data REST (bars + live quotes/trades)
│   ├── data_loader.py      # daily OHLCV -> clean DataFrame
│   └── pipeline.py         # multi-ticker fetch loop + logging
├── strategy/
│   ├── indicators.py       # 8 technical indicators
│   ├── rules.py            # trend / mean-reversion / custom strategies
│   ├── features.py, pca.py, model.py   # ML signal path
│   └── selector.py         # common interface: rule OR ml -> {ticker: signal}
├── execution/
│   └── broker.py           # Alpaca Trading API (paper): orders + states
├── risk/
│   └── limits.py           # position cap, exposure cap, stop-loss/take-profit
├── backtest/
│   ├── engine.py           # long-only backtester
│   └── metrics.py          # Sharpe, Sortino, drawdown, hit rate, ...
├── tests/
│   └── test_risk.py
├── requirements.txt
└── .env.example
```

## Setup

```
pip install -r requirements.txt
cp .env.example .env        # then add your Alpaca PAPER keys
```

`.env` (never committed):

```
ALPACA_API_KEY=your_paper_key_id
ALPACA_SECRET_KEY=your_paper_secret
```

Edit `config/config.yaml` to set the ticker universe, strategy type, and risk
limits. API keys are **never** stored there — only in `.env`.

## Running

The backend runs headless for testing:

```
python engine.py        # runs a few live paper ticks as a smoke test
```

`engine.TradingEngine.run_tick()` performs one full cycle (data → signals →
risk → execution) and returns `snapshot()` with signals, positions, orders, and
the event log. **The UI layer (dashboard with start/stop, mode switch, and live
monitoring) is built separately** and drives the engine by calling `run_tick()`
on a timer and rendering the snapshot.

## Strategy and risk controls

**Strategies** (config `strategy.type`):
- `rule` — Trend Following (MACD + ADX), Mean Reversion (RSI + Bollinger), or
  a custom EMA/RSI/OBV rule.
- `ml` — PCA on ~30 engineered features, logistic regression, long if
  P(up) > 0.6.

**Risk controls** (config `risk`):
- Max position per asset (default 20% of equity)
- Max total exposure (default 100%, i.e. no leverage)
- Stop-loss (default −10%) and take-profit (default +20%) on open positions

Every order is checked before submission; blocked orders are logged with the
reason and shown in the dashboard event log.

## Modes

- **Backtest** — historical evaluation via `backtest/engine.py`, reporting
  cumulative P&L, drawdown, Sharpe, Sortino, trade count, and hit rate.
- **Paper** — live paper trading against Alpaca's paper endpoint.

## Testing

```
pytest tests/ -q
```

## Video

<link to your 10–15 min walkthrough>
