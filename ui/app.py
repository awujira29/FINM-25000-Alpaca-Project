"""
ui/app.py
Streamlit dashboard for the Alpaca systematic trading system.
"""
 
import os
import sys
import time
from datetime import datetime
from pathlib import Path
 
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT) 
 
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")
 
st.set_page_config(page_title="Alpaca Trading System", page_icon="📈",
                   layout="wide")

if not os.environ.get("ALPACA_API_KEY") or not os.environ.get("ALPACA_SECRET_KEY"):
    st.title("Alpaca Trading System")
    st.error(
        "Alpaca API keys not found. Create a `.env` file in the repo root "
        "(copy `.env.example`) with your **paper trading** keys:\n\n"
        "```\nALPACA_API_KEY=your_paper_key_id\nALPACA_SECRET_KEY=your_paper_secret\n```\n"
        "Then restart the app. Keys are never stored in code or committed to git."
    )
    st.stop()

import yaml                                   
from engine import TradingEngine, load_config  
from execution import broker                   
from risk.limits import RiskConfig, RiskManager  
from strategy.rules import STRATEGIES          
from strategy.model import train_and_signal    
from data.data_loader import load_daily_bars   
from backtest.engine import Backtester         
from backtest.metrics import compute_all_metrics  
 
CONFIG_PATH = ROOT / "config" / "config.yaml"
 

C_STRATEGY = "#2a78d6"   
C_BENCH = "#898781"      
C_DRAWDOWN = "#e34948"  
C_GRID = "#e1e0d9"
C_MUTED = "#898781"
C_SURFACE = "#fcfcfb"

def init_state():
    ss = st.session_state
    if "config" not in ss:
        ss.config = load_config(str(CONFIG_PATH))
    if "engine" not in ss:
        ss.engine = TradingEngine(ss.config)
    if "running" not in ss:
        ss.running = False
    if "last_tick" not in ss:
        ss.last_tick = 0.0
    if "tick_count" not in ss:
        ss.tick_count = 0
    if "equity_history" not in ss:
        ss.equity_history = []
    if "backtest_results" not in ss:
        ss.backtest_results = None
 
 
init_state()

def check_connection():
    """Ping the paper account; return (connected, account_dict_or_error)."""
    try:
        acct = broker.get_account()
        return True, acct
    except Exception as e: 
        return False, str(e)
 
 
def record_equity(equity: float):
    """Append one point to the session equity curve (keep last 500)."""
    st.session_state.equity_history.append((datetime.now(), equity))
    st.session_state.equity_history = st.session_state.equity_history[-500:]
 
 
def styled_axes(ax):
    """Recessive grid/axes so the data, not the chrome, is what you see."""
    ax.set_facecolor(C_SURFACE)
    ax.grid(True, color=C_GRID, linewidth=0.8)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(C_GRID)
    ax.tick_params(colors=C_MUTED, labelsize=8)
    return ax

cfg = st.session_state.config
 
st.sidebar.title("Controls")
 
mode = st.sidebar.radio("Mode", ["Paper trading", "Backtest"],
                        index=0 if cfg.get("mode", "paper") == "paper" else 1)
cfg["mode"] = "paper" if mode == "Paper trading" else "backtest"
 
st.sidebar.subheader("Strategy")
strategy_type = st.sidebar.selectbox(
    "Type", ["rule", "ml"],
    index=0 if cfg["strategy"]["type"] == "rule" else 1,
    help="rule = indicator-based; ml = PCA + logistic regression")
cfg["strategy"]["type"] = strategy_type
 
if strategy_type == "rule":
    rule_names = list(STRATEGIES)
    current = cfg["strategy"].get("rule_name", rule_names[0])
    cfg["strategy"]["rule_name"] = st.sidebar.selectbox(
        "Rule", rule_names,
        index=rule_names.index(current) if current in rule_names else 0)
else:
    cfg["strategy"]["ml_threshold"] = st.sidebar.slider(
        "ML long threshold P(up) >", 0.50, 0.80,
        float(cfg["strategy"].get("ml_threshold", 0.6)), 0.01)
 
st.sidebar.subheader("Risk limits")
r = cfg["risk"]
r["max_position_pct"] = st.sidebar.slider(
    "Max position (% of equity)", 0.05, 0.50,
    float(r["max_position_pct"]), 0.01)
r["max_total_exposure_pct"] = st.sidebar.slider(
    "Max total exposure (% of equity)", 0.10, 1.00,
    float(r["max_total_exposure_pct"]), 0.05)
r["stop_loss_pct"] = st.sidebar.slider(
    "Stop-loss (%)", 0.02, 0.30, float(r["stop_loss_pct"]), 0.01)
