"""In-memory case store for the provider console (planv3 Part C).

Not a database — a demo store seeded from the labeled eval set. Holds each case, its
last run's state, a derived display status, and the reviewer-action history. A real
deployment would back this with an encrypted-at-rest DB; the shape is the same."""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import json

from src.models import PatientCase
from src.graph import run_case
from src.governance.explain import explain
from src import observability as obs

# Ordered pipeline for the UI stepper.
STEPS = ["Checker", "Verifier", "Assembler", "Submitter", "Appealer"]

_CASES: dict[str, dict] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _current_step(final: dict) -> str | None:
    """Last agent that acted, derived from the audit trail."""
    seen = None
    for entry in final.get("audit_log", []):
        for step in STEPS:
            if f"] {step}:" in entry:
                seen = step
    return seen


def _display_status(final: dict) -> str:
    """Map internal (status, decision) to the five console statuses."""
    status = final.get("status")
    decision = final.get("decision")
    outcome = decision.outcome.value if decision else None
    if status == "human_review":
        return "human_review"
    if status == "done":
        return "approved" if outcome == "APPROVED" else "denied"
    if final.get("needs_pa") is False:
        return "approved"          # auto-cleared, no PA needed
    return "in_progress"


def _summary(rec: dict) -> dict:
    """Row shape for the queue table."""
    c = rec["case"]
    return {
        "id": rec["id"],
        "patient_id": c.patient_id,
        "procedure": f"{c.order.cpt} — {c.order.display}",
        "plan_id": c.plan_id,
        "status": rec["status"],
        "current_step": rec["current_step"],
        "created_at": rec["created_at"],
        "updated_at": rec["updated_at"],
        "escalation_reason": rec.get("escalation_reason"),
    }


def _detail(rec: dict) -> dict:
    """Full shape for the case-detail screen."""
    c = rec["case"]
    return {
        **_summary(rec),
        "patient": {"age": c.age, "sex": c.sex, "coverage_active": c.coverage_active},
        "order": {"cpt": c.order.cpt, "display": c.order.display},
        "conditions": [{"code": x.code, "display": x.display} for x in c.conditions],
        "notes": c.notes,
        "steps": STEPS,
        "needs_pa": rec.get("needs_pa"),
        "coverage_ok": rec.get("coverage_ok"),
        "decision": rec.get("decision"),
        "reason": rec.get("reason"),
        "rationale": rec.get("rationale"),
        "audit_log": rec.get("audit_log", []),
        "actions": rec.get("actions", []),
        "trace_url": obs.trace_url(c.patient_id),   # planv4 D5: deep-link to Langfuse
    }


def _seed() -> None:
    """Load the labeled eval set as the initial queue (unrun -> needs_pa)."""
    path = Path(__file__).resolve().parent.parent / "eval" / "test_cases.json"
    if not path.exists():
        return
    for entry in json.loads(path.read_text()):
        case = PatientCase(**entry["case"])
        _CASES[entry["id"]] = {
            "id": entry["id"],
            "case": case,
            "status": "needs_pa",
            "current_step": None,
            "needs_pa": None, "coverage_ok": None,
            "decision": None, "reason": None, "rationale": None,
            "audit_log": [], "actions": [],
            "escalation_reason": None,
            "created_at": _now(), "updated_at": _now(),
        }


def list_cases(status: str | None = None, q: str | None = None) -> list[dict]:
    rows = [_summary(r) for r in _CASES.values()]
    if status:
        rows = [r for r in rows if r["status"] == status]
    if q:
        ql = q.lower()
        rows = [r for r in rows if ql in r["patient_id"].lower() or ql in r["procedure"].lower()]
    return sorted(rows, key=lambda r: r["updated_at"], reverse=True)


def get_case(case_id: str) -> dict | None:
    rec = _CASES.get(case_id)
    return _detail(rec) if rec else None


def run(case_id: str, actor_role: str = "clinician") -> dict | None:
    """Execute the agent flow and fold the result into the stored record."""
    rec = _CASES.get(case_id)
    if not rec:
        return None
    final = run_case(rec["case"], actor_role=actor_role)
    d = final.get("decision")
    rec.update({
        "needs_pa": final.get("needs_pa"),
        "coverage_ok": final.get("coverage_ok"),
        "decision": d.outcome.value if d else None,
        "reason": d.reason if d else None,
        "rationale": explain(final),
        "audit_log": final.get("audit_log", []),
        "current_step": _current_step(final),
        "status": _display_status(final),
        "escalation_reason": final.get("denial_reason") if final.get("status") == "human_review" else None,
        "updated_at": _now(),
    })
    return _detail(rec)


def _record_action(case_id: str, action: str, actor_role: str, detail: str) -> dict | None:
    rec = _CASES.get(case_id)
    if not rec:
        return None
    rec.setdefault("actions", []).append({
        "action": action, "actor_role": actor_role, "detail": detail, "at": _now(),
    })
    rec["updated_at"] = _now()
    return rec


def approve(case_id: str, actor_role: str) -> dict | None:
    rec = _record_action(case_id, "approve", actor_role, "reviewer approved")
    if not rec:
        return None
    rec["status"] = "approved"
    rec["escalation_reason"] = None
    return _detail(rec)


def send_back(case_id: str, actor_role: str, note: str) -> dict | None:
    rec = _record_action(case_id, "send_back", actor_role, note)
    if not rec:
        return None
    rec["status"] = "in_progress"
    return _detail(rec)


def escalate(case_id: str, actor_role: str, reason: str) -> dict | None:
    rec = _record_action(case_id, "escalate", actor_role, reason)
    if not rec:
        return None
    rec["status"] = "human_review"
    rec["escalation_reason"] = reason
    return _detail(rec)


_seed()
