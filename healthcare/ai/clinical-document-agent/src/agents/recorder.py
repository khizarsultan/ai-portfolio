"""Recorder — write the FHIR-shaped record, ONLY when signed_off is true (core safety gate)."""
from __future__ import annotations

from src.agents import log
from src.compliance.redact import age_band
from src.ehr import mock_ehr


def run(state: dict) -> None:
    if not state.get("signed_off"):
        log(state, "Recorder", "Blocked: no clinician sign-off — nothing written to the record.")
        return
    case = state["case"]
    subject = f"ENC-{abs(hash(case.encounter_id)) % 10000:04d} ({age_band(case.age)}, {case.sex})"
    rec = mock_ehr.write_record(subject, state["soap"].sections(), state["codes"], state["signer"])
    state["record_id"] = rec.record_id
    state["status"] = "recorded"
    log(state, "Recorder", f"Signed by {state['signer']}. Wrote record {rec.record_id} to the mock EHR.")
