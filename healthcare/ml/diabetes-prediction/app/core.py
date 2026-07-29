"""Streamlit-free core logic: model loading, performance, XAI (SHAP),
system benchmarking, and data-drift (PSI). Kept UI-agnostic so it can be
unit-tested and reused.
"""
from __future__ import annotations
import time
import numpy as np
import pandas as pd
import joblib
import psutil
from sklearn.metrics import (roc_auc_score, average_precision_score, f1_score,
                             precision_score, recall_score, accuracy_score,
                             confusion_matrix, precision_recall_curve, roc_curve)

from preprocessing import load_splits, clean, add_features, TARGET

ARTIFACT_PATH = "diabetes_model.joblib"
DATA_PATH = "diabetes_prediction_dataset.csv"

RAW_INPUT_COLS = ["gender", "age", "hypertension", "heart_disease",
                  "smoking_history", "bmi", "HbA1c_level", "blood_glucose_level"]


# ----------------------------- loading -----------------------------
def load_artifact(path: str = ARTIFACT_PATH) -> dict:
    return joblib.load(path)


def get_data(csv_path: str = DATA_PATH) -> dict:
    """Deterministic 80/10/10 splits + transformed matrices (same as training)."""
    return load_splits(csv_path, transform=True)


# --------------------------- prediction ----------------------------
def raw_to_frame(inp: dict) -> pd.DataFrame:
    """Build a single-row engineered frame from raw user input."""
    df = pd.DataFrame([{c: inp[c] for c in RAW_INPUT_COLS}])
    # bmi_missing flag never set for live input (user provides a real bmi)
    df["bmi_missing"] = 0
    df = add_features(df)
    return df


def predict_proba_raw(artifact: dict, inp: dict) -> float:
    df = raw_to_frame(inp)
    Xt = artifact["preprocessor"].transform(df)
    return float(artifact["model"].predict_proba(Xt)[:, 1][0])


# ------------------- what-if / counterfactual (model-exact) -------------------
# Clinically plausible sweep ranges for the numeric inputs (min, max).
CLINICAL_RANGES = {
    "HbA1c_level": (4.0, 12.0, "HbA1c level"),
    "blood_glucose_level": (70.0, 300.0, "Blood glucose"),
    "bmi": (15.0, 45.0, "BMI"),
    "age": (18.0, 90.0, "Age"),
}


def what_if_curve(artifact: dict, base_inp: dict, feature: str, n: int = 48):
    """Individual Conditional Expectation: re-score the SAME patient as one feature
    sweeps its plausible range (all other inputs held fixed). Returns (xs, probas)."""
    lo, hi, _ = CLINICAL_RANGES[feature]
    xs = np.linspace(lo, hi, n)
    ys = np.array([predict_proba_raw(artifact, {**base_inp, feature: float(v)}) for v in xs])
    return xs, ys


def threshold_crossings(xs, ys, thr: float):
    """Values of x where the risk curve crosses the decision threshold (linear interp)."""
    out = []
    for i in range(1, len(xs)):
        a, b = ys[i - 1] - thr, ys[i] - thr
        if a == 0:
            out.append(float(xs[i - 1]))
        elif a * b < 0:
            out.append(float(xs[i - 1] + (a / (a - b)) * (xs[i] - xs[i - 1])))
    return out


# --------------------------- performance ---------------------------
def performance_metrics(model, X_te_t, y_te, threshold: float) -> dict:
    proba = model.predict_proba(X_te_t)[:, 1]
    pred = (proba >= threshold).astype(int)
    fpr, tpr, _ = roc_curve(y_te, proba)
    prec, rec, _ = precision_recall_curve(y_te, proba)
    return {
        "scores": {
            "ROC_AUC": roc_auc_score(y_te, proba),
            "PR_AUC": average_precision_score(y_te, proba),
            "Precision": precision_score(y_te, pred, zero_division=0),
            "Recall": recall_score(y_te, pred),
            "F1": f1_score(y_te, pred),
            "Accuracy": accuracy_score(y_te, pred),
        },
        "confusion": confusion_matrix(y_te, pred),
        "roc": (fpr, tpr),
        "pr": (rec, prec),
        "proba": proba,
        "baseline": float(np.mean(y_te)),
    }


