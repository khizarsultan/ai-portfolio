"""Shared feature engineering + preprocessor for the fraud model.

Used by train.py (offline) and the live dashboard so training and inference apply
identical transforms. Leakage-safe: every feature is a row-wise function of the raw
columns; the preprocessor is fit on the training split only.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler, OneHotEncoder

TARGET = "Class"
RAW_COLS = ["Time"] + [f"V{i}" for i in range(1, 29)] + ["Amount"]
AMOUNT_BINS = [-0.01, 1, 10, 50, 200, 1e9]
AMOUNT_LABELS = ["<1", "1-10", "10-50", "50-200", "200+"]


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """Engineer hour-of-day, log-amount, a $0 flag, and a binned-amount categorical."""
    d = df.copy()
    d["hour"] = (d["Time"] // 3600 % 24).astype(int)
    d["log_amount"] = np.log1p(d["Amount"])
    d["amount_zero"] = (d["Amount"] == 0).astype(int)
    d["amount_bin"] = pd.cut(d["Amount"], bins=AMOUNT_BINS, labels=AMOUNT_LABELS)
    return d


def build_preprocessor(feature_cols) -> ColumnTransformer:
    """Standard-scale numerics, one-hot the binned amount, pass the $0 flag through."""
    num_cols = [c for c in feature_cols if c not in ("amount_bin", "amount_zero", "Amount")]
    return ColumnTransformer([
        ("num", StandardScaler(), num_cols),
        ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), ["amount_bin"]),
        ("bin", "passthrough", ["amount_zero"]),
    ])
