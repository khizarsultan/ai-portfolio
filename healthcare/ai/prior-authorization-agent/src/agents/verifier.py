"""Verifier — is coverage active and is the procedure a covered benefit?

Deterministic: calls the mock payer's eligibility service (that IS this agent's tool)."""
from __future__ import annotations
from src.state import PAState, log
from src.payer import mock_payer
from src.compliance import access


def run(state: PAState) -> PAState:
    access.enforce_tool("verifier", "payer.eligibility")
    case = state["case"]
    ok, reason = mock_payer.check_eligibility(case)
    state["coverage_ok"] = ok
    log(state, "Verifier", f"Eligibility check -> coverage_ok={ok}. {reason}")
    if not ok:
        state["status"] = "human_review"
    return state
