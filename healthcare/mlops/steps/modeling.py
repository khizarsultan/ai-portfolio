"""Pure training + evaluation logic (no MLflow / Evidently here, so it stays testable).

Produces an artifact dict compatible with the healthcare dashboard:
  {model, preprocessor, threshold, feature_names, model_name}
"""
from __future__ import annotations
import os
import sys
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import (roc_auc_score, average_precision_score, f1_score,
                             precision_score, recall_score, accuracy_score,
                             precision_recall_curve)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from preprocessing import build_preprocessor, TARGET


def _best_threshold(y_true, proba) -> float:
    prec, rec, thr = precision_recall_curve(y_true, proba)
    f1 = 2 * prec * rec / (prec + rec + 1e-12)
    return float(thr[int(np.nanargmax(f1[:-1]))])


def train_model(train_df: pd.DataFrame, random_state: int = 42) -> dict:
    """Fit preprocessor + HistGradientBoosting; tune the decision threshold on a val slice."""
    X, y = train_df.drop(columns=[TARGET]), train_df[TARGET]
    X_fit, X_val, y_fit, y_val = train_test_split(
        X, y, test_size=0.20, stratify=y, random_state=random_state)

    pre = build_preprocessor()
    X_fit_t = pre.fit_transform(X_fit)
    model = HistGradientBoostingClassifier(max_iter=200, random_state=random_state)
    model.fit(X_fit_t, y_fit)
    thr = _best_threshold(y_val, model.predict_proba(pre.transform(X_val))[:, 1])

    return {"model": model, "preprocessor": pre, "threshold": thr,
            "feature_names": list(pre.get_feature_names_out()),
            "model_name": "HistGradientBoosting"}


def evaluate_artifact(artifact: dict, test_df: pd.DataFrame) -> dict:
    """Score an artifact on a holdout set -> metrics dict (threshold-independent + at-threshold)."""
    X, y = test_df.drop(columns=[TARGET]), test_df[TARGET]
    proba = artifact["model"].predict_proba(artifact["preprocessor"].transform(X))[:, 1]
    pred = (proba >= artifact["threshold"]).astype(int)
    return {
        "roc_auc": float(roc_auc_score(y, proba)),
        "pr_auc": float(average_precision_score(y, proba)),
        "precision": float(precision_score(y, pred, zero_division=0)),
        "recall": float(recall_score(y, pred)),
        "f1": float(f1_score(y, pred)),
        "accuracy": float(accuracy_score(y, pred)),
        "n_test": int(len(y)),
        "threshold": float(artifact["threshold"]),
    }
