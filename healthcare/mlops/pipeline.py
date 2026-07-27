#!/usr/bin/env python3
"""Healthcare MLOps pipeline CLI.

Stages (each is independently runnable, or chained via `run`):

    bootstrap                 register the current app model as the production champion
    make-window [--n --drift] draw a new "production" data window into the feature store
    check-drift               PSI + Evidently drift: latest window vs training reference
    retrain                   train a challenger on reference + latest window, register it
    evaluate                  score challenger vs champion on holdout, apply the gate
    promote --approve --by X  human sign-off -> move production alias + roll out to serving
    status                    show registry, aliases, pending approval, serving artifact
    run [--drift --n]         drift-triggered flow: window -> drift -> (retrain -> evaluate)

Experiment tracking & registry UI:  mlflow ui --backend-store-uri sqlite:///mlflow.db
"""
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


def _p(title):
    print("\n" + "=" * 66 + f"\n{title}\n" + "=" * 66)


def cmd_bootstrap(args):
    _p("BOOTSTRAP — establish the production champion (trained on the reference split)")
    if registry.version_by_alias(C.ALIAS_PROD) and not args.force:
        print("A production champion already exists. Use --force to re-bootstrap.")
        return
    art = modeling.train_model(ingest.get_reference(), random_state=C.RANDOM_STATE)
    metrics = modeling.evaluate_artifact(art, ingest.get_holdout())
    v = registry.register_existing_artifact(art, metrics, note="bootstrap")
    promote.export_serving(v)   # champion becomes the live serving artifact
    print(f"Registered v{v} as '{C.ALIAS_PROD}' and rolled out to serving.  "
          f"holdout ROC-AUC={metrics['roc_auc']:.4f} PR-AUC={metrics['pr_auc']:.4f}")


def cmd_make_window(args):
    _p(f"MAKE-WINDOW — n={args.n} drift={args.drift}")
    vdir = ingest.make_window(n=args.n, drift=args.drift)
    print("feature-store snapshot:", vdir)


def cmd_check_drift(args):
    _p("CHECK-DRIFT — latest window vs training reference")
    win = ingest.latest_snapshot("window")
    if win is None:
        print("No window found. Run `make-window` first."); return None
    res = drift.run_drift_check(ingest.get_reference(), ingest.load_snapshot(win), tag="check")
    for c in res["columns"]:
        print(f"  {c['feature']:22} PSI={c['PSI']:.4f}  {c['status']}")
    print(f"\nshare drifted = {res['share_of_drifted_columns']}  (threshold {res['threshold']})")
    print("DRIFT DETECTED — retraining recommended." if res["drifted"] else "No significant drift.")
    if res["evidently_html"]:
        print("Evidently report:", res["evidently_html"])
    return res


def cmd_retrain(args):
    _p("RETRAIN — train challenger on reference + latest window")
    win = ingest.latest_snapshot("window")
    if win is None:
        print("No window found. Run `make-window` first."); return
    import pandas as pd
    ref = ingest.get_reference()
    window = ingest.load_snapshot(win)
    train_df = pd.concat([ref, window], ignore_index=True)
    art = modeling.train_model(train_df, random_state=C.RANDOM_STATE)
    metrics = modeling.evaluate_artifact(art, ingest.get_holdout())
    meta = json.load(open(os.path.join(win, "meta.json")))
    v = registry.log_and_register(art, metrics,
                                  params={"n_train": len(train_df), "window": meta["version"]},
                                  dataset_meta=meta, run_name="retrain", alias=C.ALIAS_CHALLENGER)
    print(f"Registered challenger v{v}.  holdout ROC-AUC={metrics['roc_auc']:.4f} "
          f"PR-AUC={metrics['pr_auc']:.4f} recall={metrics['recall']:.3f}")


def cmd_evaluate(args):
    _p("EVALUATE — challenger vs champion on holdout")
    rec = evaluate.evaluate_challenger()
    cm, pm = rec["challenger_metrics"], rec["champion_metrics"]
    print(f"challenger v{rec['challenger_version']}: ROC-AUC={cm['roc_auc']:.4f} PR-AUC={cm['pr_auc']:.4f}")
    if pm:
        print(f"champion   v{rec['champion_version']}: ROC-AUC={pm['roc_auc']:.4f} PR-AUC={pm['pr_auc']:.4f}")
    for r in rec["gate_reasons"]:
        print("  •", r)
    print("\nGATE:", "PASSED → pending manual approval" if rec["gate_passed"] else "FAILED → rejected")


def cmd_promote(args):
    _p("PROMOTE — manual approval gate")
    if not args.approve and not args.reject:
        print("Specify --approve or --reject."); return
    entry = promote.promote(approve=args.approve, approver=args.by, reason=args.reason)
    print(json.dumps(entry, indent=2))
    if entry["action"] == "promoted_to_production":
        print(f"\n✅ v{entry['challenger_version']} is now PRODUCTION and live at {entry['serving_artifact']}")


def cmd_status(args):
    _p("STATUS — model registry")
    versions = registry.list_versions()
    if not versions:
        print("No registered versions yet. Run `bootstrap`.")
    for v in versions:
        al = (" [" + ", ".join(v["aliases"]) + "]") if v["aliases"] else ""
        print(f"  v{v['version']:<3}{al:<26} ROC-AUC={v['roc_auc'] or '—':<10} "
              f"PR-AUC={v['pr_auc'] or '—':<10} dataset={v['dataset'] or '—'}")
    pend = evaluate.load_pending()
    if pend:
        print(f"\nPENDING APPROVAL: challenger v{pend['challenger_version']} "
              f"(gate {'passed' if pend['gate_passed'] else 'failed'}) — awaiting sign-off.")
    print(f"\nServing artifact: {C.SERVING_ARTIFACT} "
          f"({'present' if os.path.exists(C.SERVING_ARTIFACT) else 'MISSING'})")


def cmd_run(args):
    _p(f"RUN — drift-triggered flow (drift={args.drift}, n={args.n})")
    ingest.make_window(n=args.n, drift=args.drift)
    res = cmd_check_drift(args)
    if res and res["drifted"]:
        print("\n→ Drift detected: triggering retrain + evaluate.")
        cmd_retrain(args)
        cmd_evaluate(args)
        print("\nNext: review in `mlflow ui`, then "
              "`python pipeline.py promote --approve --by <you> --reason '...'`")
    else:
        print("\n→ No drift: skipping retraining.")


def main():
    ap = argparse.ArgumentParser(description="Healthcare MLOps pipeline")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("bootstrap").add_argument("--force", action="store_true")
    mw = sub.add_parser("make-window"); mw.add_argument("--n", type=int, default=8000); mw.add_argument("--drift", action="store_true")
    sub.add_parser("check-drift")
    sub.add_parser("retrain")
    sub.add_parser("evaluate")
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
