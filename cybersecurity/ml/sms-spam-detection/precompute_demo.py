"""Offline precompute for the SMS-spam v2 site dashboards (binary, linear TF-IDF).

Everything the dashboards render is computed here from the self-contained artifact
(bundles vectorizer/model/coef/vocab + X_test/y_test/X_ref text). The model is linear,
so local explanations are EXACT (tfidf(token) * coef(token)) — no SHAP needed.

MLOps note: this project has NO committed MLflow registry, so the registry + the
champion-vs-challenger + approval cycle are emitted as a clearly-flagged illustrative
scenario (illustrative=True). The data-drift monitor IS real (serving vs training text).

Run from this directory:  python precompute_demo.py
Writes: ../../../site/public/demo-data/sms-spam.json
"""
from __future__ import annotations
import os
import sys
import json
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, "app")
OUT = os.path.abspath(os.path.join(HERE, "..", "..", "..", "site", "public", "demo-data", "sms-spam.json"))

sys.path.insert(0, APP)
os.chdir(APP)
import core  # noqa: E402

DRIFT_COLS = ["length", "n_digits", "n_words", "n_upper"]
PRETTY = {"length": "Message length", "n_digits": "Digit count", "n_words": "Word count", "n_upper": "Uppercase letters"}

EXAMPLES = [
    {"name": "Prize scam", "text": "Congratulations! You've WON a FREE $1000 gift card. Click http://bit.ly/claim now to claim your prize!"},
    {"name": "Bank phish", "text": "URGENT: your account is locked. Verify at http://secure-bank-login.com to restore access immediately."},
    {"name": "Normal message", "text": "Hey, are we still meeting for lunch at 1pm today?"},
    {"name": "Subtle nudge", "text": "Your parcel could not be delivered. Reschedule here: http://track-parcel.info/redeliver"},
]


def downsample(xs, ys, n=80):
    xs, ys = np.asarray(xs), np.asarray(ys)
    idx = np.arange(len(xs)) if len(xs) <= n else np.unique(np.linspace(0, len(xs) - 1, n).astype(int))
    return [[round(float(xs[i]), 5), round(float(ys[i]), 5)] for i in idx]


