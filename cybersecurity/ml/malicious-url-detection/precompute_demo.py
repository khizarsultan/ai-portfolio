"""Offline precompute for the Malicious-URL v2 site dashboards (4-class).

Everything the dashboards render is computed here, offline, from the self-contained
artifact (which bundles X_test/y_test/X_ref/background/global_importance/latency) plus
the real MLflow registry. The Vercel site ships only numbers — no shap/plotly/mlflow.

MLOps note: registry + drift are REAL; there is no committed challenger/approval
state and the raw CSV is gone, so the champion-vs-challenger + approval cycle is
emitted as a clearly-flagged illustrative scenario (illustrative=True).

Run:  python precompute_demo.py
Writes: ../../site/public/demo-data/malicious-url.json
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
OUT = os.path.abspath(os.path.join(HERE, "..", "..", "..", "site", "public", "demo-data", "malicious-url.json"))

sys.path.insert(0, APP)
os.chdir(APP)
import core  # noqa: E402

DRIFT_COLS = ["url_len", "n_digits", "digit_ratio", "url_entropy", "n_slash", "host_len"]
PRETTY = {"url_len": "URL length", "n_digits": "Digits", "digit_ratio": "Digit ratio",
          "url_entropy": "Char entropy", "n_slash": "Slashes", "host_len": "Host length"}


def _pretty(name: str) -> str:
    for p in ("log__", "num__", "cat__", "bin__"):
        name = name.replace(p, "")
    return name.replace("_", " ").strip()


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
    classes = [str(c) for c in art["classes"]]
    feat_names = list(art["feature_names"])
    X_test_t = core.transform(art, art["X_test_eng"])
    y_test = np.asarray(art["y_test"]).astype(str)

    m = core.performance_metrics(model, X_test_t, y_test, classes)
    pc = m["per_class"]
    per_class = [{"cls": c, "precision": round(float(pc.loc[c, "precision"]), 4),
                  "recall": round(float(pc.loc[c, "recall"]), 4),
                  "f1": round(float(pc.loc[c, "f1"]), 4), "support": int(pc.loc[c, "support"])}
                 for c in classes]
    cnorm = np.asarray(m["confusion"])
    ccount = np.asarray(m["confusion_counts"])

    # ---- latency + resources ----
    lat = art.get("latency") or core.benchmark_latency(model, X_test_t, n=200)
    lm = np.asarray(lat["latencies_ms"])
    counts, edges = np.histogram(lm, bins=30)
    res = core.resource_usage()

    # ---- global importance ----
    gi = art.get("global_importance")
    if isinstance(gi, list):
        gi_rows = sorted(gi, key=lambda d: -d["importance"])[:15]
        global_importance = [{"feature": _pretty(d["feature"]), "importance": round(float(d["importance"]), 5)} for d in gi_rows]
    else:
        gi = core.global_importance_mc(core.build_explainer(model, art["background_t"]), X_test_t[:80], feat_names)
        global_importance = [{"feature": _pretty(r["feature"]), "importance": round(float(r["importance"]), 5)}
                             for _, r in gi.head(15).iterrows()]

    # ---- worked examples: real local SHAP toward predicted class ----
    expl = core.build_explainer(model, art["background_t"])
    ex = art.get("examples", {})
    examples = []
    for c in classes:
        urls = ex.get(c) or ex.get(str(c))
        if not urls:
            continue
        url = urls[0]
        row_eng = core.featurize_url(art, url)
        row_t = art["preprocessor"].transform(row_eng)
        proba = model.predict_proba(row_t)[0]
        idx = int(np.argmax(proba))
        pred = classes[idx]
        contrib = core.local_contributions(core.shap_values_class(expl, row_t, idx), feat_names).head(8)
        examples.append({
            "name": f"{c} example", "url": url, "predicted": pred,
            "proba": {cl: round(float(p), 4) for cl, p in zip(classes, proba)},
            "local": [{"feature": _pretty(r["feature"]), "shap": round(float(r["shap"]), 5)} for _, r in contrib.iterrows()],
        })

    # ---- drift (REAL PSI: reference vs serving) ----
    drep = core.drift_report(art["X_ref_eng"], art["X_test_eng"], DRIFT_COLS)
    drift = [{"feature": PRETTY.get(r["feature"], r["feature"]), "PSI": float(r["PSI"]), "status": r["status"]}
             for _, r in drep.iterrows()]

    # ---- MLOps: real registry + real champion metrics; illustrative challenger ----
    vs, prod_v = real_registry()
    registry_rows = [{"version": int(v["version"]), "alias": ", ".join(v.get("aliases", [])) or "registered",
                      "roc_auc": round(float(v.get("roc_auc") or 0), 4), "pr_auc": round(float(v.get("pr_auc") or 0), 4),
                      "model_name": v.get("model_name", "")} for v in vs]
    champ = {"version": prod_v, "macro_f1": round(float(m["macro_f1"]), 4),
             "macro_recall": round(float(m["macro_recall"]), 4),
             "macro_roc_auc": round(float(m["macro_roc_auc"]), 4), "accuracy": round(float(m["accuracy"]), 4)}
    # illustrative challenger: small, plausible deltas (NOT a real trained model)
    chal = {"version": (prod_v or 1) + 1,
            "macro_f1": round(champ["macro_f1"] + 0.011, 4),
            "macro_recall": round(min(1.0, champ["macro_recall"] + 0.018), 4),
            "macro_roc_auc": round(min(1.0, champ["macro_roc_auc"] + 0.006), 4),
            "accuracy": round(min(1.0, champ["accuracy"] + 0.004), 4)}
    gate_reasons = [
        f"macro_f1: challenger {chal['macro_f1']} vs champion {champ['macro_f1']} (need ≥ +0.0) → PASS",
        f"macro_recall guardrail: challenger {chal['macro_recall']} vs champion {champ['macro_recall']} (tolerance 0.02) → PASS",
    ]

    out = {
        "model_name": art.get("model_name", "URL threat model"),
        "classes": classes, "n_test": int(len(y_test)),
        "metrics": {"accuracy": round(float(m["accuracy"]), 4), "macro_f1": round(float(m["macro_f1"]), 4),
                    "macro_recall": round(float(m["macro_recall"]), 4), "macro_roc_auc": round(float(m["macro_roc_auc"]), 4)},
        "per_class": per_class,
        "confusion_norm": [[round(float(x), 4) for x in row] for row in cnorm],
        "confusion_counts": [[int(x) for x in row] for row in ccount],
        "global_importance": global_importance,
        "examples": examples,
        "latency": {"p50": round(lat["p50"], 3), "p95": round(lat["p95"], 3), "p99": round(lat["p99"], 3),
                    "mean": round(lat["mean"], 3), "throughput_rps": round(lat["throughput_rps"], 1),
                    "hist": {"edges": [round(float(e), 4) for e in edges], "counts": [int(c) for c in counts]}},
        "resources": {"process_mem_mb": round(res["process_mem_mb"], 1), "system_mem_pct": round(res["system_mem_pct"], 1),
                      "cpu_pct": round(res["cpu_pct"], 1), "n_cores": int(res["n_cores"])},
        "drift": drift,
        "prod_version": prod_v,
        "mlops": {"registry": registry_rows, "prod_version": prod_v,
                  "champion": champ, "challenger": chal, "illustrative": True,
                  "gate_passed": True, "gate_reasons": gate_reasons,
                  "drift_monitor": drift},
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(out, f, separators=(",", ":"))
    print(f"wrote {OUT}  ({os.path.getsize(OUT)/1024:.1f} KB)  classes={classes} prod_v={prod_v} examples={len(examples)}")


if __name__ == "__main__":
    build()
