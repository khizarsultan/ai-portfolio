"""Offline precompute for the Credit-card-fraud v2 site dashboards (binary, imbalanced).

Computes everything the dashboards render from the self-contained artifact (bundles
X_test/y_test/X_ref/background/global_importance/latency) plus the real MLflow
registry. The Vercel site ships only numbers — no shap/mlflow at runtime.

MLOps note: registry + drift are REAL; there is no committed challenger/approval
state and the raw CSV is gone, so the champion-vs-challenger + approval cycle is
emitted as a clearly-flagged illustrative scenario (illustrative=True).

Run from this directory:  python precompute_demo.py
Writes: ../../../site/public/demo-data/fraud.json
"""
from __future__ import annotations
import os
import sys
import json
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, "app")
MLOPS = os.path.join(HERE, "mlops")
OUT = os.path.abspath(os.path.join(HERE, "..", "..", "..", "site", "public", "demo-data", "fraud.json"))

sys.path.insert(0, APP)
os.chdir(APP)  # core.py uses a relative artifact path
import core  # noqa: E402

# Business-meaningful drift signals (anonymized PCA V-features + engineered amount/time).
DRIFT_COLS = ["log_amount", "hour", "V14", "V10", "V4", "V12"]
PRETTY = {"log_amount": "Amount (log)", "hour": "Transaction hour",
          "V14": "Signal V14", "V10": "Signal V10", "V4": "Signal V4", "V12": "Signal V12"}


def _pretty(name: str) -> str:
    for p in ("num__", "cat__", "bin__", "log__", "remainder__"):
        name = name.replace(p, "")
    return name.replace("amount_bin_", "amount ").replace("_", " ").strip()


def downsample(xs, ys, n=80):
    xs, ys = np.asarray(xs), np.asarray(ys)
    idx = np.arange(len(xs)) if len(xs) <= n else np.unique(np.linspace(0, len(xs) - 1, n).astype(int))
    return [[round(float(xs[i]), 5), round(float(ys[i]), 5)] for i in idx]


def real_registry():
    try:
        sys.path.insert(0, MLOPS)
        import config as C          # noqa
        from steps import registry  # noqa
        vs = registry.list_versions()
        prod = registry.version_by_alias(C.ALIAS_PROD)
        return vs, (int(prod.version) if prod else None)
    except Exception as e:
        print("registry read failed:", e)
        return [], None


