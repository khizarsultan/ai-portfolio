"""Champion vs. challenger evaluation + promotion gate.

Scores the challenger (and current champion) on the frozen holdout set, then applies the
promotion policy from config. A challenger that passes is written to a pending-approval
record — it is NOT auto-promoted. A human approves it in the promote step.
"""
from __future__ import annotations
import os
import sys
import json
import datetime as dt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as C
from steps import ingest, modeling, registry

PENDING = os.path.join(C.STATE_DIR, "pending_approval.json")


def _gate(chal: dict, prod: dict | None) -> tuple[bool, list[str]]:
    if prod is None:
        return True, ["No champion in production yet — challenger will become the baseline."]
    reasons = []
    pm = C.PRIMARY_METRIC
    primary_ok = chal[pm] >= prod[pm] + C.MIN_IMPROVEMENT
    reasons.append(f"{pm}: challenger {chal[pm]:.4f} vs champion {prod[pm]:.4f} "
                   f"(need ≥ +{C.MIN_IMPROVEMENT}) → {'PASS' if primary_ok else 'FAIL'}")
    gm = C.GUARDRAIL_METRIC
    guard_ok = chal[gm] >= prod[gm] - C.GUARDRAIL_TOLERANCE
    reasons.append(f"{gm} guardrail: challenger {chal[gm]:.4f} vs champion {prod[gm]:.4f} "
                   f"(tolerance {C.GUARDRAIL_TOLERANCE}) → {'PASS' if guard_ok else 'FAIL'}")
    return (primary_ok and guard_ok), reasons


def evaluate_challenger() -> dict:
    chal = registry.load_artifact(C.ALIAS_CHALLENGER)
    if chal is None:
        raise RuntimeError("No challenger registered. Run `retrain` first.")
    prod = registry.load_artifact(C.ALIAS_PROD)

    holdout = ingest.get_holdout()
    chal_m = modeling.evaluate_artifact(chal, holdout)
    prod_m = modeling.evaluate_artifact(prod, holdout) if prod else None

    passed, reasons = _gate(chal_m, prod_m)
    record = {
        "created_at": dt.datetime.now().isoformat(timespec="seconds"),
        "challenger_version": chal["version"],
        "champion_version": prod["version"] if prod else None,
        "challenger_metrics": chal_m,
        "champion_metrics": prod_m,
        "primary_metric": C.PRIMARY_METRIC,
        "gate_passed": passed,
        "gate_reasons": reasons,
        "decision": "pending_approval" if passed else "rejected_by_gate",
    }
    with open(PENDING, "w") as f:
        json.dump(record, f, indent=2)
    return record


def load_pending() -> dict | None:
    if not os.path.exists(PENDING):
        return None
    with open(PENDING) as f:
        return json.load(f)
