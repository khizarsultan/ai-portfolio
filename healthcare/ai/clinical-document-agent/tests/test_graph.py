from src.graph import run
from tests.conftest import fake_chat, make_case

CLEAN_SOAP = {
    "subjective": "Patient reports dysuria and urinary frequency.",
    "objective": "Urinalysis positive for nitrites.",
    "assessment": "Uncomplicated urinary tract infection.",
    "plan": "Nitrofurantoin, increase fluids.",
}
CODES = [{"system": "ICD-10", "code": "N39.0", "rationale": "UTI"},
         {"system": "CPT", "code": "99213", "rationale": "office visit"}]


def _sign(_s):
    return {"action": "sign", "signer": "Dr. Test"}


def test_clean_case_signed_and_recorded():
    st = run(make_case(), fake_chat(CLEAN_SOAP, CODES), _sign)
    assert st["status"] == "recorded"
    assert st["record_id"]


def test_reject_routes_to_human_review():
    st = run(make_case(), fake_chat(CLEAN_SOAP, CODES),
             lambda _s: {"action": "reject", "signer": "Dr. Test", "reason": "needs imaging"})
    assert st["status"] == "human_review"
    assert st.get("record_id") is None


def test_edit_then_sign_records_after_one_loop():
    seen = {"n": 0}

    def signoff(_s):                        # edit once, then sign
        seen["n"] += 1
        return {"action": "edit", "feedback": "downcode", "signer": "Dr. Test"} if seen["n"] == 1 \
            else {"action": "sign", "signer": "Dr. Test"}

    st = run(make_case(), fake_chat(CLEAN_SOAP, CODES), signoff)
    assert st["status"] == "recorded"
    assert st["edit_count"] == 1


def test_nothing_recorded_without_signoff_reaching_recorder():
    # ungrounded claim -> validator blocks before the gate; recorder never runs
    soap = dict(CLEAN_SOAP, assessment="UTI with history of stroke.")
    st = run(make_case(source_note="Dysuria, no neuro history."),
             fake_chat(soap, CODES), _sign)
    assert st["status"] == "human_review"
    assert st.get("record_id") is None
