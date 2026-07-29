"""Manual-approval promotion gate + serving rollout.

A challenger that passed the automated gate still needs a human sign-off. On approval we
move the `production` alias, drop `challenger`, stamp an audit trail on the model version,
and export the dashboard-native artifact to the serving path — i.e. the new model goes live.
"""
from __future__ import annotations
import os
import sys
import json
import datetime as dt
import joblib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as C
from steps import registry, evaluate

APPROVALS = os.path.join(C.STATE_DIR, "approvals.jsonl")
DASHBOARD_KEYS = ("model", "preprocessor", "threshold", "feature_names", "model_name")


def export_serving(version: str) -> str:
    """Materialize a registered version to the exact artifact the dashboard loads."""
    art = registry.load_artifact(version)
    slim = {k: art[k] for k in DASHBOARD_KEYS}
    joblib.dump(slim, C.SERVING_ARTIFACT, compress=3)
    return C.SERVING_ARTIFACT


def _append(entry: dict):
    with open(APPROVALS, "a") as f:
        f.write(json.dumps(entry) + "\n")


def promote(approve: bool, approver: str, reason: str) -> dict:
    rec = evaluate.load_pending()
    if rec is None:
        raise RuntimeError("No pending evaluation. Run `evaluate` first.")
    if not rec["gate_passed"]:
        raise RuntimeError("Challenger failed the automated gate — it cannot be promoted.")

    v = rec["challenger_version"]
    entry = {"timestamp": dt.datetime.now().isoformat(timespec="seconds"),
             "challenger_version": v, "previous_champion": rec["champion_version"],
             "approver": approver, "reason": reason}

    if not approve:
        entry["action"] = "rejected_by_human"
        _append(entry)
        os.remove(evaluate.PENDING)
        return entry

    cl = registry.client()
    registry.set_alias(C.ALIAS_PROD, v)
    registry.delete_alias(C.ALIAS_CHALLENGER)
    cl.set_model_version_tag(C.REGISTERED_MODEL, v, "approved_by", approver)
    cl.set_model_version_tag(C.REGISTERED_MODEL, v, "approved_at", entry["timestamp"])
    cl.set_model_version_tag(C.REGISTERED_MODEL, v, "approval_reason", reason)
    path = export_serving(v)

    entry["action"] = "promoted_to_production"
    entry["serving_artifact"] = path
    _append(entry)
    os.remove(evaluate.PENDING)
    return entry