r["take_profit_pct"] = st.sidebar.slider(
    "Take-profit (%)", 0.05, 0.50, float(r["take_profit_pct"]), 0.01)
 
st.session_state.engine.risk = RiskManager(RiskConfig(**r))
st.session_state.engine.config = cfg
 
if st.sidebar.button("💾 Save settings to config.yaml"):
    with open(CONFIG_PATH, "w") as f:
        yaml.safe_dump(cfg, f, sort_keys=False)
    st.sidebar.success("Saved.")
 
refresh = st.sidebar.number_input(
    "Refresh interval (seconds)", min_value=10, max_value=600,
    value=int(cfg.get("refresh_seconds", 60)), step=10)
cfg["refresh_seconds"] = int(refresh)
 
st.sidebar.caption(
    f"Universe: {', '.join(cfg['universe'])}\n\n"
    "Paper trading only — no real money.")

st.title("📈 Alpaca Systematic Trading System")
 
connected, acct = check_connection()
b1, b2, b3, b4 = st.columns(4)
b1.metric("Connection", "🟢 Connected" if connected else "🔴 Disconnected")
b2.metric("Mode", "📄 Paper" if cfg["mode"] == "paper" else "🕰 Backtest")
b3.metric("Engine", "▶ Running" if st.session_state.running else "⏸ Stopped")
b4.metric("Ticks this session", st.session_state.tick_count)
 
if not connected:
    st.error(f"Cannot reach Alpaca paper API: {acct}")
 
if cfg["mode"] == "paper":
 
    c_start, c_stop, c_tick, _ = st.columns([1, 1, 1, 3])
    if c_start.button("▶ Start", type="primary", disabled=not connected):
        st.session_state.running = True
        st.session_state.last_tick = 0.0  
    if c_stop.button("⏹ Stop"):
        st.session_state.running = False
    run_once = c_tick.button("Run one tick", disabled=not connected)
 
    due = (st.session_state.running
           and time.time() - st.session_state.last_tick >= refresh)
    if (due or run_once) and connected:
        with st.spinner("Running tick: data → signals → risk → orders..."):
            try:
                st.session_state.engine.run_tick()
                st.session_state.tick_count += 1
                st.session_state.last_tick = time.time()
            except Exception as e:
                st.error(f"Tick failed: {e}")
                st.session_state.running = False
 
    if connected:
        equity = float(acct["equity"])
        record_equity(equity)
        last_eq = float(acct.get("last_equity", equity))
        day_pl = equity - last_eq
 
        st.subheader("Account (paper)")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Equity", f"${equity:,.2f}",
                  f"{day_pl:+,.2f} today")
        m2.metric("Cash", f"${float(acct['cash']):,.2f}")
        m3.metric("Buying power", f"${float(acct['buying_power']):,.2f}")
 
        try:
            positions = broker.get_all_positions()
        except Exception:
            positions = []
        unreal = sum(p["unrealized_pl"] for p in positions)
        m4.metric("Unrealized P&L", f"${unreal:,.2f}")
 
        if len(st.session_state.equity_history) >= 2:
            hist = pd.DataFrame(st.session_state.equity_history,
                                columns=["time", "equity"]).set_index("time")
            st.line_chart(hist, color=C_STRATEGY, height=200)
 
        left, right = st.columns(2)
 
        with left:
            st.subheader("Positions & P&L")
            if positions:
                pos_df = pd.DataFrame(positions)
                pos_df["unrealized_pl"] = pos_df["unrealized_pl"].round(2)
                st.dataframe(pos_df, use_container_width=True,
                             hide_index=True)
            else:
                st.info("No open positions.")
 
            st.subheader("Latest signals")
            sigs = st.session_state.engine.last_signals
            if sigs:
                sig_df = pd.DataFrame(
                    [{"symbol": s,
                      "signal": "🟢 LONG" if v == 1 else "⚪ FLAT"}
                     for s, v in sigs.items()])
                st.dataframe(sig_df, use_container_width=True,
                             hide_index=True)
            else:
                st.info("No signals yet — press Start or Run one tick.")
 
        with right:
            st.subheader("Recent orders")
            try:
                orders = broker.recent_orders(10)
            except Exception:
                orders = []
            if orders:
                st.dataframe(pd.DataFrame(orders), use_container_width=True,
                             hide_index=True)
            else:
                st.info("No orders yet.")
 
            st.subheader("Event log")
            events = st.session_state.engine.events
            if events:
                st.code("\n".join(events[:20]), language=None)
            else:
                st.caption("Engine events (data, signals, orders, "
                           "risk blocks) appear here.")
 
    if st.session_state.running:
        nxt = max(0, int(refresh - (time.time() - st.session_state.last_tick)))
        st.caption(f"Next tick in ~{nxt}s (auto-refreshing)")
        time.sleep(min(5, max(1, nxt)))
        st.rerun()

