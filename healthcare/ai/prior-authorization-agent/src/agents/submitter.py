"""Submitter — send the packet to the mock payer and record the decision.

Deterministic: the payer's adjudication service is this agent's tool. This node also owns
the loop counters (needs-info / appeal) and trips the human-review status when a cap is hit,
because only node return values persist to graph state — routing functions can't."""
from __future__ import annotations
from src.state import PAState, log
from src.models import Outcome
from src.payer import mock_payer
from src.compliance import access
from src.config import MAX_NEEDS_INFO_LOOPS, MAX_APPEAL_LOOPS


def run(state: PAState) -> PAState:
    access.enforce_tool("submitter", "payer.decide")
    packet = state["packet"]
    decision = mock_payer.decide(packet)
    state["decision"] = decision
    outcome = decision.outcome

    if outcome == Outcome.APPROVED:
        state["denial_reason"] = None
        state["status"] = "done"
        log(state, "Submitter", f"Payer decision: APPROVED. {decision.reason}")
        return state

    state["denial_reason"] = decision.reason
    if outcome == Outcome.NEEDS_INFO:
        state["needs_info_loops"] = state.get("needs_info_loops", 0) + 1
        capped = state["needs_info_loops"] > MAX_NEEDS_INFO_LOOPS
    else:  # DENIED
        state["appeal_loops"] = state.get("appeal_loops", 0) + 1
        capped = state["appeal_loops"] > MAX_APPEAL_LOOPS

    log(state, "Submitter", f"Payer decision: {outcome.value}. {decision.reason}")
    if capped:
        state["status"] = "human_review"
        log(state, "Orchestrator",
            f"{outcome.value} loop cap reached -> routing to human review.")
    return state
