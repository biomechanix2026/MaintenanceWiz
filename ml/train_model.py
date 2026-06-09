"""
Train the prognostic RUL model and persist artifacts.

Output (ml/artifacts/):
  rul_model.pkl          - pickled RULModel (estimator + metadata)
  feature_columns.json   - feature contract + estimator kind

Run:  python ml/train_model.py

Uses scikit-learn's RandomForestRegressor when available; otherwise falls back
to the pure-numpy NumpyForest so it always produces a working artifact.
"""
from __future__ import annotations
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (SENSOR_FEATURES, MAX_RUL_DAYS, SENSOR_LOGS_CSV,
                    ASSET_REGISTRY_CSV)
from ml.model import RULModel, NumpyForest, to_deviation


def build_dataset():
    sensors = pd.read_csv(SENSOR_LOGS_CSV)
    registry = pd.read_csv(ASSET_REGISTRY_CSV)[["asset_id", "type"]]
    df = sensors.merge(registry, on="asset_id")
    X, y = [], []
    for _, r in df.iterrows():
        readings = {f: r[f] for f in SENSOR_FEATURES}
        X.append(to_deviation(r["type"], readings))
        y.append(r["health_index"] * MAX_RUL_DAYS)   # RUL target in days
    return np.array(X), np.array(y)


def train():
    X, y = build_dataset()
    # simple train/test split (time-agnostic; data is synthetic)
    rng = np.random.default_rng(0)
    idx = rng.permutation(len(y))
    cut = int(0.8 * len(y))
    tr, te = idx[:cut], idx[cut:]

    try:
        from sklearn.ensemble import RandomForestRegressor
        est = RandomForestRegressor(n_estimators=200, max_depth=8,
                                    min_samples_leaf=3, random_state=42)
        est.fit(X[tr], y[tr])
        kind = "sklearn-rf"
    except Exception as e:
        print(f"[info] scikit-learn unavailable ({type(e).__name__}); "
              f"using numpy fallback forest.")
        est = NumpyForest(n_estimators=120, max_depth=9, min_leaf=2).fit(X[tr], y[tr])
        kind = "numpy-forest"

    # metrics
    pred = est.predict(X[te])
    mae = float(np.mean(np.abs(pred - y[te])))
    rmse = float(np.sqrt(np.mean((pred - y[te]) ** 2)))
    ss_res = np.sum((y[te] - pred) ** 2)
    ss_tot = np.sum((y[te] - np.mean(y[te])) ** 2)
    r2 = float(1 - ss_res / ss_tot) if ss_tot > 0 else 0.0

    model = RULModel(est, kind=kind, train_mean=float(np.mean(y[tr])))
    model.save()

    print(f"Trained estimator: {kind}")
    print(f"  samples: {len(y)} (train {len(tr)} / test {len(te)})")
    print(f"  MAE : {mae:6.2f} days")
    print(f"  RMSE: {rmse:6.2f} days")
    print(f"  R^2 : {r2:6.3f}")
    print(f"Saved -> ml/artifacts/rul_model.pkl")

    # sanity demo on one degraded asset
    demo = {"temperature": 70, "vibration": 6.5, "pressure": 1.35,
            "humidity": 45, "power": 145}
    print("\nDemo (CONV-BELT-03-like degraded conveyor):")
    print(f"  RUL        : {model.predict_rul('conveyor', demo):.1f} days")
    print(f"  Fail prob  : {model.failure_probability('conveyor', demo):.2%}")
    exp = model.explain("conveyor", demo)
    print(f"  Top driver : {exp['top_driver']}  ({exp['method']})")


if __name__ == "__main__":
    train()
