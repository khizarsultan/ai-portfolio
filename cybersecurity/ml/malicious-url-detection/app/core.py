"""UI-agnostic core for the URL dashboard: model loading, MULTI-CLASS performance,
XAI (SHAP), system benchmarking, and data-drift (PSI). Same shape as the healthcare
and finance cores, adapted for 4-class classification.
"""
from __future__ import annotations
import time
import numpy as np
import pandas as pd
import joblib
import psutil
from sklearn.metrics import (f1_score, recall_score, precision_score, accuracy_score,
                             confusion_matrix, roc_auc_score)

import features as feats

ARTIFACT_PATH = "artifact.joblib"


# ----------------------------- loading -----------------------------
def load_artifact(path: str = ARTIFACT_PATH) -> dict:
    return joblib.load(path)


def transform(artifact: dict, df_eng: pd.DataFrame) -> np.ndarray:
    return artifact["preprocessor"].transform(df_eng[artifact["input_cols"]])


def featurize_url(artifact: dict, url: str) -> pd.DataFrame:
    """Raw URL string -> one-row engineered frame using the training-time TLD set."""
    F = feats.featurize(pd.Series([url]))
    F = feats.apply_top_tlds(F, artifact["top_tlds"])
    return F[artifact["input_cols"]]


# --------------------------- performance (multi-class) -------------
def performance_metrics(model, X_te_t, y_te, classes) -> dict:
    pred = model.predict(X_te_t)
    proba = model.predict_proba(X_te_t)
    per_class = pd.DataFrame({
        "precision": precision_score(y_te, pred, average=None, labels=classes, zero_division=0),
        "recall": recall_score(y_te, pred, average=None, labels=classes, zero_division=0),
        "f1": f1_score(y_te, pred, average=None, labels=classes, zero_division=0),
        "support": [int((y_te == c).sum()) for c in classes],
    }, index=classes)
    return {
        "accuracy": accuracy_score(y_te, pred),
        "macro_f1": f1_score(y_te, pred, average="macro"),
        "macro_recall": recall_score(y_te, pred, average="macro"),
        "macro_roc_auc": roc_auc_score(y_te, proba, multi_class="ovr", average="macro", labels=model.classes_),
        "per_class": per_class,
        "confusion": confusion_matrix(y_te, pred, labels=classes, normalize="true"),
        "confusion_counts": confusion_matrix(y_te, pred, labels=classes),
    }


# ------------------------------ XAI --------------------------------
def build_explainer(model, background: np.ndarray):
    import shap
    bg = shap.sample(background, min(80, len(background)), random_state=0)
    return shap.Explainer(model.predict_proba, bg)


def shap_values_class(explainer, X: np.ndarray, class_idx: int):
    """SHAP Explanation for one class (predict_proba -> shape (n, features, n_classes))."""
    exp = explainer(X)
    return exp[..., class_idx] if exp.values.ndim == 3 else exp


def global_importance_mc(explainer, X: np.ndarray, feature_names) -> pd.DataFrame:
    """Mean |SHAP| aggregated over samples AND classes -> overall importance."""
    exp = explainer(X)
    vals = np.abs(exp.values)
    mean_abs = vals.mean(axis=(0, 2)) if vals.ndim == 3 else vals.mean(axis=0)
    return (pd.DataFrame({"feature": list(feature_names), "importance": mean_abs})
            .sort_values("importance", ascending=False).reset_index(drop=True))


def local_contributions(shap_exp_row, feature_names) -> pd.DataFrame:
    vals = np.asarray(shap_exp_row.values).ravel()
    df = pd.DataFrame({"feature": list(feature_names), "shap": vals})
    df["abs"] = df["shap"].abs()
    return df.sort_values("abs", ascending=False).reset_index(drop=True)


# --------------------------- system perf ---------------------------
def benchmark_latency(model, X_sample: np.ndarray, n: int = 200) -> dict:
    n = min(n, len(X_sample))
    lat = np.empty(n)
    for i in range(n):
        t0 = time.perf_counter()
        model.predict_proba(X_sample[i:i+1])
        lat[i] = (time.perf_counter() - t0) * 1000.0
    t0 = time.perf_counter()
    model.predict_proba(X_sample[:n])
    batch_s = time.perf_counter() - t0
    return {"latencies_ms": lat, "p50": float(np.percentile(lat, 50)),
            "p95": float(np.percentile(lat, 95)), "p99": float(np.percentile(lat, 99)),
            "mean": float(lat.mean()),
            "throughput_rps": float(n / batch_s) if batch_s > 0 else float("nan")}


def resource_usage() -> dict:
    p = psutil.Process()
    return {"process_mem_mb": p.memory_info().rss / 1e6,
            "system_mem_pct": psutil.virtual_memory().percent,
            "cpu_pct": psutil.cpu_percent(interval=0.2), "n_cores": psutil.cpu_count()}


# ---------------------------- drift (PSI) --------------------------
def psi(reference: np.ndarray, current: np.ndarray, bins: int = 10) -> float:
    ref = reference[~np.isnan(reference)]
    cur = current[~np.isnan(current)]
    if len(ref) == 0 or len(cur) == 0:
        return float("nan")
    quantiles = np.unique(np.quantile(ref, np.linspace(0, 1, bins + 1)))
    if len(quantiles) < 3:
        return 0.0
    quantiles[0], quantiles[-1] = -np.inf, np.inf
    r = np.clip(np.histogram(ref, bins=quantiles)[0] / len(ref), 1e-6, None)
    c = np.clip(np.histogram(cur, bins=quantiles)[0] / len(cur), 1e-6, None)
    return float(np.sum((c - r) * np.log(c / r)))


def drift_report(reference_df: pd.DataFrame, current_df: pd.DataFrame, cols) -> pd.DataFrame:
    rows = []
    for c in cols:
        val = psi(reference_df[c].values.astype(float), current_df[c].values.astype(float))
        status = "OK" if val < 0.1 else ("WARNING" if val < 0.25 else "DRIFT")
        rows.append({"feature": c, "PSI": round(val, 4), "status": status})
    return pd.DataFrame(rows)
