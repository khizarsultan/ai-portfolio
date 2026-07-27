"""GDPR purpose limitation, retention, and right to erasure (planv2 B2)."""
from __future__ import annotations
import json
from pathlib import Path

from src.config import PROCESSED, RETENTION_DAYS

# Recognised processing purposes and Art. 6/9 lawful bases (illustrative).
PURPOSES = {"treatment", "prior_authorization", "care_coordination"}
LAWFUL_BASES = {
    "Art.9(2)(h) provision of health care",
    "Art.6(1)(b) contract",
    "Art.6(1)(c) legal obligation",
    "consent",
}


def check_consent(case) -> tuple[bool, str]:
    """Refuse processing unless a valid purpose AND lawful basis are tagged."""
    if not case.purpose or not case.lawful_basis:
        return False, "Missing GDPR purpose or lawful basis — processing refused (purpose limitation)."
    if case.purpose not in PURPOSES:
        return False, f"Unrecognised purpose '{case.purpose}'."
    if case.lawful_basis not in LAWFUL_BASES:
        return False, f"Unrecognised lawful basis '{case.lawful_basis}'."
    return True, f"Purpose '{case.purpose}' under {case.lawful_basis}."


def delete_case(case_id: str) -> bool:
    """Right to erasure: remove a processed case file. Returns True if a file was deleted."""
    path = PROCESSED / f"case_{case_id}.json"
    if path.exists():
        path.unlink()
        return True
    # also allow deletion by patient_id match
    for p in PROCESSED.glob("*.json"):
        try:
            if json.loads(p.read_text()).get("patient_id") == case_id:
                p.unlink()
                return True
        except Exception:
            continue
    return False


RETENTION_POLICY = (
    f"Processed cases are retained for {RETENTION_DAYS} days, then purged. Subjects may "
    "request erasure at any time (delete_case / DELETE /case/{id}).")
