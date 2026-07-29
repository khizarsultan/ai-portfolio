"""UI-agnostic core for the SMS spam dashboard."""
from __future__ import annotations
import re
import time
import numpy as np
import pandas as pd
import joblib
import psutil
from sklearn.metrics import (roc_auc_score, average_precision_score, f1_score,
                             precision_score, recall_score, accuracy_score,
                             confusion_matrix, precision_recall_curve, roc_curve)

ARTIFACT_PATH = "artifact.joblib"


def load_artifact(path: str = ARTIFACT_PATH) -> dict:
    return joblib.load(path)


def proba_text(art, texts) -> np.ndarray:
    return art["model"].predict_proba(art["vectorizer"].transform(texts))[:, 1]


def performance_metrics(art, texts, y, threshold: float) -> dict:
    proba = proba_text(art, texts)
    pred = (proba >= threshold).astype(int)
    fpr, tpr, _ = roc_curve(y, proba)
    rec_c, prec_c = precision_recall_curve(y, proba)[1], precision_recall_curve(y, proba)[0]
    return {"scores": {"ROC_AUC": roc_auc_score(y, proba), "PR_AUC": average_precision_score(y, proba),
                       "Precision": precision_score(y, pred, zero_division=0), "Recall": recall_score(y, pred),
                       "F1": f1_score(y, pred), "Accuracy": accuracy_score(y, pred)},
            "confusion": confusion_matrix(y, pred), "roc": (fpr, tpr), "pr": (rec_c, prec_c),
            "baseline": float(np.mean(y))}


def explain_text(art, text: str, top: int = 10) -> pd.DataFrame:
    """Per-message token contributions toward spam = tfidf(token) * coef(token)."""
    v = art["vectorizer"].transform([text])
    contrib = v.multiply(art["coef"]).toarray().ravel()
    idx = np.nonzero(contrib)[0]
    if len(idx) == 0:
        return pd.DataFrame(columns=["token", "contribution"])
    df = pd.DataFrame({"token": art["vocab"][idx], "contribution": contrib[idx]})
    return df.reindex(df["contribution"].abs().sort_values(ascending=False).index).head(top).reset_index(drop=True)


def global_tokens(art, top: int = 15) -> pd.DataFrame:
    order = np.argsort(art["coef"])
    spam = [(art["vocab"][i], art["coef"][i]) for i in order[::-1][:top]]
    return pd.DataFrame(spam, columns=["token", "weight"])


def benchmark_latency(art, texts, n: int = 200) -> dict:
    texts = list(texts[:n]); n = len(texts)
    lat = np.empty(n)
    for i, t in enumerate(texts):
        t0 = time.perf_counter(); proba_text(art, [t]); lat[i] = (time.perf_counter() - t0) * 1000
    t0 = time.perf_counter(); proba_text(art, texts); batch = time.perf_counter() - t0
    return {"latencies_ms": lat, "p50": float(np.percentile(lat, 50)), "p95": float(np.percentile(lat, 95)),
            "p99": float(np.percentile(lat, 99)), "mean": float(lat.mean()),
            "throughput_rps": float(n / batch) if batch > 0 else float("nan")}


def resource_usage() -> dict:
    p = psutil.Process()
    return {"process_mem_mb": p.memory_info().rss / 1e6, "system_mem_pct": psutil.virtual_memory().percent,
            "cpu_pct": psutil.cpu_percent(interval=0.2), "n_cores": psutil.cpu_count()}


_DIGIT = re.compile(r"\d")
_URL = re.compile(r"http|www|\.com|\.co\b", re.I)


def text_features(texts) -> pd.DataFrame:
    s = pd.Series(list(texts))
    return pd.DataFrame({"length": s.str.len(), "n_digits": s.str.count(_DIGIT),
                         "n_words": s.str.split().str.len(), "n_upper": s.str.count(r"[A-Z]")})


def psi(ref, cur, bins: int = 10) -> float:
    ref, cur = ref[~np.isnan(ref)], cur[~np.isnan(cur)]
    if len(ref) == 0 or len(cur) == 0:
        return float("nan")
    q = np.unique(np.quantile(ref, np.linspace(0, 1, bins + 1)))
    if len(q) < 3:
        return 0.0
    q[0], q[-1] = -np.inf, np.inf
    r = np.clip(np.histogram(ref, bins=q)[0] / len(ref), 1e-6, None)
    c = np.clip(np.histogram(cur, bins=q)[0] / len(cur), 1e-6, None)
    return float(np.sum((c - r) * np.log(c / r)))


def drift_report(ref_df, cur_df, cols) -> pd.DataFrame:
    rows = []
    for c in cols:
        val = psi(ref_df[c].values.astype(float), cur_df[c].values.astype(float))
        rows.append({"feature": c, "PSI": round(val, 4),
                     "status": "OK" if val < 0.1 else ("WARNING" if val < 0.25 else "DRIFT")})
    return pd.DataFrame(rows)
