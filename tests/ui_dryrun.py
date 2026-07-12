
"""
Dry-run harness for ui/app.py (not a pytest file).
"""
 
import sys
import types
import contextlib
from pathlib import Path
 
import pandas as pd
import numpy as np
 
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import os
os.environ.setdefault("ALPACA_API_KEY", "PKTEST_DUMMY")
os.environ.setdefault("ALPACA_SECRET_KEY", "SKTEST_DUMMY")

class SessionState(dict):
    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError as e:
            raise AttributeError(k) from e
    def __setattr__(self, k, v):
        self[k] = v
 
class StopException(Exception):
    pass
 
class Column:
    def __getattr__(self, name):
        return _widget(name)
    def __enter__(self): return self
    def __exit__(self, *a): return False
 
CALLS = []
 
def _widget(name):
    def fn(*args, **kwargs):
        CALLS.append(name)
        if name in ("radio", "selectbox"):
            options = args[1] if len(args) > 1 else kwargs.get("options")
            idx = kwargs.get("index", 0)
            return options[idx]
        if name == "slider":
            return args[3] if len(args) > 3 else kwargs.get("value", args[1])
        if name == "number_input":
            return kwargs.get("value", args[1] if len(args) > 1 else 0)
        if name in ("button", "form_submit_button", "checkbox", "toggle"):
            return False
        if name == "columns":
            spec = args[0]
            n = spec if isinstance(spec, int) else len(spec)
            return [Column() for _ in range(n)]
        if name == "stop":
            raise StopException()
        if name in ("form", "spinner", "expander", "container"):
            @contextlib.contextmanager
            def cm(*a, **k):
                yield Column()
            return cm()
        return None
    return fn
 
def make_streamlit(mode_choice="Paper trading"):
    st = types.ModuleType("streamlit")
    st.session_state = SessionState()
    sidebar = Column()
 
    def radio(label, options, index=0, **k):
        CALLS.append("radio")
        if label == "Mode":
            return mode_choice
        return options[index]
 
    for name in ("set_page_config", "title", "error", "info", "success",
                 "warning", "caption", "subheader", "header", "markdown",
                 "metric", "dataframe", "code", "line_chart", "pyplot",
                 "write", "rerun", "divider"):
        setattr(st, name, _widget(name))
    for name in ("selectbox", "slider", "number_input", "button",
                 "form_submit_button", "columns", "form", "spinner",
                 "expander", "container", "stop", "checkbox", "toggle"):
        setattr(st, name, _widget(name))
    st.radio = radio
    sidebar.radio = radio
    st.sidebar = sidebar
    return st

def fake_synthetic_bars(n=750, seed=7):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(end="2026-07-10", periods=n)
    rets = rng.normal(0.0004, 0.015, n)
    close = 100 * np.exp(np.cumsum(rets))
    df = pd.DataFrame({
        "Open": close * (1 + rng.normal(0, 0.002, n)),
        "High": close * (1 + abs(rng.normal(0, 0.006, n))),
        "Low":  close * (1 - abs(rng.normal(0, 0.006, n))),
        "Close": close,
        "Volume": rng.integers(1e6, 5e6, n).astype(float),
    }, index=idx)
    return df
 
def patch_backend():
    from execution import broker
    from data import pipeline, data_loader
 
    broker.get_account = lambda: {
        "status": "ACTIVE", "equity": "100234.50", "last_equity": "100000.0",
        "cash": "60000.0", "buying_power": "120000.0"}
    broker.get_all_positions = lambda: [
        {"symbol": "AAPL", "qty": 10.0, "avg_entry": 210.0,
         "market_value": 2150.0, "unrealized_pl": 50.0}]
    broker.get_position = lambda s: 10.0 if s == "AAPL" else 0.0
    broker.recent_orders = lambda limit=20: [
        {"id": "abc", "symbol": "AAPL", "side": "buy", "qty": "10",
         "filled_qty": "10", "status": "filled", "filled_avg_price": "210.0"}]
    broker.submit_order = lambda s, q, side: {"id": "x", "status": "accepted"}
 
    data_loader.load_daily_bars = lambda symbol, years=5, feed="iex": \
        fake_synthetic_bars()
    pipeline.fetch_universe_history = lambda tickers, years=5: {
        t: fake_synthetic_bars(seed=i) for i, t in enumerate(tickers)}
    pipeline.fetch_live_prices = lambda tickers, feed="iex": {
        t: 100.0 for t in tickers}
 
