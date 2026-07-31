"""Orchestrator: linear-with-gate pipeline (plan §3).

  intake -> SOAP Writer -> Coder -> Validator
       -> blocking flags / low confidence -> human_review
       -> otherwise -> await sign-off (HUMAN-IN-THE-LOOP, required)
              signed          -> Recorder -> recorded
              edited          -> back to SOAP Writer/Coder (loop, max 2) then human_review
              rejected        -> human_review

The sign-off is a real human gate. It is injected as `signoff_fn(state) -> {"action","signer",...}`
so the CLI, tests, and a future console/API can all supply the clinician's decision. Nothing
reaches the Recorder before `signed_off` is true. Mirrors a LangGraph StateGraph with a
conditional edge on the validator and an interrupt at the sign-off node.
"""
from __future__ import annotations

from typing import Callable

from src.agents import intake, soap_writer, coder, validator, recorder, log
from src.config import MAX_EDIT_LOOPS
from src.governance.explain import explain
from src.models import EncounterCase

Chat = Callable[[str, str], str]
SignoffFn = Callable[[dict], dict]


def _signoff_gate(state: dict, decision: dict) -> None:
    state["signer"] = decision.get("signer", "clinician")
    action = decision.get("action", "sign")
    if action == "sign":
        state["signed_off"] = True
        log(state, "Sign-off", f"{state['signer']} reviewed and signed the note.")
    elif action == "reject":
        state["status"] = "human_review"
        log(state, "Sign-off", f"{state['signer']} rejected: {decision.get('reason', '')}")
    elif action == "edit":
        state["edit_feedback"] = decision.get("feedback", "")
        log(state, "Sign-off", f"{state['signer']} edited the draft: {decision.get('feedback', '')}")


def run(case: EncounterCase, chat: Chat, signoff_fn: SignoffFn) -> dict:
    state: dict = {"case": case, "audit_log": [], "status": "running", "signed_off": False,
                   "edit_count": 0, "edit_feedback": None, "flags": [], "blocking": []}
    intake.run(state)

    loops = 0
    while True:
        soap_writer.run(state, chat)
        coder.run(state, chat)
        validator.run(state)
        state["edit_feedback"] = None
        if state["status"] == "human_review":
            break

        decision = signoff_fn(state)              # human-in-the-loop (interrupt)
        _signoff_gate(state, decision)
        if state["status"] == "human_review":     # rejected
            break
        if state.get("signed_off"):
            recorder.run(state)
            break

        loops += 1                                # edit -> regenerate
        state["edit_count"] = loops
        if loops > MAX_EDIT_LOOPS:
            state["status"] = "human_review"
            log(state, "Orchestrator", "Edit loop cap reached -> human review.")
            break

    if state["status"] == "running":
        state["status"] = "human_review"
    state["rationale"] = explain(state)
    return state
