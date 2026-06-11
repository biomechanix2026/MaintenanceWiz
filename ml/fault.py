"""
AI4I 2020 fault-mode classifier (MW2 port).

Trains a binary failure-risk forest plus one per-mode forest on the UCI AI4I
2020 dataset, or any frame with the same columns. sklearn is imported lazily
inside training so the fallback ladder stays intact.

Train + save:  python -m ml.fault
"""
from __future__ import annotations

import json
import os
import pickle
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import ML_ARTIFACTS_DIR

MODES = ["TWF", "HDF", "PWF", "OSF", "RNF"]
FEATURES = [
    "Type",
    "Air temperature [K]",
    "Process temperature [K]",
    "Rotational speed [rpm]",
    "Torque [Nm]",
    "Tool wear [min]",
]
MODEL_PATH = os.path.join(ML_ARTIFACTS_DIR, "fault_model.pkl")
_TYPE_CODE = {"L": 0, "M": 1, "H": 2}


def _encode(df: pd.DataFrame) -> pd.DataFrame:
    X = df[FEATURES].copy()
    X["Type"] = X["Type"].map(_TYPE_CODE).fillna(1).astype(int)
    return X


def train_fault_model(df: pd.DataFrame) -> dict:
    from sklearn.ensemble import RandomForestClassifier

    X = _encode(df)

    def _fit(y):
        clf = RandomForestClassifier(
            n_estimators=200,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        )
        return clf.fit(X, y)

    return {
        "risk": _fit(df["Machine failure"]),
        "modes": {m: _fit(df[m]) for m in MODES},
        "features": FEATURES,
    }


def classify_fault(bundle: dict, reading: dict) -> dict:
    X = _encode(pd.DataFrame([reading]))

    def _p1(clf):
        probs = clf.predict_proba(X)[0]
        return float(probs[list(clf.classes_).index(1)]) if 1 in clf.classes_ else 0.0

    probs = {m: round(_p1(clf), 3) for m, clf in bundle["modes"].items()}
    return {
        "risk": round(_p1(bundle["risk"]), 3),
        "probable_mode": max(probs, key=probs.get),
        "probs": probs,
    }


def save_fault_model(bundle: dict, path: str = MODEL_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(bundle, f)


def load_fault_model(path: str = MODEL_PATH) -> dict:
    with open(path, "rb") as f:
        return pickle.load(f)


if __name__ == "__main__":
    csv = os.path.join(os.path.dirname(ML_ARTIFACTS_DIR), "..", "data", "raw", "ai4i2020.csv")
    csv = os.path.normpath(csv)
    df = pd.read_csv(csv)
    bundle = train_fault_model(df)
    save_fault_model(bundle)
    res = classify_fault(bundle, {
        "Type": "M",
        "Air temperature [K]": 302.0,
        "Process temperature [K]": 311.0,
        "Rotational speed [rpm]": 1400.0,
        "Torque [Nm]": 65.0,
        "Tool wear [min]": 220.0,
    })
    print(f"Saved {MODEL_PATH}")
    print(json.dumps(res, indent=2))
