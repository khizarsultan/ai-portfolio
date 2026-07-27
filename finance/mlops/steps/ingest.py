"""Data ingestion + feature store for the fraud pipeline."""
from __future__ import annotations
import os
import sys
import json
import hashlib
import datetime as dt
import numpy as np
import pandas as pd
import joblib
from sklearn.model_selection import train_test_split

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as C
from features import add_features, TARGET


def _roles() -> dict:
    df = add_features(pd.read_csv(C.RAW_CSV).drop_duplicates().reset_index(drop=True))
    ref, tmp = train_test_split(df, test_size=0.40, stratify=df[TARGET], random_state=C.RANDOM_STATE)
    holdout, pool = train_test_split(tmp, test_size=0.50, stratify=tmp[TARGET], random_state=C.RANDOM_STATE)
    return {"reference": ref.reset_index(drop=True),
            "holdout": holdout.reset_index(drop=True),
            "pool": pool.reset_index(drop=True)}


def get_reference():
    return _roles()["reference"]


def get_holdout():
    return _roles()["holdout"]


def _inject_drift(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    for col, shift in [("V14", -2.5), ("V17", -2.0), ("log_amount", 0.8)]:
        d[col] = d[col] + shift
    return d


def make_window(n: int = 8000, drift: bool = False, seed: int | None = None) -> str:
    pool = _roles()["pool"]
    n = min(n, len(pool))
    rng = np.random.RandomState(C.RANDOM_STATE if seed is None else seed)
    window = pool.iloc[rng.choice(len(pool), size=n, replace=False)].reset_index(drop=True)
    if drift:
        window = _inject_drift(window)
    return save_snapshot(window, kind="window", meta={"drift_injected": bool(drift), "n_rows": int(n)})


def save_snapshot(df: pd.DataFrame, kind: str, meta: dict | None = None) -> str:
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    existing = [d for d in os.listdir(C.FEATURE_STORE) if d.startswith(kind)]
    version = f"{kind}-{len(existing)+1:04d}-{stamp}"
    vdir = os.path.join(C.FEATURE_STORE, version)
    os.makedirs(vdir, exist_ok=True)
    joblib.dump(df, os.path.join(vdir, "data.pkl"), compress=3)
    digest = hashlib.md5(pd.util.hash_pandas_object(df, index=True).values.tobytes()).hexdigest()
    sidecar = {"version": version, "kind": kind, "created_at": stamp, "n_rows": len(df),
               "n_cols": df.shape[1], "md5": digest, **(meta or {})}
    with open(os.path.join(vdir, "meta.json"), "w") as f:
        json.dump(sidecar, f, indent=2)
    return vdir


def load_snapshot(vdir: str) -> pd.DataFrame:
    return joblib.load(os.path.join(vdir, "data.pkl"))


def latest_snapshot(kind: str = "window"):
    cands = sorted(d for d in os.listdir(C.FEATURE_STORE) if d.startswith(kind))
    return os.path.join(C.FEATURE_STORE, cands[-1]) if cands else None
