"""Offline fake LLM so the pipeline and agents test without a network / key."""
from __future__ import annotations

import json
from typing import Callable

from src.models import EncounterCase


def fake_chat(soap: dict, codes: list[dict]) -> Callable[[str, str], str]:
    """Return a chat(system, user) that answers SOAP-writer and Coder prompts from fixtures."""
    def chat(system: str, user: str) -> str:
        if "medical coder" in system:
            return json.dumps({"codes": codes})
        return json.dumps(soap)          # clinical scribe (SOAP writer)
    return chat


def make_case(**kw) -> EncounterCase:
    base = dict(encounter_id="t1", age=40, sex="female", specialty="Family medicine",
                source_note="Patient with dysuria and urinary frequency; urinalysis positive.",
                reference_codes=["N39.0"])
    base.update(kw)
    return EncounterCase(**base)
