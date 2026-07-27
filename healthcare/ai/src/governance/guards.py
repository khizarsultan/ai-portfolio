"""Trust & safety guards (planv2 B3.2).

Hallucination guard: any ICD-10 / CPT code an agent emits must exist in a known code list;
unknown codes are flagged so the caller can drop them and escalate. The allow-list here is a
curated demo set (the payer policy codes plus common companions) — in production this would be
the licensed ICD-10-CM / CPT tables. Format is also sanity-checked as a second line."""
from __future__ import annotations
import re
import yaml

from src.config import RULES_DIR

_ICD10_RE = re.compile(r"^[A-TV-Z]\d[0-9A-Z](?:\.[0-9A-Z]{1,4})?$")
_CPT_RE = re.compile(r"^\d{4}[\dA-Z]$")

# Common valid companions that appear in cases but aren't payer-policy codes.
_EXTRA_ICD10 = {"Z00.00", "E66.9", "I10", "R19.00"}


def _load_known() -> tuple[set[str], set[str]]:
    with open(RULES_DIR / "medical_necessity.yaml") as f:
        nec = yaml.safe_load(f) or {}
    icd10, cpt = set(_EXTRA_ICD10), set()
    for code, crit in nec.items():
        cpt.add(str(code))
        icd10.update(crit.get("required_diagnoses") or [])
    return icd10, cpt


KNOWN_ICD10, KNOWN_CPT = _load_known()


def has_icd10_format(code: str) -> bool:
    return bool(_ICD10_RE.match(code))


def is_valid_icd10(code: str) -> bool:
    return code in KNOWN_ICD10


def is_valid_cpt(code: str) -> bool:
    return code in KNOWN_CPT


def check_codes(codes: list[str]) -> list[str]:
    """Return the subset of ICD-10-style codes that are NOT recognised (possible hallucinations)."""
    return [c for c in codes if c not in KNOWN_ICD10]
