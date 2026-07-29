"""Compliance layer (planv2 B2): redaction, RBAC, consent, audit. Runs offline."""
import pytest

from src.models import PatientCase, Order, Condition
from src.compliance import redact, access, consent, audit


def _case(**kw):
    base = dict(patient_id="abc123", age=71, sex="female", plan_id="PLAN_A",
                conditions=[Condition(code="M23.2")], order=Order(cpt="73721", display="MRI knee"),
                purpose="prior_authorization",
                lawful_basis="Art.9(2)(h) provision of health care")
    base.update(kw)
    return PatientCase(**base)


def test_redact_scrubs_identifiers():
    s = redact.scrub_text("Seen 2025-11-01, SSN 123-45-6789, call 415-555-1212, a@b.com")
    assert "2025-11-01" not in s and "123-45-6789" not in s
    assert "[DATE]" in s and "[SSN]" in s and "[PHONE]" in s and "[EMAIL]" in s


def test_redact_case_deidentifies():
    r = redact.redact_case(_case())
    assert r["subject"].startswith("PT-") and "abc123" not in r["subject"]
    assert r["age_band"] == "65+"                       # exact age generalized
    assert r["diagnoses"] == ["M23.2"]                  # clinical codes retained


def test_remote_payload_is_redacted():
    case = _case(notes="Seen 2025-11-01, call 415-555-1212")
    remote = redact.case_payload(case, remote=True)      # sent to a hosted backend (NIM)
    assert "abc123" not in remote and "415-555-1212" not in remote and "2025-11-01" not in remote
    assert "M23.2" in remote                              # clinical codes retained
    local = redact.case_payload(case, remote=False)       # local backend gets full record
    assert "abc123" in local


def test_rbac_roles():
    assert access.can("clinician", "submit") is True
    assert access.can("clinician", "approve") is False
    assert access.can("reviewer", "view_full_packet") is True
    with pytest.raises(access.AccessDenied):
        access.enforce("clinician", "delete")


def test_agent_tool_policy():
    access.enforce_tool("submitter", "payer.decide")     # allowed
    with pytest.raises(access.AccessDenied):
        access.enforce_tool("appealer", "payer.decide")  # Appealer must not decide


def test_consent_required():
    ok, _ = consent.check_consent(_case())
    assert ok is True
    bad, reason = consent.check_consent(_case(purpose=None))
    assert bad is False and "purpose" in reason.lower()


def test_audit_is_append_only():
    trail = audit.AuditTrail()
    trail.record("Checker", "evaluated PA", "case:1", "needs_pa=True")
    entries = trail.entries()
    assert len(entries) == 1 and entries[0].actor == "Checker"
    # entries() returns a copy; mutating it can't change the trail
    with pytest.raises((AttributeError, TypeError)):
        entries[0].actor = "tampered"                    # frozen dataclass