# ------------------------------ XAI --------------------------------
def build_explainer(model, background: np.ndarray):
    """Model-agnostic SHAP explainer (robust across sklearn models incl. HGB)."""
    import shap
    bg = shap.sample(background, min(100, len(background)), random_state=0)
    return shap.Explainer(model.predict_proba, bg)


def shap_values_pos(explainer, X: np.ndarray):
    """Return SHAP Explanation for the positive class (diabetes=1)."""
    exp = explainer(X)
    # predict_proba -> shape (n, features, 2); take positive class
    if exp.values.ndim == 3:
        return exp[..., 1]
    return exp


def global_importance(shap_exp, feature_names) -> pd.DataFrame:
    """Mean absolute SHAP value per feature -> global importance ranking."""
    mean_abs = np.abs(shap_exp.values).mean(axis=0)
    return (pd.DataFrame({"feature": list(feature_names), "importance": mean_abs})
            .sort_values("importance", ascending=False)
            .reset_index(drop=True))


def local_contributions(shap_exp_row, feature_names) -> pd.DataFrame:
    """Signed SHAP contributions for a single prediction (row 0 of the Explanation)."""
    vals = np.asarray(shap_exp_row.values).ravel()
    df = pd.DataFrame({"feature": list(feature_names), "shap": vals})
    df["abs"] = df["shap"].abs()
    return df.sort_values("abs", ascending=False).reset_index(drop=True)


# --------------------------- system perf ---------------------------
def benchmark_latency(model, X_sample: np.ndarray, n: int = 200) -> dict:
    """Single-row inference latencies (ms) -> p50/p95/p99 + throughput."""
    n = min(n, len(X_sample))
    lat = np.empty(n)
    for i in range(n):
        row = X_sample[i:i+1]
        t0 = time.perf_counter()
        model.predict_proba(row)
        lat[i] = (time.perf_counter() - t0) * 1000.0
    # batch throughput
    t0 = time.perf_counter()
    model.predict_proba(X_sample[:n])
    batch_s = time.perf_counter() - t0
    return {
        "latencies_ms": lat,
        "p50": float(np.percentile(lat, 50)),
        "p95": float(np.percentile(lat, 95)),
        "p99": float(np.percentile(lat, 99)),
        "mean": float(lat.mean()),
        "throughput_rps": float(n / batch_s) if batch_s > 0 else float("nan"),
    }


def resource_usage() -> dict:
    p = psutil.Process()
    return {
        "process_mem_mb": p.memory_info().rss / 1e6,
        "system_mem_pct": psutil.virtual_memory().percent,
        "cpu_pct": psutil.cpu_percent(interval=0.2),
        "n_cores": psutil.cpu_count(),
    }


# ---------------------------- drift (PSI) --------------------------
def psi(reference: np.ndarray, current: np.ndarray, bins: int = 10) -> float:
    """Population Stability Index between reference and current distributions."""
    ref = reference[~np.isnan(reference)]
    cur = current[~np.isnan(current)]
    if len(ref) == 0 or len(cur) == 0:
        return float("nan")
    quantiles = np.unique(np.quantile(ref, np.linspace(0, 1, bins + 1)))
    if len(quantiles) < 3:
        return 0.0
    quantiles[0], quantiles[-1] = -np.inf, np.inf
    r = np.histogram(ref, bins=quantiles)[0] / len(ref)
    c = np.histogram(cur, bins=quantiles)[0] / len(cur)
    r = np.clip(r, 1e-6, None)
    c = np.clip(c, 1e-6, None)
    return float(np.sum((c - r) * np.log(c / r)))


def drift_report(reference_df: pd.DataFrame, current_df: pd.DataFrame,
                 cols=("age", "bmi", "HbA1c_level", "blood_glucose_level")) -> pd.DataFrame:
    rows = []
    for c in cols:
        val = psi(reference_df[c].values.astype(float), current_df[c].values.astype(float))
        status = "OK" if val < 0.1 else ("WARNING" if val < 0.25 else "DRIFT")
        rows.append({"feature": c, "PSI": round(val, 4), "status": status})
    return pd.DataFrame(rows)
