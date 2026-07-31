"""Shared graph state (plan §7)."""
from __future__ import annotations

from typing import TypedDict

from src.models import Code, EncounterCase, SOAPNote


class EncounterState(TypedDict, total=False):
    case: EncounterCase
    encounter_text: str | None      # cleaned, redacted input
    soap: SOAPNote | None
    codes: list[Code] | None
    flags: list[str]                # validation issues shown to the reviewer
    blocking: list[str]             # subset that routes to human review
    confidence: float | None
    signed_off: bool
    signer: str | None
    edit_feedback: str | None
    edit_count: int
    audit_log: list[str]
    status: str                     # running | await_signoff | recorded | human_review
    record_id: str | None