def build():
    art = core.load_artifact()
    texts = list(art["X_test_text"])
    y = np.asarray(art["y_test"]).astype(int)
    thr = float(art["threshold"])

    m = core.performance_metrics(art, texts, y, thr)
    proba = core.proba_text(art, texts)
    cm = np.asarray(m["confusion"])
    fpr, tpr = m["roc"]
    rec, prec = m["pr"]

    # ---- threshold sweep (client drives a live slider) ----
    P = int((y == 1).sum()); N = int((y == 0).sum())
    sweep = []
    for t in np.round(np.arange(0.05, 0.96, 0.02), 2):
        pred = proba >= t
        tp = int(np.sum(pred & (y == 1))); fp = int(np.sum(pred & (y == 0)))
        fn = P - tp; tn = N - fp
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / P if P else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
        acc = (tp + tn) / (tp + tn + fp + fn)
        sweep.append({"t": float(t), "tp": tp, "fp": fp, "fn": fn, "tn": tn,
                      "precision": round(precision, 4), "recall": round(recall, 4),
                      "f1": round(f1, 4), "accuracy": round(acc, 4)})

    # ---- latency + resources ----
    lat = core.benchmark_latency(art, texts, n=200)
    lm = np.asarray(lat["latencies_ms"])
    counts, edges = np.histogram(lm, bins=30)
    res = core.resource_usage()

    # ---- global spam-driving tokens (linear coefficients) ----
    gt = core.global_tokens(art, top=15)
    global_tokens = [{"token": str(r["token"]), "weight": round(float(r["weight"]), 4)} for _, r in gt.iterrows()]

    # ---- worked examples: exact per-token local explanation ----
    examples = []
    for e in EXAMPLES:
        p = float(core.proba_text(art, [e["text"]])[0])
        ex = core.explain_text(art, e["text"], top=10)
        examples.append({"name": e["name"], "text": e["text"], "probability": round(p, 5),
                         "flag": bool(p >= thr),
                         "tokens": [{"token": str(r["token"]), "contribution": round(float(r["contribution"]), 5)}
                                    for _, r in ex.iterrows()]})

    # ---- drift (REAL PSI: reference vs serving text features) ----
    ref_f = core.text_features(art["X_ref_text"])
    cur_f = core.text_features(art["X_test_text"])
    drep = core.drift_report(ref_f, cur_f, DRIFT_COLS)
    drift = [{"feature": PRETTY.get(r["feature"], r["feature"]), "PSI": float(r["PSI"]), "status": r["status"]}
             for _, r in drep.iterrows()]

    # ---- MLOps: NO real registry -> illustrative registry + cycle; drift is real ----
    s = m["scores"]
    champ = {"version": 1, "roc_auc": round(float(s["ROC_AUC"]), 4), "pr_auc": round(float(s["PR_AUC"]), 4),
             "recall": round(float(s["Recall"]), 4), "precision": round(float(s["Precision"]), 4)}
    chal = {"version": 2,
            "roc_auc": round(min(1.0, champ["roc_auc"] + 0.003), 4),
            "pr_auc": round(min(1.0, champ["pr_auc"] + 0.012), 4),
            "recall": round(min(1.0, champ["recall"] + 0.02), 4),
            "precision": round(min(1.0, champ["precision"] + 0.005), 4)}
    registry_rows = [{"version": 1, "alias": "production (champion)",
                      "roc_auc": champ["roc_auc"], "pr_auc": champ["pr_auc"], "model_name": art.get("model_name", "")}]
    gate_reasons = [
        f"PR-AUC (primary): challenger {chal['pr_auc']} vs champion {champ['pr_auc']} (need ≥ +0.0) → PASS",
        f"Recall guardrail: challenger {chal['recall']} vs champion {champ['recall']} (tolerance 0.02) → PASS",
    ]

    out = {
        "model_name": art.get("model_name", "SMS spam model"),
        "trained_on": "5,574 labelled SMS messages",
        "threshold_default": round(thr, 4),
        "prod_version": 1,
        "scores": {k: round(float(v), 4) for k, v in s.items()},
        "confusion": [[int(cm[0, 0]), int(cm[0, 1])], [int(cm[1, 0]), int(cm[1, 1])]],
        "baseline": round(float(m["baseline"]), 4),
        "n_test": int(len(y)),
        "roc": downsample(fpr, tpr, 80),
        "pr": downsample(rec, prec, 80),
        "sweep": sweep,
        "latency": {"p50": round(lat["p50"], 3), "p95": round(lat["p95"], 3), "p99": round(lat["p99"], 3),
                    "mean": round(lat["mean"], 3), "throughput_rps": round(lat["throughput_rps"], 1),
                    "hist": {"edges": [round(float(e), 4) for e in edges], "counts": [int(c) for c in counts]}},
        "resources": {"process_mem_mb": round(res["process_mem_mb"], 1), "system_mem_pct": round(res["system_mem_pct"], 1),
                      "cpu_pct": round(res["cpu_pct"], 1), "n_cores": int(res["n_cores"])},
        "global_tokens": global_tokens,
        "examples": examples,
        "drift": drift,
        "mlops": {"registry": registry_rows, "registry_real": False, "prod_version": 1,
                  "champion": champ, "challenger": chal, "illustrative": True,
                  "gate_passed": True, "gate_reasons": gate_reasons, "drift_monitor": drift},
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(out, f, separators=(",", ":"))
    print(f"wrote {OUT}  ({os.path.getsize(OUT)/1024:.1f} KB)  spam={P}/{len(y)} examples={len(examples)}")


if __name__ == "__main__":
    build()
