"""SOAP Writer — draft the 4-section note, grounded in the encounter text."""
from __future__ import annotations

from typing import Callable

from src.agents import log
from src.llm.structured import extract
from src.models import SOAPNote

SYS = ("You are a clinical scribe. From the encounter note, write a SOAP note. Use ONLY facts "
       "present in the note — do NOT invent findings, history, or diagnoses. Respond ONLY with a "
       "JSON object.")
SECTIONS = ["subjective", "objective", "assessment", "plan"]


def run(state: dict, chat: Callable[[str, str], str]) -> None:
    fb = state.get("edit_feedback")
    loop = f'\nClinician feedback on the previous draft: "{fb}". Apply it.' if fb else ""
    user = (f"Encounter note:\n{state['encounter_text']}{loop}\n\n"
            'Return JSON: {"subjective":"","objective":"","assessment":"","plan":""} — each a '
            "concise paragraph grounded in the note.")
    out = extract(chat, SYS, user, SECTIONS)
    state["soap"] = SOAPNote(**{k: str(out.get(k, "")).strip() for k in SECTIONS})
    log(state, "SOAP Writer", "Drafted SOAP note" + (" (revised)" if fb else "") + ".")
