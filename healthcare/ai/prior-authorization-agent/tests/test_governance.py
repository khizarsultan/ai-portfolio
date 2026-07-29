"""Governance layer (planv2 B3): contracts, identity scopes, guards, explain. Runs offline."""
import pytest

from src.models import PatientCase, Order, Condition, Decision, Outcome
from src.governance import contracts, identity, guards
from src.governance.explain import explain


def _state(**kw):
    case = PatientCase(patient_id="p1", age=50, sex="male", plan_id="PLAN_A",
                       order=Order(cpt="73721", display="MRI knee"),
                       purpose="prior_authorization",
                       lawful_basis="Art.9(2)(h) provision of health care")
    s = {"case": case, "audit_log": [], "attempt": 0}
    s.update(kw)
    return s


def test_handoff_contract_validates_and_is_idempotent():
    s = _state(needs_pa=True, status="running")
    c1 = contracts.validate_handoff(s)
    c2 = contracts.validate_handoff(s)
    assert c1.version == contracts.CONTRACT_VERSION
    assert c1.model_dump() == c2.model_dump()            # idempotent


def test_agent_least_privilege():
    assert identity.can_use_tool("appealer", "records.read") is True
    assert identity.can_use_tool("appealer", "payer.decide") is False
    assert identity.can_read_field("checker", "notes") is False   # checker can't read notes
    assert identity.can_read_field("assembler", "notes") is True


def test_hallucination_guard():
    assert guards.is_valid_icd10("M23.2") is True
    assert guards.is_valid_icd10("X99.9") is False
    assert guards.is_valid_cpt("73721") is True
    assert guards.check_codes(["M23.2", "FAKE1", "G47.33"]) == ["FAKE1"]


def test_explain_produces_rationale():
    s = _state(needs_pa=True, coverage_ok=True,
               decision=Decision(outcome=Outcome.APPROVED, reason="criteria met"),
               status="done", audit_log=["[01] Checker: needs_pa=True"])
    text = explain(s)
    assert "APPROVED" in text and "criteria met" in text and "audit trail" in text.lower()


def test_explain_auto_clear():
    s = _state(needs_pa=False, status="done")
    assert "auto-cleared" in explain(s)
