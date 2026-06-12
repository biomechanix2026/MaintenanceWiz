"""
NASA C-MAPSS turbofan loader + rolling-window features (MW2 port).

Format: space-separated, no header; columns = unit, cycle, 3 op-settings,
21 sensors. Attribution: Saxena & Goebel (2008), NASA Prognostics CoE.
Used as a rotating-equipment analogue to benchmark the estimator class, not a
validated steel-plant prediction.
"""
from __future__ import annotations

import pandas as pd

COLS = ["unit", "cycle", "op1", "op2", "op3"] + [f"s{i}" for i in range(1, 22)]
SENSOR_COLS = [f"s{i}" for i in range(1, 22)]


def load_cmapss(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, sep=r"\s+", header=None).iloc[:, :26]
    df.columns = COLS
    return df


def add_rul_labels(df: pd.DataFrame, cap: int = 125) -> pd.DataFrame:
    """Piecewise-linear RUL: cycles to that unit's final cycle, capped."""
    max_cycle = df.groupby("unit")["cycle"].transform("max")
    return df.assign(rul=(max_cycle - df["cycle"]).clip(upper=cap))


def build_features(df: pd.DataFrame, window: int = 5):
    feats = df.copy()
    cols = list(SENSOR_COLS)
    for c in SENSOR_COLS:
        g = feats.groupby("unit")[c]
        feats[f"{c}_rmean"] = g.transform(lambda s: s.rolling(window, min_periods=1).mean())
        feats[f"{c}_rstd"] = g.transform(lambda s: s.rolling(window, min_periods=1).std().fillna(0.0))
        cols += [f"{c}_rmean", f"{c}_rstd"]
    cols.append("cycle")
    return feats, cols


def last_cycle_rows(feats: pd.DataFrame) -> pd.DataFrame:
    idx = feats.groupby("unit")["cycle"].idxmax()
    return feats.loc[idx]
