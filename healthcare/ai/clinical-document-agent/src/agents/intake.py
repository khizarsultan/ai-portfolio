"""Intake — normalize raw visit input into clean, redacted encounter text."""
from __future__ import annotations

from src.agents import log
from src.compliance.redact import scrub


def run(state: dict) -> None:
    case = state["case"]
    state["encounter_text"] = scrub(case.source_note.strip())
    log(state, "Intake", "Encounter normalized and Safe-Harbor redacted "
                         "(purpose=clinical_documentation).")
