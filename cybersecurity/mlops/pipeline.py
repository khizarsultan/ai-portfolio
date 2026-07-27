#!/usr/bin/env python3
"""URL-threat MLOps pipeline CLI (multi-class). Stages: bootstrap, make-window,
check-drift, retrain, evaluate, promote, status, run."""
from __future__ import annotations
import os
import sys
import json
import argparse
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C
from steps import ingest, modeling, registry, drift, evaluate, promote

PM, GM = C.PRIMARY_METRIC, C.GUARDRAIL_METRIC


def _p(t):
    print("\n" + "=" * 60 + f"\n{t}\n" + "=" * 60)


def cmd_bootstrap(args):
    _p("BOOTSTRAP — champion trained on the reference split")
    if registry.version_by_alias(C.ALIAS_PROD) and not args.force:
        print("Champion already exists. Use --force."); return
    art = modeling.train_model(ingest.get_reference(), random_state=C.RANDOM_STATE)
    metrics = modeling.evaluate_artifact(art, ingest.get_holdout())
    v = registry.register_existing_artifact(art, metrics, note="bootstrap")
    promote.export_serving(v)
    print(f"Registered v{v} as '{C.ALIAS_PROD}'.  {PM}={metrics[PM]:.4f} {GM}={metrics[GM]:.4f}")


def cmd_make_window(args):
    _p(f"MAKE-WINDOW — n={args.n} drift={args.drift}")
    print("snapshot:", ingest.make_window(n=args.n, drift=args.drift))


def cmd_check_drift(args):
    _p("CHECK-DRIFT — latest window vs reference")
    win = ingest.latest_snapshot("window")
    if not win:
        print("No window. Run make-window."); return None
    res = drift.run_drift_check(ingest.get_reference(), ingest.load_snapshot(win), tag="check")
    for c in res["columns"]:
        print(f"  {c['feature']:14} PSI={c['PSI']:.4f}  {c['status']}")
    print("DRIFT DETECTED." if res["drifted"] else "No significant drift.")
    return res


def cmd_retrain(args):
    _p("RETRAIN — challenger on reference + latest window")
    import pandas as pd
    win = ingest.latest_snapshot("window")
    if not win:
        print("No window."); return
    df = pd.concat([ingest.get_reference(), ingest.load_snapshot(win)], ignore_index=True)
    art = modeling.train_model(df, random_state=C.RANDOM_STATE)
    metrics = modeling.evaluate_artifact(art, ingest.get_holdout())
    meta = json.load(open(os.path.join(win, "meta.json")))
    v = registry.log_and_register(art, metrics, params={"window": meta["version"]},
                                  dataset_meta=meta, run_name="retrain", alias=C.ALIAS_CHALLENGER)
    print(f"Challenger v{v}.  {PM}={metrics[PM]:.4f} {GM}={metrics[GM]:.4f}")


def cmd_evaluate(args):
    _p("EVALUATE — challenger vs champion")
    rec = evaluate.evaluate_challenger()
    cm, pm = rec["challenger_metrics"], rec["champion_metrics"]
    print(f"challenger v{rec['challenger_version']}: {PM}={cm[PM]:.4f} {GM}={cm[GM]:.4f}")
    if pm:
        print(f"champion   v{rec['champion_version']}: {PM}={pm[PM]:.4f} {GM}={pm[GM]:.4f}")
    for r in rec["gate_reasons"]:
        print(" •", r)
    print("GATE:", "PASSED → pending approval" if rec["gate_passed"] else "FAILED")


def cmd_promote(args):
    _p("PROMOTE — manual approval")
    if not args.approve and not args.reject:
        print("Use --approve or --reject."); return
    print(json.dumps(promote.promote(args.approve, args.by, args.reason), indent=2))


def cmd_status(args):
    _p("STATUS")
    for v in registry.list_versions():
        al = (" [" + ", ".join(v["aliases"]) + "]") if v["aliases"] else ""
        print(f"  v{v['version']:<3}{al:<26} {PM}={v['roc_auc'] or '—'} {GM}={v['pr_auc'] or '—'}")
    pend = evaluate.load_pending()
    if pend:
        print(f"PENDING: challenger v{pend['challenger_version']} ({'passed' if pend['gate_passed'] else 'failed'})")
    print("Serving:", "present" if os.path.exists(C.SERVING_ARTIFACT) else "MISSING")


def cmd_run(args):
    _p(f"RUN — drift-triggered (drift={args.drift})")
    ingest.make_window(n=args.n, drift=args.drift)
    res = cmd_check_drift(args)
    if res and res["drifted"]:
        cmd_retrain(args); cmd_evaluate(args)
    else:
        print("No drift → skip retraining.")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("bootstrap").add_argument("--force", action="store_true")
    mw = sub.add_parser("make-window"); mw.add_argument("--n", type=int, default=8000); mw.add_argument("--drift", action="store_true")
    sub.add_parser("check-drift"); sub.add_parser("retrain"); sub.add_parser("evaluate")
    pr = sub.add_parser("promote")
    pr.add_argument("--approve", action="store_true"); pr.add_argument("--reject", action="store_true")
    pr.add_argument("--by", default="unknown"); pr.add_argument("--reason", default="")
    sub.add_parser("status")
    rn = sub.add_parser("run"); rn.add_argument("--n", type=int, default=8000); rn.add_argument("--drift", action="store_true")
    args = ap.parse_args()
    {"bootstrap": cmd_bootstrap, "make-window": cmd_make_window, "check-drift": cmd_check_drift,
     "retrain": cmd_retrain, "evaluate": cmd_evaluate, "promote": cmd_promote,
     "status": cmd_status, "run": cmd_run}[args.cmd](args)


if __name__ == "__main__":
    main()