def build():
    art = core.load_artifact()
    model = art["model"]
    feat_names = list(art["feature_names"])
    Xeng = art["X_test_eng"]
    X_te_t = core.transform(art, Xeng)
    y_te = np.asarray(art["y_test"]).astype(int)
    thr = float(art["threshold"])

    # ---- performance @ default threshold + curves ----
    m = core.performance_metrics(model, X_te_t, y_te, thr)
    proba = model.predict_proba(X_te_t)[:, 1]
    cm = np.asarray(m["confusion"])
    fpr, tpr = m["roc"]
    rec, prec = m["pr"]

    # ---- threshold sweep (client drives a live slider) ----
    P = int((y_te == 1).sum()); N = int((y_te == 0).sum())
    sweep = []
    for t in np.round(np.arange(0.05, 0.96, 0.02), 2):
        pred = proba >= t
        tp = int(np.sum(pred & (y_te == 1))); fp = int(np.sum(pred & (y_te == 0)))
        fn = P - tp; tn = N - fp
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

    # ---- global importance ----
    gi = art.get("global_importance")
    if isinstance(gi, list):
        gi_rows = sorted(gi, key=lambda d: -d["importance"])[:15]
        global_importance = [{"feature": _pretty(d["feature"]), "importance": round(float(d["importance"]), 5)} for d in gi_rows]
    else:
        expl0 = core.build_explainer(model, art["background_t"])
        gdf = core.global_importance(core.shap_values_pos(expl0, X_te_t[:150]), feat_names)
        global_importance = [{"feature": _pretty(r["feature"]), "importance": round(float(r["importance"]), 5)}
                             for _, r in gdf.head(15).iterrows()]

    # ---- worked examples: pick 2 clearest frauds + 1 clear legit, real local SHAP ----
    expl = core.build_explainer(model, art["background_t"])
    fraud_idx = [i for i in np.argsort(-proba) if y_te[i] == 1][:2]
    legit_idx = [i for i in np.argsort(proba) if y_te[i] == 0][:1]
    examples = []
    for kind, i in [("Fraud", fraud_idx[0]), ("Fraud", fraud_idx[1] if len(fraud_idx) > 1 else fraud_idx[0]), ("Legit", legit_idx[0])]:
        row = Xeng.iloc[[i]]
        row_t = X_te_t[i:i + 1]
        p = float(proba[i])
        contrib = core.local_contributions(core.shap_values_pos(expl, row_t), feat_names).head(8)
        amt = float(row["Amount"].iloc[0]); hr = int(row["hour"].iloc[0])
        examples.append({
            "name": f"{kind} · ${amt:,.2f} · {hr:02d}:00", "amount": round(amt, 2), "hour": hr,
            "actual": int(y_te[i]), "probability": round(p, 5), "flag": bool(p >= thr),
            "local": [{"feature": _pretty(r["feature"]), "shap": round(float(r["shap"]), 5)} for _, r in contrib.iterrows()],
        })

    # ---- drift (REAL PSI: reference vs serving) ----
    drep = core.drift_report(art["X_ref_eng"], Xeng, [c for c in DRIFT_COLS if c in Xeng.columns])
    drift = [{"feature": PRETTY.get(r["feature"], r["feature"]), "PSI": float(r["PSI"]), "status": r["status"]}
             for _, r in drep.iterrows()]

    # ---- MLOps: real registry + real champion; illustrative challenger ----
    vs, prod_v = real_registry()
    registry_rows = [{"version": int(v["version"]), "alias": ", ".join(v.get("aliases", [])) or "registered",
                      "roc_auc": round(float(v.get("roc_auc") or 0), 4), "pr_auc": round(float(v.get("pr_auc") or 0), 4),
                      "model_name": v.get("model_name", "")} for v in vs]
    s = m["scores"]
    champ = {"version": prod_v, "roc_auc": round(float(s["ROC_AUC"]), 4), "pr_auc": round(float(s["PR_AUC"]), 4),
             "recall": round(float(s["Recall"]), 4), "precision": round(float(s["Precision"]), 4)}
    chal = {"version": (prod_v or 1) + 1,
            "roc_auc": round(min(1.0, champ["roc_auc"] + 0.004), 4),
            "pr_auc": round(min(1.0, champ["pr_auc"] + 0.021), 4),
            "recall": round(min(1.0, champ["recall"] + 0.03), 4),
            "precision": round(max(0.0, champ["precision"] - 0.01), 4)}
    gate_reasons = [
        f"PR-AUC (primary): challenger {chal['pr_auc']} vs champion {champ['pr_auc']} (need ≥ +0.0) → PASS",
        f"Recall guardrail: challenger {chal['recall']} vs champion {champ['recall']} (tolerance 0.02) → PASS",
    ]

    out = {
        "model_name": art.get("model_name", "Fraud model"),
        "trained_on": "284,807 card transactions (0.17% fraud)",
        "threshold_default": round(thr, 4),
        "prod_version": prod_v,
        "scores": {k: round(float(v), 4) for k, v in s.items()},
        "confusion": [[int(cm[0, 0]), int(cm[0, 1])], [int(cm[1, 0]), int(cm[1, 1])]],
        "baseline": round(float(m["baseline"]), 5),
        "n_test": int(len(y_te)),
        "roc": downsample(fpr, tpr, 80),
        "pr": downsample(rec, prec, 80),
        "sweep": sweep,
        "latency": {"p50": round(lat["p50"], 3), "p95": round(lat["p95"], 3), "p99": round(lat["p99"], 3),
                    "mean": round(lat["mean"], 3), "throughput_rps": round(lat["throughput_rps"], 1),
                    "hist": {"edges": [round(float(e), 4) for e in edges], "counts": [int(c) for c in counts]}},
        "resources": {"process_mem_mb": round(res["process_mem_mb"], 1), "system_mem_pct": round(res["system_mem_pct"], 1),
                      "cpu_pct": round(res["cpu_pct"], 1), "n_cores": int(res["n_cores"])},
        "global_importance": global_importance,
        "examples": examples,
        "drift": drift,
        "mlops": {"registry": registry_rows, "prod_version": prod_v,
                  "champion": champ, "challenger": chal, "illustrative": True,
                  "gate_passed": True, "gate_reasons": gate_reasons, "drift_monitor": drift},
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(out, f, separators=(",", ":"))
    print(f"wrote {OUT}  ({os.path.getsize(OUT)/1024:.1f} KB)  prod_v={prod_v} frauds={P}/{len(y_te)} examples={len(examples)}")


if __name__ == "__main__":
    build()
