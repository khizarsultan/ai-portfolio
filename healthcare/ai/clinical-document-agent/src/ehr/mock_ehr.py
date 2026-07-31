"""In-memory mock EHR. Stores FHIR-shaped records — write only after sign-off."""
from __future__ import annotations

from src.models import Code, Record

_STORE: dict[str, Record] = {}


def write_record(subject: str, section: dict[str, str], codes: list[Code], attester: str) -> Record:
    rid = f"REC-{abs(hash(subject + attester)) % 100000:05d}"
    rec = Record(record_id=rid, subject=subject, section=section, codes=codes, attester=attester)
    _STORE[rid] = rec
    return rec


def read_record(rid: str) -> Record | None:
    return _STORE.get(rid)


def delete_record(rid: str) -> bool:      # GDPR erasure (plan §B2)
    return _STORE.pop(rid, None) is not None
