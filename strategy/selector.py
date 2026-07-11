import logging

from strategy.rules import STRATEGIES
from strategy.model import train_and_signal

log = logging.getLogger("selector")

def generate_signals(history, strategy_type="rule", rule_name="Trend Following",
                     ml_threshold=0.6, years=5):
    """Return {ticker: 0/1 signal} from the rule or ML strategy."""
    signals = {}

    if strategy_type == "rule":
        strategy_fn = STRATEGIES.get(rule_name)
        if strategy_fn is None:
            raise ValueError(f"Unknown rule strategy: {rule_name}. "
                             f"Options: {list(STRATEGIES)}")
        for symbol, df in history.items():
            try:
                result = strategy_fn(df)
                signals[symbol] = int(result["Signal"].iloc[-1])
            except Exception as e:
                log.warning("signal %s failed: %s", symbol, e)
                signals[symbol] = 0

    elif strategy_type == "ml":
        for symbol in history:
            try:
                sig_df, model, scaler, pca = train_and_signal(
                    symbol, years=years, threshold=ml_threshold)
                signals[symbol] = int(sig_df["Signal"].iloc[-1])
            except Exception as e:
                log.warning("ML signal %s failed: %s", symbol, e)
                signals[symbol] = 0

    else:
        raise ValueError(f"strategy_type must be 'rule' or 'ml', got {strategy_type}")

    log.info("signals (%s): %s", strategy_type, signals)
    return signals

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from data.data_loader import load_daily_bars
    hist = {s: load_daily_bars(s, years=2) for s in ["AAPL", "MSFT"]}
    print("Rule:", generate_signals(hist, "rule", "Trend Following"))
