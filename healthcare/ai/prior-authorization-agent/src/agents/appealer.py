"""Appealer — on a denial, find supporting evidence in the case, draft an appeal, and revise
the packet. May only use facts present in the case, so an unsupportable denial stays denied.

Scoped identity: records.read only — the Appealer CANNOT call the payer's decision path.
Emitted codes pass the hallucination guard. Invalid model output escalates to human review."""
from __future__ import annotations
from pydantic import BaseModel, Field

from src.state import PAState, log
from src.llm.structured import extract, StructuredError
from src.llm.client import is_remote
from src.compliance import access, redact
from src.governance import guards


class AppealerOut(BaseModel):
    appeal_letter: str = Field(description="Formal appeal letter addressing the denial reason.")
    added_diagnosis_codes: list[str] = Field(description="Additional ICD-10 codes from the case that rebut the denial.")
    added_prior_treatments: list[str] = Field(description="Additional documented prior treatments from the case.")
    updated_justification: str = Field(description="Strengthened clinical justification grounded in the case.")


_PROMPT = """You are a physician-advisor drafting an appeal of a denied prior authorization.
Use ONLY facts present in the patient case. If the case genuinely lacks the required
evidence, write an honest letter and add nothing you cannot support.

Patient case (JSON):
{case_json}

Denied packet diagnosis codes: {dx}
Denied packet prior treatments: {tx}
Payer denial reason: "{denial_reason}"

Find any evidence in the case that rebuts the denial, draft the appeal, and list any
additional diagnosis codes / prior treatments the payer overlooked."""


def run(state: PAState) -> PAState:
    access.enforce_tool("appealer", "records.read")
    case = state["case"]
    packet = state["packet"]
    try:
        out: AppealerOut = extract(AppealerOut, _PROMPT.format(
            case_json=redact.case_payload(case, is_remote()),
            dx=packet.diagnosis_codes, tx=packet.prior_treatments,
            denial_reason=state.get("denial_reason") or ""))
    except StructuredError as e:
        state["status"] = "human_review"
        log(state, "Appealer", f"Could not draft a valid appeal ({e}) -> human review.")
        return state

    unknown = guards.check_codes(out.added_diagnosis_codes)
    added_dx = [c for c in out.added_diagnosis_codes if c not in unknown]
    if unknown:
        log(state, "Appealer", f"Hallucination guard: dropped unrecognised code(s) {unknown}.")

    packet.diagnosis_codes = sorted(set(packet.diagnosis_codes) | set(added_dx))
    packet.prior_treatments = sorted(set(packet.prior_treatments) | set(out.added_prior_treatments))
    if out.updated_justification.strip():
        packet.clinical_justification = out.updated_justification
    packet.appeal_letter = out.appeal_letter
    state["packet"] = packet
    log(state, "Appealer",
        f"Drafted appeal; added dx={added_dx}, prior_tx={out.added_prior_treatments}.")
    return state
