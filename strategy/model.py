# model.py
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

from data.data_loader import load_daily_bars
from strategy.features import build_features
from strategy.pca import apply_pca


def build_dataset(symbol="AAPL", years=5):
    raw = load_daily_bars(symbol, years=years)
    feats = build_features(raw).dropna()
    y = feats["Target"]
    X = feats.drop(columns=["Target"])
    return feats, X, y


def train_and_signal(symbol="AAPL", years=5, threshold=0.6, train_frac=0.8):
    feats, X, y = build_dataset(symbol, years)

    split = int(len(X) * train_frac)
    X_train, X_test = X.iloc[:split], X.iloc[split:]
    y_train, y_test = y.iloc[:split], y.iloc[split:]

    X_train_pca, X_test_pca, scaler, pca = apply_pca(X_train, X_test, variance_threshold=0.95)

    model = LogisticRegression(max_iter=1000, class_weight="balanced")
    model.fit(X_train_pca, y_train)

    proba_up = model.predict_proba(X_test_pca)[:, 1]
    signal = (proba_up > threshold).astype(int)

    signals = feats.iloc[split:][["Close"]].copy()
    signals["Prob_Up"] = proba_up
    signals["Signal"] = signal

    # Diagnostics
    try:
        auc = roc_auc_score(y_test, proba_up)
    except ValueError:
        auc = float("nan")
    long_mask = signal == 1
    long_precision = y_test.values[long_mask].mean() if long_mask.sum() > 0 else float("nan")

    print(f"Test rows: {len(signals)}")
    print(f"Days signal = Long: {int(signal.sum())} ({signal.mean():.1%})")
    print(f"AUC: {auc:.3f}   |   Long precision: {long_precision:.1%} "
          f"(on {int(long_mask.sum())} long days)")
    print(f"Prob_Up range: {proba_up.min():.3f} to {proba_up.max():.3f}")

    return signals, model, scaler, pca


if __name__ == "__main__":
    signals, model, scaler, pca = train_and_signal("MSFT", years=5)
    print(signals.tail())