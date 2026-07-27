"""Graph wiring. Structure compiles without an API key; full flow needs one."""
import os
import pytest

from src.models import PatientCase, Order, Condition, PriorTreatment
from src.graph import build_graph, run_case

needs_llm = pytest.mark.skipif(os.getenv("RUN_LLM_TESTS") != "1",
                               reason="set RUN_LLM_TESTS=1 (needs Ollama serving) to run")

CONSENT = dict(purpose="prior_authorization",
               lawful_basis="Art.9(2)(h) provision of health care")


def test_graph_compiles():
    assert build_graph() is not None


@needs_llm
def test_auto_clear_flow():
    case = PatientCase(patient_id="P1", age=40, sex="male", plan_id="PLAN_A",
                       conditions=[Condition(code="M54.5")],
                       order=Order(cpt="97110", display="PT"), **CONSENT)
    final = run_case(case)
    assert final["needs_pa"] is False
    assert final["status"] == "done"


@needs_llm
def test_approved_flow():
    case = PatientCase(patient_id="P2", age=55, sex="female", plan_id="PLAN_A",
                       conditions=[Condition(code="M23.2", display="Meniscus tear")],
                       prior_treatments=[PriorTreatment(type="conservative_treatment")],
                       order=Order(cpt="73721", display="MRI knee"), **CONSENT)
    final = run_case(case)
    assert final["decision"].outcome.value == "APPROVED"
    assert final["audit_log"]
