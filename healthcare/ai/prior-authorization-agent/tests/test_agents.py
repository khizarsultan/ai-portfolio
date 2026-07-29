"""Per-agent isolation tests. Deterministic agents run without a key; LLM agents need one."""
import os
import pytest

from src.models import PatientCase, Order, Condition, Packet, Outcome
from src.state import log
from src.agents import verifier, submitter

needs_llm = pytest.mark.skipif(os.getenv("RUN_LLM_TESTS") != "1",
                               reason="set RUN_LLM_TESTS=1 (needs Ollama serving) to run")


def _state(case, **kw):
    s = {"case": case, "audit_log": [], "attempt": 0}
    s.update(kw)
    return s


def test_verifier_flags_non_covered():
    case = PatientCase(patient_id="P1", age=50, sex="male", plan_id="PLAN_B",
                       order=Order(cpt="70551", display="MRI brain"))
    s = verifier.run(_state(case))
    assert s["coverage_ok"] is False
    assert s["status"] == "human_review"


def test_submitter_records_decision():
    case = PatientCase(patient_id="P2", age=50, sex="male", plan_id="PLAN_A",
                       order=Order(cpt="73721", display="MRI knee"))
    packet = Packet(patient_id="P2", order=case.order,
                    diagnosis_codes=["M23.2"], prior_treatments=["conservative_treatment"],
                    clinical_justification="Necessary.")
    s = submitter.run(_state(case, packet=packet))
    assert s["decision"].outcome == Outcome.APPROVED
    assert s["status"] == "done"


@needs_llm
def test_assembler_builds_packet():
    from src.agents import assembler
    case = PatientCase(patient_id="P3", age=55, sex="female", plan_id="PLAN_A",
                       conditions=[Condition(code="M23.2", display="Meniscus tear")],
                       order=Order(cpt="73721", display="MRI knee"))
    s = assembler.run(_state(case))
    assert s["packet"] is not None
    assert s["packet"].diagnosis_codes