def run_app(mode_choice):
    for m in list(sys.modules):
        if m == "streamlit":
            del sys.modules[m]
    st = make_streamlit(mode_choice)
    sys.modules["streamlit"] = st
 
    patch_backend()
    src = (ROOT / "ui" / "app.py").read_text()
    code = compile(src, str(ROOT / "ui" / "app.py"), "exec")
    g = {"__name__": "__main__", "__file__": str(ROOT / "ui" / "app.py")}
    try:
        exec(code, g)
    except StopException:
        print(f"  (st.stop() reached)")
    return st
 
print("=== PASS 1: paper mode ===")
st = run_app("Paper trading")
assert "metric" in CALLS and "dataframe" in CALLS
assert st.session_state.engine is not None
print("  paper mode rendered OK;",
      f"{CALLS.count('metric')} metrics, {CALLS.count('dataframe')} tables")
 
print("=== PASS 2: paper mode, one engine tick with fake data ===")
eng = st.session_state.engine
eng.run_tick()
snap = eng.snapshot()
assert set(snap) == {"signals", "positions", "orders", "events"}
assert len(snap["signals"]) == 5
print("  run_tick OK; signals:", snap["signals"])
print("  events:", snap["events"][:3])
 
print("=== PASS 3: backtest mode render ===")
CALLS.clear()
st = run_app("Backtest")
print("  backtest form rendered OK")
 
print("=== PASS 4: backtest pipeline (exact calls the UI makes) ===")
from strategy.rules import STRATEGIES
from backtest.engine import Backtester
from backtest.metrics import compute_all_metrics
from data.data_loader import load_daily_bars
 
raw = load_daily_bars("AAPL", years=3)  
for name, fn in STRATEGIES.items():
    sig_df = fn(raw)
    bt = Backtester(sig_df, initial_capital=100_000, commission_bps=1.0)
    res = bt.run()
    bench = Backtester.buy_and_hold(sig_df, initial_capital=100_000)
    m = compute_all_metrics(res["Daily_Return"], res["Portfolio_Value"], bt.trades)
    bm = compute_all_metrics(bench["Daily_Return"], bench["Portfolio_Value"])
    print(f"  {name:28s} trades={len(bt.trades):3d} "
          f"total={m['Total Return']:+.1%} sharpe={m['Sharpe Ratio']:.2f} "
          f"maxDD={m['Max Drawdown']:.1%}")
 
print("=== PASS 5: chart code (matplotlib figures build without error) ===")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
sig_df = STRATEGIES["Trend Following"](raw)
bt = Backtester(sig_df); res = bt.run()
bench = Backtester.buy_and_hold(sig_df)
fig, ax = plt.subplots(figsize=(10, 3.2))
ax.plot(res.index, res["Portfolio_Value"], color="#2a78d6", lw=2, label="Strategy")
ax.plot(bench.index, bench["Portfolio_Value"], color="#898781", lw=2, ls="--",
        label="Buy & hold")
ax.legend(frameon=False)
fig.savefig("/tmp/equity_test.png", dpi=80)
fig2, ax2 = plt.subplots(figsize=(10, 1.8))
ax2.fill_between(res.index, res["Drawdown"] * 100, 0, color="#e34948", alpha=0.35)
fig2.savefig("/tmp/dd_test.png", dpi=80)
print("  charts OK ->", Path("/tmp/equity_test.png").exists(),
      Path("/tmp/dd_test.png").exists())
 
print("\nALL DRY-RUN CHECKS PASSED")
