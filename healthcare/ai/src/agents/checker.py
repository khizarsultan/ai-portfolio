"""Checker — does this order need prior authorization?

Ground truth is the payer's pa_required.yaml. The model reasons over the plan + order and
justifies its call; we cross-check against the rule table and trust the table on disagreement.
Scoped identity: may only use rules.pa_lookup and read plan_id/order (no clinical notes)."""
from __future__ import annotations
from pydantic import BaseModel, Field

from src.state import PAState, log
from src.payer import rules_engine
from src.llm.structured import extract, StructuredError
from src.compliance import access


class CheckerOut(BaseModel):
    needs_pa: bool = Field(description="True if this order requires prior authorization.")
    rationale: str = Field(description="One sentence explaining the decision.")


_PROMPT = """You are a prior-authorization intake specialist for a US health plan.

Plan: {plan_id}
Ordered procedure: CPT {cpt} ({display})
Procedures that require prior authorization under this plan: {pa_list}

Decide whether this specific order requires prior authorization. Answer strictly from the
plan's PA list above.

Example: if the ordered CPT is in the list -> needs_pa=true; if it is not -> needs_pa=false."""


def run(state: PAState) -> PAState:
    access.enforce_tool("checker", "rules.pa_lookup")
    case = state["case"]
    cpt = case.order.cpt
    pa_list = rules_engine._load()[0].get(case.plan_id) or []
    table_says = rules_engine.requires_pa(case.plan_id, cpt)

    try:
        out: CheckerOut = extract(CheckerOut, _PROMPT.format(
            plan_id=case.plan_id, cpt=cpt, display=case.order.display,
            pa_list=", ".join(pa_list) or "(none)"))
        rationale = out.rationale
        if out.needs_pa != table_says:
            log(state, "Checker",
                f"model said needs_pa={out.needs_pa} but rule table says {table_says}; "
                f"deferring to rule table.")
    except StructuredError as e:
        rationale = f"(model output invalid: {e}; used rule table.)"

    state["needs_pa"] = table_says  # rule table is authoritative
    log(state, "Checker", f"CPT {cpt} under {case.plan_id} -> needs_pa={table_says}. {rationale}")
    if not table_says:
        state["status"] = "done"
    return state
