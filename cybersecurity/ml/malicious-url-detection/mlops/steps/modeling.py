"""Pure training + evaluation for the URL-threat model (multi-class, cost-sensitive)."""
from __future__ import annotations
import os
import sys
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import f1_score, recall_score, accuracy_score, roc_auc_score

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from features import build_preprocessor, FEATURE_COLS, TARGET


def train_model(train_df: pd.DataFrame, random_state: int = 42) -> dict:
    X, y = train_df[FEATURE_COLS], train_df[TARGET]
    pre = build_preprocessor()
    model = HistGradientBoostingClassifier(max_iter=200, class_weight="balanced", random_state=random_state)
    model.fit(pre.fit_transform(X), y)
    return {"model": model, "preprocessor": pre,
            "feature_names": list(pre.get_feature_names_out()),
            "model_name": "HistGradientBoosting (cost-sensitive, multi-class)"}


def evaluate_artifact(artifact: dict, test_df: pd.DataFrame) -> dict:
    X, y = test_df[FEATURE_COLS], test_df[TARGET]
    Xt = artifact["preprocessor"].transform(X)
    pred = artifact["model"].predict(Xt)
    proba = artifact["model"].predict_proba(Xt)
    return {"macro_f1": float(f1_score(y, pred, average="macro")),
            "macro_recall": float(recall_score(y, pred, average="macro")),
            "accuracy": float(accuracy_score(y, pred)),
            "macro_roc_auc": float(roc_auc_score(y, proba, multi_class="ovr", average="macro",
                                                 labels=artifact["model"].classes_)),
            "n_test": int(len(y))}
