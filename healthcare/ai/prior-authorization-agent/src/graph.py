r"""LangGraph wiring. Nodes = agents; edges branch on results. Mirrors plan §3 + planv2 B3.

    intake (consent gate) -> Checker --no PA--> done (auto-clear)
                    \--PA--> Verifier --not covered--> human review
                                   \--covered--> Assembler -> Submitter --APPROVED--> done
                                                                        --NEEDS_INFO--> Assembler [<=2]
                                                                        --DENIED-----> Appealer -> Submitter [<=2]

Every handoff is validated against the versioned HandoffContext contract (interoperability +
idempotency); a contract violation escalates to human review rather than propagating bad state.
"""
from __future__ import annotations
from langgraph.graph import StateGraph, START, END

from src.state import PAState, log
from src.models import Outcome
from src.agents import checker, verifier, assembler, submitter, appealer
from src.compliance import access, consent
from src.governance import contracts
from src import observability as obs


def _wrap(name, fn):
    """Count the step, run the agent, then validate the handoff against the contract."""
    def node(state: PAState) -> PAState:
        state["attempt"] = state.get("attempt", 0) + 1
        state = fn(state)
        try:
            contracts.validate_handoff(state)                 # B3.1 interoperability guarantee
        except Exception as e:
            state["status"] = "human_review"
            log(state, "Orchestrator", f"Handoff from {name} failed contract validation ({e}).")
        return state
    return node


# ---- nodes ---------------------------------------------------------------
def intake(state: PAState) -> PAState:
    ok, reason = consent.check_consent(state["case"])          # B2 GDPR purpose limitation
    log(state, "Intake", reason)
    if not ok:
        state["status"] = "human_review"
    return state


# ---- conditional edges ---------------------------------------------------
def after_intake(state: PAState) -> str:
    return END if state.get("status") == "human_review" else "checker"


def after_checker(state: PAState) -> str:
    if state.get("status") == "human_review":
        return END
    return "verifier" if state.get("needs_pa") else END


def after_verifier(state: PAState) -> str:
    return "assembler" if state.get("coverage_ok") else END


def after_assembler(state: PAState) -> str:
    return END if state.get("status") == "human_review" else "submitter"


def after_submitter(state: PAState) -> str:
    outcome = state["decision"].outcome
    if outcome == Outcome.APPROVED or state.get("status") == "human_review":
        return END
    return "assembler" if outcome == Outcome.NEEDS_INFO else "appealer"


def after_appealer(state: PAState) -> str:
    return END if state.get("status") == "human_review" else "submitter"


def build_graph():
    g = StateGraph(PAState)
    g.add_node("intake", intake)
    g.add_node("checker", _wrap("checker", checker.run))
    g.add_node("verifier", _wrap("verifier", verifier.run))
    g.add_node("assembler", _wrap("assembler", assembler.run))
    g.add_node("submitter", _wrap("submitter", submitter.run))
    g.add_node("appealer", _wrap("appealer", appealer.run))

    g.add_edge(START, "intake")
    g.add_conditional_edges("intake", after_intake, {"checker": "checker", END: END})
    g.add_conditional_edges("checker", after_checker, {"verifier": "verifier", END: END})
    g.add_conditional_edges("verifier", after_verifier, {"assembler": "assembler", END: END})
    g.add_conditional_edges("assembler", after_assembler, {"submitter": "submitter", END: END})
    g.add_conditional_edges("submitter", after_submitter,
                            {"assembler": "assembler", "appealer": "appealer", END: END})
    g.add_conditional_edges("appealer", after_appealer, {"submitter": "submitter", END: END})
    return g.compile()


def initial_state(case, actor_role: str = "clinician") -> PAState:
    return {"case": case, "actor_role": actor_role, "attempt": 0,
            "needs_info_loops": 0, "appeal_loops": 0, "audit_log": [], "status": "running"}


def run_case(case, actor_role: str = "clinician", expected_label: str | None = None) -> PAState:
    access.enforce(actor_role, "submit")                        # B2 RBAC: who may submit
    graph = build_graph()
    with obs.trace_case(case, actor_role) as tracer:            # planv4 D: one trace per case
        final = graph.invoke(initial_state(case, actor_role),
                             config=tracer.config(recursion_limit=50))
        if final.get("status") == "running":
            final["status"] = "done"
        tracer.finish(final, expected_label)
    return final
