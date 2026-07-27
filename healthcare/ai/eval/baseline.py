"""Single-prompt baseline: one Claude call classifies the case, no agents, no tools.

This is the comparison point — it has to reason about PA rules, coverage, medical necessity
and documentation all at once, which is where a single prompt tends to fumble the
multi-step (needs-info / deny-then-appeal) cases."""
from __future__ import annotations
from pydantic import BaseModel, Field

from src.llm.structured import extract, StructuredError
from src.llm.client import is_remote
from src.compliance import redact
from src.payer import rules_engine

LABELS = ["AUTO_CLEAR", "NOT_COVERED", "APPROVED", "NEEDS_INFO", "DENIED"]


class BaselineOut(BaseModel):
    label: str = Field(description=f"Exactly one of: {LABELS}")


_PROMPT = """You are a prior-authorization adjudicator. Given a patient case and the payer
rules, output the single correct final outcome label.

Payer rules:
- PA required per plan: {pa_required}
- Covered procedures per plan: {covered}
- Medical necessity per CPT: {necessity}

Labels:
- AUTO_CLEAR: the procedure does not require PA under the plan.
- NOT_COVERED: PA is required but the procedure is not a covered benefit, or coverage is inactive.
- APPROVED: PA required, covered, and medical necessity (diagnosis + required documentation) is met.
- NEEDS_INFO: necessity is plausible but required documentation is missing.
- DENIED: the diagnosis does not establish medical necessity.

Patient case (JSON):
{case_json}

Return exactly one label."""


def classify(case) -> str:
    pa, nec, plans = rules_engine._load()
    covered = {k: v.get("covered_cpt") for k, v in plans.items()}
    try:
        out: BaselineOut = extract(BaselineOut, _PROMPT.format(
            pa_required=pa, covered=covered,
            necessity={k: {"dx": v["required_diagnoses"],
                           "docs": v.get("required_prior_treatments") or []} for k, v in nec.items()},
            case_json=redact.case_payload(case, is_remote())))
    except StructuredError:
        return "DENIED"
    return out.label if out.label in LABELS else "DENIED"
