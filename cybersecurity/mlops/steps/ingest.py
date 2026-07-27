"""Data ingestion + feature store for the URL-threat pipeline (subsampled for speed)."""
from __future__ import annotations
import os
import sys
import json
import hashlib
import datetime as dt
from functools import lru_cache
import numpy as np
import pandas as pd
import joblib
from sklearn.model_selection import train_test_split

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as C
from features import featurize, apply_top_tlds, FEATURE_COLS, TARGET


@lru_cache(maxsize=1)
def _roles():
    df = pd.read_csv(C.RAW_CSV).drop_duplicates().reset_index(drop=True)
    df["url"] = df["url"].str.strip()
    bad = df.groupby("url")[TARGET].nunique()
    df = df[~df["url"].isin(bad[bad > 1].index)].reset_index(drop=True)
    if len(df) > C.SAMPLE_ROWS:
        df = df.groupby(TARGET, group_keys=False).apply(
            lambda g: g.sample(max(1, int(C.SAMPLE_ROWS * len(g) / len(df))), random_state=C.RANDOM_STATE))
    F = featurize(df["url"]); F[TARGET] = df[TARGET].values
    ref, tmp = train_test_split(F, test_size=0.40, stratify=F[TARGET], random_state=C.RANDOM_STATE)
    holdout, pool = train_test_split(tmp, test_size=0.50, stratify=tmp[TARGET], random_state=C.RANDOM_STATE)
    top = list(ref["tld"].value_counts().head(15).index)
    out = {}
    for name, part in [("reference", ref), ("holdout", holdout), ("pool", pool)]:
        out[name] = apply_top_tlds(part, top)[FEATURE_COLS + [TARGET]].reset_index(drop=True)
    out["top_tlds"] = top
    return out


def get_reference():
    return _roles()["reference"]


def get_holdout():
    return _roles()["holdout"]


def get_top_tlds():
    return _roles()["top_tlds"]


def _inject_drift(df):
    d = df.copy()
    for col, s in [("url_len", 25), ("n_digits", 6), ("url_entropy", 0.4)]:
        d[col] = d[col] + s
    return d


def make_window(n: int = 8000, drift: bool = False, seed: int | None = None) -> str:
    pool = _roles()["pool"]
    n = min(n, len(pool))
    rng = np.random.RandomState(C.RANDOM_STATE if seed is None else seed)
    w = pool.iloc[rng.choice(len(pool), size=n, replace=False)].reset_index(drop=True)
    if drift:
        w = _inject_drift(w)
    return save_snapshot(w, kind="window", meta={"drift_injected": bool(drift), "n_rows": int(n)})


def save_snapshot(df, kind, meta=None) -> str:
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    existing = [d for d in os.listdir(C.FEATURE_STORE) if d.startswith(kind)]
    version = f"{kind}-{len(existing)+1:04d}-{stamp}"
    vdir = os.path.join(C.FEATURE_STORE, version)
    os.makedirs(vdir, exist_ok=True)
    joblib.dump(df, os.path.join(vdir, "data.pkl"), compress=3)
    digest = hashlib.md5(pd.util.hash_pandas_object(df, index=True).values.tobytes()).hexdigest()
    with open(os.path.join(vdir, "meta.json"), "w") as f:
        json.dump({"version": version, "kind": kind, "created_at": stamp, "n_rows": len(df),
                   "md5": digest, **(meta or {})}, f, indent=2)
    return vdir


def load_snapshot(vdir):
    return joblib.load(os.path.join(vdir, "data.pkl"))


def latest_snapshot(kind="window"):
    cands = sorted(d for d in os.listdir(C.FEATURE_STORE) if d.startswith(kind))
    return os.path.join(C.FEATURE_STORE, cands[-1]) if cands else None
