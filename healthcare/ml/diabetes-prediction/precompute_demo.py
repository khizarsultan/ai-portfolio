"""Offline precompute for the diabetes v2 site dashboards.

Runs the real model + SHAP + performance sweep + latency + drift, and reads the
real MLOps state files, then writes ONE static JSON the Vercel site renders
client-side. Heavy libs (shap, plotly, evidently, mlflow) never touch Vercel —
they run here, offline, and the site ships only numbers.

Run from this directory:
    python precompute_demo.py
Writes: ../../../site/public/demo-data/diabetes.json
"""
from __future__ import annotations
import os
import sys
import json
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, "app")
MLOPS = os.path.join(HERE, "mlops")
OUT = os.path.abspath(os.path.join(HERE, "..", "..", "..", "site", "public", "demo-data", "diabetes.json"))

sys.path.insert(0, APP)
os.chdir(APP)  # core.py uses relative paths for the artifact + csv

import core  # noqa: E402

RAW_COLS = core.RAW_INPUT_COLS
PRETTY = {"HbA1c_level": "HbA1c level", "blood_glucose_level": "Blood glucose",
          "bmi": "BMI", "age": "Age"}


def _pretty(name: str) -> str:
    for p in ("log__", "num__", "cat__", "bin__", "remainder__"):
        name = name.replace(p, "")
    return name.replace("_", " ").strip()


def downsample(xs, ys, n=80):
    xs, ys = np.asarray(xs), np.asarray(ys)
    if len(xs) <= n:
        idx = np.arange(len(xs))
    else:
        idx = np.unique(np.linspace(0, len(xs) - 1, n).astype(int))
    return [[round(float(xs[i]), 5), round(float(ys[i]), 5)] for i in idx]


