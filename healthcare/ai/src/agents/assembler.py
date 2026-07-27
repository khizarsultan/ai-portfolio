"""Assembler — build a complete, truthful PA packet from the patient case.

The model selects the documented diagnoses / prior treatments and writes the justification;
it must not invent evidence. Emitted ICD-10 codes pass a hallucination guard (unknown codes
are dropped and flagged). Scoped identity: records.read only. Invalid model output escalates."""
from __future__ import annotations
from pydantic import BaseModel, Field

from src.state import PAState, log
from src.models import Packet
from src.llm.structured import extract, StructuredError
from src.llm.client import is_remote
from src.compliance import access, redact
from src.governance import guards


class AssemblerOut(BaseModel):
    diagnosis_codes: list[str] = Field(description="ICD-10 codes FROM THE CASE that justify the order.")
    prior_treatments: list[str] = Field(description="Prior-treatment types documented IN THE CASE (e.g. conservative_treatment).")
    clinical_justification: str = Field(description="2-4 sentence medical-necessity narrative grounded in the case.")
    attachments: list[str] = Field(description="Names of supporting documents to attach.")


_PROMPT = """You are a clinical documentation specialist assembling a prior-authorization packet.
Use ONLY facts present in the patient case below. Do NOT fabricate diagnoses or treatments.

Patient case (JSON):
{case_json}

Requested procedure: CPT {cpt} ({display})
{loop_note}

Build the packet: list the diagnosis codes and prior treatments that are actually documented
in the case and support this procedure, and write a concise clinical justification.

Example: if the case lists condition code M23.2 and a conservative_treatment, return
diagnosis_codes=["M23.2"], prior_treatments=["conservative_treatment"]."""


def run(state: PAState) -> PAState:
    access.enforce_tool("assembler", "records.read")
    case = state["case"]
    loop_note = ""
    if state.get("denial_reason"):
        loop_note = ("This is a re-submission. The previous packet was rejected because: "
                     f"\"{state['denial_reason']}\". Look through the case for that "
                     "missing/challenged evidence and include it if it exists.")

    try:
        out: AssemblerOut = extract(AssemblerOut, _PROMPT.format(
            case_json=redact.case_payload(case, is_remote()),
            cpt=case.order.cpt, display=case.order.display, loop_note=loop_note))
    except StructuredError as e:
        state["status"] = "human_review"
        log(state, "Assembler", f"Could not assemble a valid packet ({e}) -> human review.")
        return state

    # Hallucination guard: drop any ICD-10 code not in the known list, flag it.
    unknown = guards.check_codes(out.diagnosis_codes)
    dx = [c for c in out.diagnosis_codes if c not in unknown]
    if unknown:
        log(state, "Assembler",
            f"Hallucination guard: dropped unrecognised code(s) {unknown}.")

    packet = Packet(
        patient_id=case.patient_id,
        order=case.order,
        diagnosis_codes=dx,
        prior_treatments=out.prior_treatments,
        clinical_justification=out.clinical_justification,
        attachments=out.attachments,
        appeal_letter=state["packet"].appeal_letter if state.get("packet") else None,
    )
    state["packet"] = packet
    log(state, "Assembler",
        f"Built packet: dx={packet.diagnosis_codes}, prior_tx={packet.prior_treatments}, "
        f"{len(packet.attachments)} attachment(s).")
    return state
