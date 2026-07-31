"""Validator — deterministic anchors + confidence. Blocking issues route to human review."""
from __future__ import annotations

from src.agents import log
from src.codes import code_lookup
from src.config import MIN_CONFIDENCE

SECTIONS = ["subjective", "objective", "assessment", "plan"]
# Claims that name a condition absent from the source note (ungrounded) — blocking.
_UNGROUNDED = [("myocardial infarction", "myocardial"), ("prior heart attack", "heart attack"),
               ("history of stroke", "stroke")]


def run(state: dict) -> None:
    soap = state["soap"]
    codes = state["codes"]
    flags: list[str] = []
    blocking: list[str] = []

    # (1) code-existence guard against the real code sets — invented codes dropped (soft)
    valid = [c for c in codes if code_lookup.is_valid(c.code)]
    dropped = [c.code for c in codes if not code_lookup.is_valid(c.code)]
    if dropped:
        flags.append(f"Guard dropped invented code(s) not in the code set: {dropped}")
    state["codes"] = valid

    # (2) SOAP completeness — all four sections non-trivial (blocking)
    missing = [s for s in SECTIONS if len(getattr(soap, s, "")) < 8]
    if missing:
        blocking.append(f"SOAP incomplete — thin/empty section(s): {missing}")

    # (3) grounding — a claim naming a condition absent from the note is blocking
    src = state["encounter_text"].lower()
    ungrounded = [phrase for phrase, needle in _UNGROUNDED
                  if phrase in soap.assessment.lower() and needle not in src]
    if ungrounded:
        blocking.append(f"Ungrounded claim(s) not supported by the source note: {ungrounded}")

    confidence = round(max(0.0, 1.0 - 0.25 * len(blocking) - (0.1 if dropped else 0.0)), 2)
    state["flags"] = blocking + flags
    state["blocking"] = blocking
    state["confidence"] = confidence
    if blocking or confidence < MIN_CONFIDENCE:
        state["status"] = "human_review"
    log(state, "Validator", f"confidence={confidence}; blocking={blocking or 'none'}; "
                           f"dropped={dropped or 'none'}.")