def build():
    art, data = core.load_artifact(), core.get_data()
    model = art["model"]
    feat_names = list(art["feature_names"])
    X_te_t, y_te = data["X_test_t"], np.asarray(data["y_test"])
    thr = float(art["threshold"])

    # ---- performance @ default threshold + curves ----
    m = core.performance_metrics(model, X_te_t, y_te, thr)
    proba = np.asarray(m["proba"])
    cm = m["confusion"]
    fpr, tpr = m["roc"]
    rec, prec = m["pr"]

    # ---- threshold sweep (client drives a live slider from this) ----
    P = int((y_te == 1).sum())
    N = int((y_te == 0).sum())
    sweep = []
    for t in np.round(np.arange(0.05, 0.96, 0.02), 2):
        pred = proba >= t
        tp = int(np.sum(pred & (y_te == 1)))
        fp = int(np.sum(pred & (y_te == 0)))
        fn = P - tp
        tn = N - fp
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / P if P else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
        acc = (tp + tn) / (tp + tn + fp + fn)
        sweep.append({"t": float(t), "tp": tp, "fp": fp, "fn": fn, "tn": tn,
                      "precision": round(precision, 4), "recall": round(recall, 4),
                      "f1": round(f1, 4), "accuracy": round(acc, 4)})

    # ---- latency + resources ----
    lat = art.get("latency") or core.benchmark_latency(model, X_te_t, n=200)
    lm = np.asarray(lat["latencies_ms"])
    counts, edges = np.histogram(lm, bins=30)
    res = core.resource_usage()

    # ---- SHAP: global importance + per-patient local + what-if ----
    gi = art.get("global_importance")
    if gi is None:
        expl = core.build_explainer(model, data["X_train_t"])
        gi = core.global_importance(core.shap_values_pos(expl, X_te_t[:150]), feat_names)
    global_importance = [{"feature": _pretty(r["feature"]), "importance": round(float(r["importance"]), 5)}
                         for _, r in gi.head(15).iterrows()]

    expl = core.build_explainer(model, data["X_train_t"])
    samples = [
        {"name": "54F · HbA1c 6.2 · glucose 145", "input": dict(
            gender="Female", age=54, hypertension=0, heart_disease=0,
            smoking_history="never", bmi=28.5, HbA1c_level=6.2, blood_glucose_level=145)},
        {"name": "67M · HbA1c 7.8 · glucose 210", "input": dict(
            gender="Male", age=67, hypertension=1, heart_disease=1,
            smoking_history="former", bmi=33.0, HbA1c_level=7.8, blood_glucose_level=210)},
        {"name": "31F · HbA1c 5.2 · glucose 95", "input": dict(
            gender="Female", age=31, hypertension=0, heart_disease=0,
            smoking_history="never", bmi=22.0, HbA1c_level=5.2, blood_glucose_level=95)},
    ]
    patients = []
    for s in samples:
        inp = s["input"]
        row = art["preprocessor"].transform(core.raw_to_frame(inp))
        p = core.predict_proba_raw(art, inp)
        contrib = core.local_contributions(core.shap_values_pos(expl, row), feat_names)
        local = [{"feature": _pretty(r["feature"]), "shap": round(float(r["shap"]), 5)}
                 for _, r in contrib.head(10).iterrows()]
        whatif = {}
        for fk, label in PRETTY.items():
            xs, ys = core.what_if_curve(art, inp, fk)
            crossings = core.threshold_crossings(xs, ys, thr)
            cur = float(inp[fk])
            nearest = min(crossings, key=lambda z: abs(z - cur)) if crossings else None
            whatif[fk] = {"label": label, "curve": downsample(xs, ys, 48),
                          "current": cur, "flip": (round(nearest, 2) if nearest is not None else None)}
        patients.append({"name": s["name"], "input": inp,
                         "probability": round(float(p), 5), "local": local, "whatif": whatif})

    # ---- drift (train vs test, real PSI) ----
    drift_df = core.drift_report(data["X_train"], data["X_test"])
    drift = [{"feature": PRETTY.get(r["feature"], r["feature"]), "PSI": float(r["PSI"]),
              "status": r["status"]} for _, r in drift_df.iterrows()]

    # ---- MLOps state (real pipeline output files) ----
    def _read(path, default):
        try:
            with open(os.path.join(MLOPS, path)) as f:
                return json.load(f)
        except Exception:
            return default

    pending = _read(os.path.join("state", "pending_approval.json"), {})
    drift_trigger = _read(os.path.join("reports", "drift-check.json"), {})
    approvals = []
    try:
        with open(os.path.join(MLOPS, "state", "approvals.jsonl")) as f:
            approvals = [json.loads(l) for l in f if l.strip()]
    except Exception:
        pass
    for a in approvals:  # redact email-style approver to first token
        if isinstance(a.get("approver"), str) and "@" in a["approver"]:
            a["approver"] = a["approver"].split("@")[0]
    prod_version = approvals[-1]["challenger_version"] if approvals else pending.get("champion_version")

    registry = []
    if pending:
        cv, chv = pending.get("champion_version"), pending.get("challenger_version")
        cm_, chm = pending.get("champion_metrics", {}), pending.get("challenger_metrics", {})
        registry.append({"version": prod_version or cv, "alias": "production (champion)",
                         "roc_auc": round(cm_.get("roc_auc", 0), 4), "pr_auc": round(cm_.get("pr_auc", 0), 4),
                         "recall": round(cm_.get("recall", 0), 4), "precision": round(cm_.get("precision", 0), 4)})
        registry.append({"version": chv, "alias": "challenger (pending approval)",
                         "roc_auc": round(chm.get("roc_auc", 0), 4), "pr_auc": round(chm.get("pr_auc", 0), 4),
                         "recall": round(chm.get("recall", 0), 4), "precision": round(chm.get("precision", 0), 4)})

    out = {
        "model_name": art.get("model_name", "Diabetes risk model"),
        "trained_on": "100,000 patient records",
        "threshold_default": round(thr, 4),
        "prod_version": prod_version,
        "scores": {k: round(float(v), 4) for k, v in m["scores"].items()},
        "confusion": [[int(cm[0, 0]), int(cm[0, 1])], [int(cm[1, 0]), int(cm[1, 1])]],
        "baseline": round(float(m["baseline"]), 4),
        "n_test": int(len(y_te)),
        "roc": downsample(fpr, tpr, 80),
        "pr": downsample(rec, prec, 80),
        "sweep": sweep,
        "latency": {"p50": round(lat["p50"], 3), "p95": round(lat["p95"], 3),
                    "p99": round(lat["p99"], 3), "mean": round(lat["mean"], 3),
                    "throughput_rps": round(lat["throughput_rps"], 1),
                    "hist": {"edges": [round(float(e), 4) for e in edges],
                             "counts": [int(c) for c in counts]}},
        "resources": {"process_mem_mb": round(res["process_mem_mb"], 1),
                      "system_mem_pct": round(res["system_mem_pct"], 1),
                      "cpu_pct": round(res["cpu_pct"], 1), "n_cores": int(res["n_cores"])},
        "global_importance": global_importance,
        "patients": patients,
        "drift": drift,
        "mlops": {"registry": registry, "prod_version": prod_version,
                  "gate_passed": pending.get("gate_passed"),
                  "gate_reasons": pending.get("gate_reasons", []),
                  "champion_version": pending.get("champion_version"),
                  "challenger_version": pending.get("challenger_version"),
                  "champion_metrics": pending.get("champion_metrics", {}),
                  "challenger_metrics": pending.get("challenger_metrics", {}),
                  "approvals": approvals,
                  "drift_trigger": drift_trigger},
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(out, f, separators=(",", ":"))
    print(f"wrote {OUT}  ({os.path.getsize(OUT)/1024:.1f} KB)")


if __name__ == "__main__":
    build()