else:
    st.subheader("Backtest")
 
    with st.form("backtest_form"):
        f1, f2, f3, f4 = st.columns(4)
        symbol = f1.selectbox("Ticker", cfg["universe"])
        years = f2.slider("Years of history", 1, 10,
                          int(cfg["data"]["years"]))
        capital = f3.number_input("Initial capital ($)", 10_000, 10_000_000,
                                  100_000, step=10_000)
        commission = f4.number_input("Commission (bps)", 0.0, 50.0, 0.0,
                                     step=0.5)
        submitted = st.form_submit_button("Run backtest", type="primary")
 
    if submitted:
        with st.spinner(f"Backtesting {symbol} ({cfg['strategy']['type']})..."):
            try:
                if cfg["strategy"]["type"] == "rule":
                    raw = load_daily_bars(symbol, years=years)
                    sig_df = STRATEGIES[cfg["strategy"]["rule_name"]](raw)
                    label = cfg["strategy"]["rule_name"]
                else:
                    sig_df, *_ = train_and_signal(
                        symbol, years=years,
                        threshold=cfg["strategy"]["ml_threshold"])
                    label = "ML (PCA + logistic reg.)"
 
                bt = Backtester(sig_df, initial_capital=capital,
                                commission_bps=commission)
                results = bt.run()
                bench = Backtester.buy_and_hold(sig_df,
                                                initial_capital=capital)
                st.session_state.backtest_results = dict(
                    symbol=symbol, label=label, results=results,
                    trades=bt.trades, bench=bench)
            except Exception as e:
                st.error(f"Backtest failed: {e}")
                st.session_state.backtest_results = None
 
    br = st.session_state.backtest_results
    if br:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
 
        res, bench = br["results"], br["bench"]
 
        st.markdown(f"**{br['symbol']} — {br['label']}** vs buy & hold")
        fig, ax = plt.subplots(figsize=(10, 3.2))
        fig.patch.set_facecolor(C_SURFACE)
        styled_axes(ax)
        ax.plot(res.index, res["Portfolio_Value"], color=C_STRATEGY,
                linewidth=2, label="Strategy")
        ax.plot(bench.index, bench["Portfolio_Value"], color=C_BENCH,
                linewidth=2, linestyle="--", label="Buy & hold")
        ax.legend(frameon=False, fontsize=9, labelcolor="#52514e")
        ax.set_ylabel("Portfolio value ($)", color=C_MUTED, fontsize=9)
        st.pyplot(fig, clear_figure=True)
 
        fig2, ax2 = plt.subplots(figsize=(10, 1.8))
        fig2.patch.set_facecolor(C_SURFACE)
        styled_axes(ax2)
        ax2.fill_between(res.index, res["Drawdown"] * 100, 0,
                         color=C_DRAWDOWN, alpha=0.35, linewidth=0)
        ax2.plot(res.index, res["Drawdown"] * 100, color=C_DRAWDOWN,
                 linewidth=1)
        ax2.set_ylabel("Drawdown (%)", color=C_MUTED, fontsize=9)
        st.pyplot(fig2, clear_figure=True)
 
        st.subheader("Performance metrics")
        metrics = compute_all_metrics(res["Daily_Return"],
                                      res["Portfolio_Value"], br["trades"])
        bench_metrics = compute_all_metrics(bench["Daily_Return"],
                                            bench["Portfolio_Value"])
        mdf = pd.DataFrame({"Strategy": metrics,
                            "Buy & hold": bench_metrics})
        pct_rows = ["Total Return", "CAGR", "Volatility (ann.)",
                    "Max Drawdown", "Win Rate"]
        fmt = mdf.copy()
        for row in fmt.index:
            fmt.loc[row] = [
                f"{v:.1%}" if row in pct_rows and pd.notna(v)
                else (f"{v:.2f}" if pd.notna(v) else "—")
                for v in mdf.loc[row]]
        st.dataframe(fmt, use_container_width=True)
 
        st.subheader(f"Trade log ({len(br['trades'])} trades)")
        if br["trades"] is not None and not br["trades"].empty:
            tdf = br["trades"].copy()
            tdf["Return_Pct"] = (tdf["Return_Pct"] * 100).round(2)
            st.dataframe(tdf, use_container_width=True, hide_index=True)
        else:
            st.info("No completed trades in this period.")
    else:
        st.info("Choose parameters and press **Run backtest**.")
 