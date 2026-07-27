"""Manual-approval promotion gate + serving rollout (rebuilds the full dashboard bundle)."""
from __future__ import annotations
import os
import sys
import json
import datetime as dt
import joblib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as C
from steps import bundle, ingest, registry, evaluate

APPROVALS = os.path.join(C.STATE_DIR, "approvals.jsonl")


def export_serving(version: str) -> str:
    """Rebuild the full dashboard artifact from a registered version and roll it out."""
    core_art = registry.load_artifact(version)
    b = bundle.build(core_art, ingest.get_reference(), ingest.get_holdout())
    joblib.dump(b, C.SERVING_ARTIFACT, compress=3)
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
