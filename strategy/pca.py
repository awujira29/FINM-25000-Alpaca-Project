import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA

def apply_pca(X_train, X_test, variance_threshold=0.80):
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)   # fit + transform on train
    X_test_scaled = scaler.transform(X_test) 


    pca = PCA(n_components=variance_threshold)
    X_train_pca = pca.fit_transform(X_train_scaled)
    X_test_pca = pca.transform(X_test_scaled) 

    n_components = pca.n_components_
    total_var = pca.explained_variance_ratio_.sum()
    print(f"PCA kept {n_components} components "
          f"explaining {total_var:.1%} of variance "
          f"(from {X_train.shape[1]} original features).")
    
    return X_train_pca, X_test_pca, scaler, pca

if __name__ == "__main__":
    from data.data_loader import load_daily_bars
    from strategy.features import build_features

    raw = load_daily_bars("AAPL", years=5)
    feats = build_features(raw).dropna()

    # Separate features from target, drop non-feature columns.
    y = feats["Target"]
    X = feats.drop(columns=["Target"])

    # Time-ordered split: first 80% train, last 20% test. NO shuffling.
    split = int(len(X) * 0.8)
    X_train, X_test = X.iloc[:split], X.iloc[split:]

    X_train_pca, X_test_pca, scaler, pca = apply_pca(X_train, X_test)
    print("Train PCA shape:", X_train_pca.shape)
    print("Test PCA shape:", X_test_pca.shape)