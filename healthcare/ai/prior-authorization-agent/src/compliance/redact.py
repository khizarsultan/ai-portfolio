"""De-identification / data minimization (planv2 B2).

Strips the HIPAA Safe Harbor identifiers before anything is written to logs (or, if a hosted
model were ever used, sent off-machine). Synthetic data is treated as if it were real PHI."""
from __future__ import annotations
import json
import re

# The 18 HIPAA Safe Harbor identifier categories (§164.514(b)(2)).
SAFE_HARBOR_IDENTIFIERS = [
    "names", "geographic_subdivisions", "dates", "phone_numbers", "fax_numbers",
    "email_addresses", "social_security_numbers", "medical_record_numbers",
    "health_plan_beneficiary_numbers", "account_numbers", "certificate_license_numbers",
    "vehicle_identifiers", "device_identifiers", "urls", "ip_addresses",
    "biometric_identifiers", "full_face_photos", "other_unique_identifiers",
]

_PATTERNS = [
    (re.compile(r"\b\d{4}-\d{2}-\d{2}\b"), "[DATE]"),                     # ISO dates
    (re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b"), "[DATE]"),
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN]"),
    (re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"), "[PHONE]"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[EMAIL]"),
    (re.compile(r"https?://\S+"), "[URL]"),
    (re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b"), "[IP]"),
    (re.compile(r"\b\d{5}(?:-\d{4})?\b"), "[ZIP]"),
    (re.compile(r"\bMRN[:#]?\s*\w+\b", re.I), "[MRN]"),
]


def scrub_text(text: str) -> str:
    """Remove free-text identifiers (dates, SSNs, phones, emails, URLs, MRNs, ZIPs, IPs)."""
    if not text:
        return text
    for pat, repl in _PATTERNS:
        text = pat.sub(repl, text)
    return text


def _age_band(age: int) -> str:
    if age < 18:
        return "0-17"
    if age < 40:
        return "18-39"
    if age < 65:
        return "40-64"
    return "65+"


def redact_case(case) -> dict:
    """Return a de-identified view safe for logging: pseudonymous id, banded age, scrubbed text.
    Clinical codes are retained (not identifiers) — that is what the pipeline reasons over."""
    return {
        "subject": f"PT-{abs(hash(case.patient_id)) % 10000:04d}",   # pseudonym, not the id
        "age_band": _age_band(case.age),
        "sex": case.sex,
        "plan_id": case.plan_id,
        "order": {"cpt": case.order.cpt, "display": case.order.display},
        "diagnoses": [c.code for c in case.conditions],
        "prior_treatment_types": [t.type for t in case.prior_treatments],
        "notes": scrub_text(case.notes),
    }


def case_payload(case, remote: bool) -> str:
    """JSON the agents put in a prompt. Off-machine (remote) backends get the de-identified
    view; local backends get the full record (nothing leaves the machine)."""
    if remote:
        return json.dumps(redact_case(case), indent=2)
    return case.model_dump_json(indent=2)
