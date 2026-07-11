import numpy as np
import pandas as pd
from strategy.indicators import add_all_indicators

def build_features(df, rolling_window=20):
    df = add_all_indicators(df).copy()

    df["Log_Return"] = np.log(df["Close"]).diff()
    df["Roll_Mean"] = df["Log_Return"].rolling(rolling_window).mean()
    df["Roll_Std"] = df["Log_Return"].rolling(rolling_window).std()
       
      
    
    for h in (5, 10, 20, 60):
        df[f"Return_{h}d"] = df["Close"].pct_change(h)

    
    df["Close_vs_SMA20"] = df["Close"] / df["SMA_20"] - 1
    df["Close_vs_SMA50"] = df["Close"] / df["SMA_50"] - 1
    df["SMA20_vs_SMA50"] = df["SMA_20"] / df["SMA_50"] - 1

   
    vol_short = df["Log_Return"].rolling(5).std()
    vol_long = df["Log_Return"].rolling(60).std()
    df["Vol_Regime"] = vol_short / vol_long

    df["Target"] = (df["Close"].shift(-1) > df["Close"]).astype(int)

    return df

if __name__ == "__main__":
    from data.data_loader import load_daily_bars
    raw = load_daily_bars("AAPL", years=5)
    feats = build_features(raw)
    print(feats.shape)
    print(feats[["Close", "Log_Return", "Roll_Mean", "Roll_Std", "Target"]].tail())