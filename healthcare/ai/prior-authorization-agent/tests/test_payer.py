"""Mock payer + rules engine. Pure and deterministic — runs without an API key."""
from src.models import Packet, Order, PatientCase, Condition, Outcome
from src.payer import mock_payer, rules_engine


def _packet(cpt, dx, tx, just="Medically necessary."):
    return Packet(patient_id="P1", order=Order(cpt=cpt, display=""),
                  diagnosis_codes=dx, prior_treatments=tx, clinical_justification=just)


def test_requires_pa_and_coverage():
    assert rules_engine.requires_pa("PLAN_A", "73721") is True
    assert rules_engine.requires_pa("PLAN_A", "97110") is False   # PT never needs PA
    assert rules_engine.is_covered("PLAN_B", "70551") is False    # brain MRI not covered on HMO


def test_approved():
    d = mock_payer.decide(_packet("73721", ["M23.2"], ["conservative_treatment"]))
    assert d.outcome == Outcome.APPROVED


def test_needs_info_when_prior_treatment_missing():
    d = mock_payer.decide(_packet("73721", ["M23.2"], []))
    assert d.outcome == Outcome.NEEDS_INFO
    assert any("conservative_treatment" in m for m in d.missing)


def test_needs_info_when_justification_blank():
    d = mock_payer.decide(_packet("70551", ["G43.909"], [], just="  "))
    assert d.outcome == Outcome.NEEDS_INFO


def test_denied_when_diagnosis_unsupported():
    d = mock_payer.decide(_packet("73721", ["Z00.00"], ["conservative_treatment"]))
    assert d.outcome == Outcome.DENIED


def test_eligibility_paths():
    covered = PatientCase(patient_id="P1", age=50, sex="male", plan_id="PLAN_A",
                          order=Order(cpt="70551", display=""))
    ok, _ = mock_payer.check_eligibility(covered)
    assert ok is True
    not_cov = PatientCase(patient_id="P2", age=50, sex="male", plan_id="PLAN_B",
                          order=Order(cpt="70551", display=""))
    ok2, _ = mock_payer.check_eligibility(not_cov)
    assert ok2 is False
    inactive = PatientCase(patient_id="P3", age=50, sex="male", plan_id="PLAN_A",
                           coverage_active=False, order=Order(cpt="73721", display=""))
    ok3, _ = mock_payer.check_eligibility(inactive)
    assert ok3 is False
