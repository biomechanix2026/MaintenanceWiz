"""
Benchmark MW1's RUL estimator class on NASA C-MAPSS FD001 (MW2 port).

Trains RandomForest (the product path) and, when xgboost is installed, an
XGBoost variant on rolling-window features. Evaluation uses each test unit's
last cycle against capped ground truth. The output is capability provenance,
not a validated steel-plant prediction.

Run:  python -m ml.benchmark_rul
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import ML_ARTIFACTS_DIR, ROOT
from ml.cmapss import add_rul_labels, build_features, last_cycle_rows, load_cmapss

DATA_DIR = os.path.join(ROOT, "data", "raw", "cmapss")
OUT_PATH = os.path.join(ML_ARTIFACTS_DIR, "benchmark.json")
CAP = 125


def _rmse(preds, truth) -> float:
    return float(np.sqrt(np.mean((np.asarray(preds) - np.asarray(truth)) ** 2)))


def run(data_dir: str = DATA_DIR, out_path: str = OUT_PATH, emit: bool = True) -> dict:
    train = add_rul_labels(load_cmapss(os.path.join(data_dir, "train_FD001.txt")), cap=CAP)
    test = load_cmapss(os.path.join(data_dir, "test_FD001.txt"))
    truth = np.minimum(
        pd.read_csv(os.path.join(data_dir, "RUL_FD001.txt"), header=None)[0].astype(float),
        CAP,
    )

    tr_feats, cols = build_features(train)
    te_feats, _ = build_features(test)
    last = last_cycle_rows(te_feats).sort_values("unit")

    results = {
        "dataset": "NASA C-MAPSS FD001",
        "cap": CAP,
        "models": {},
        "caveat": (
            "Rotating-equipment analogue benchmark of the estimator class; "
            "not a validated steel-plant prediction."
        ),
    }

    from sklearn.ensemble import RandomForestRegressor

    rf = RandomForestRegressor(
        n_estimators=200,
        max_depth=12,
        min_samples_leaf=3,
        random_state=42,
        n_jobs=-1,
    )
    rf.fit(tr_feats[cols], tr_feats["rul"])
    results["models"]["random_forest"] = round(
        _rmse(np.clip(rf.predict(last[cols]), 0, CAP), truth),
        2,
    )

    try:
        from xgboost import XGBRegressor

        xgb = XGBRegressor(
            n_estimators=400,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            n_jobs=-1,
        )
        xgb.fit(tr_feats[cols], tr_feats["rul"])
        results["models"]["xgboost"] = round(
            _rmse(np.clip(xgb.predict(last[cols]), 0, CAP), truth),
            2,
        )
    except ImportError:
        results["models"]["xgboost"] = None

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    if emit:
        print(json.dumps(results, indent=2))
    return results


if __name__ == "__main__":
    run()
