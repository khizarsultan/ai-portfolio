"""Audit trail -> human-readable rationale (plan §B3.4)."""
from __future__ import annotations


def explain(state: dict) -> str:
    case = state["case"]
    lines = [f"Documentation rationale for a {case.specialty.lower()} encounter:"]
    lines.append(f"- Drafted a SOAP note and extracted {len(state.get('codes') or [])} code(s), "
                 "then validated them against the real ICD-10/CPT code sets.")
    if state.get("flags"):
        lines.append("- Validation flags: " + "; ".join(state["flags"]) + ".")
    lines.append(f"- Validator confidence: {state.get('confidence')}.")
    if state.get("edit_count"):
        lines.append(f"- The draft was revised {state['edit_count']} time(s) on clinician feedback.")
    status = state.get("status")
    if status == "recorded":
        lines.append(f"- OUTCOME: {state.get('signer')} signed off; record {state.get('record_id')} written.")
    elif status == "human_review":
        lines.append("- OUTCOME: escalated to a human reviewer — nothing was written to the record.")
    return "\n".join(lines)
