from src.agents import intake, soap_writer, coder, validator, recorder
from tests.conftest import fake_chat, make_case

CLEAN_SOAP = {
    "subjective": "Patient reports dysuria and urinary frequency.",
    "objective": "Urinalysis positive for nitrites.",
    "assessment": "Uncomplicated urinary tract infection.",
    "plan": "Nitrofurantoin, increase fluids.",
}


def _state(case=None):
    return {"case": case or make_case(), "audit_log": [], "status": "running",
            "signed_off": False, "flags": [], "blocking": [], "edit_feedback": None}


def test_intake_redacts_and_sets_text():
    st = _state(make_case(source_note="Call 415-555-1212 re: dysuria."))
    intake.run(st)
    assert "[PHONE]" in st["encounter_text"]


def test_validator_drops_invented_code_but_not_blocking():
    st = _state()
    intake.run(st)
    chat = fake_chat(CLEAN_SOAP, [{"system": "ICD-10", "code": "N39.0", "rationale": "UTI"},
                                  {"system": "ICD-10", "code": "M54.99", "rationale": "invented"}])
    soap_writer.run(st, chat)
    coder.run(st, chat)
    validator.run(st)
    assert [c.code for c in st["codes"]] == ["N39.0"]     # invented dropped
    assert st["status"] != "human_review"                 # drop alone is not blocking
    assert st["confidence"] < 1.0


def test_validator_blocks_ungrounded_claim():
    st = _state(make_case(source_note="Chest pain on exertion, ECG done."))
    intake.run(st)
    soap = dict(CLEAN_SOAP, assessment="Chest pain with history of myocardial infarction.")
    chat = fake_chat(soap, [{"system": "ICD-10", "code": "R07.9", "rationale": "chest pain"}])
    soap_writer.run(st, chat)
    coder.run(st, chat)
    validator.run(st)
    assert st["status"] == "human_review"
    assert any("Ungrounded" in f for f in st["flags"])


def test_recorder_requires_signoff():
    st = _state()
    intake.run(st)
    chat = fake_chat(CLEAN_SOAP, [{"system": "ICD-10", "code": "N39.0", "rationale": "UTI"}])
    soap_writer.run(st, chat); coder.run(st, chat); validator.run(st)
    recorder.run(st)                                  # no sign-off
    assert st.get("record_id") is None
    st["signed_off"] = True; st["signer"] = "Dr. Test"
    recorder.run(st)
    assert st["record_id"] and st["status"] == "recorded"
