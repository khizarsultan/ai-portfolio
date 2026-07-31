"""Coder — extract ICD-10 + CPT codes from the SOAP note, each with a rationale."""
from __future__ import annotations

from typing import Callable

from src.agents import log
from src.codes import code_lookup
from src.llm.structured import extract
from src.models import Code

SYS = ("You are a medical coder. From the SOAP note, extract ICD-10 diagnosis codes and CPT "
       "procedure/E&M codes, each with a one-line rationale. Use ONLY codes justified by the "
       "note. Respond ONLY with a JSON object.")


def run(state: dict, chat: Callable[[str, str], str]) -> None:
    soap = state["soap"]
    fb = state.get("edit_feedback")
    user = (f"SOAP note (JSON):\n{soap.model_dump_json(indent=2)}\n"
            + (f'\nClinician feedback: "{fb}". Apply it.\n' if fb else "")
            + '\nReturn JSON: {"codes":[{"system":"ICD-10"|"CPT","code":"","rationale":""}]}')
    out = extract(chat, SYS, user, ["codes"])
    codes: list[Code] = []
    for c in out.get("codes") or []:
        if not isinstance(c, dict):
            continue
        code = str(c.get("code", "")).strip().upper()
        if not code:
            continue
        system = code_lookup.system_of(code)
        if system == "?":
            system = str(c.get("system", "?")).strip() or "?"
        codes.append(Code(system=system, code=code, rationale=str(c.get("rationale", "")).strip()))
    state["codes"] = codes
    log(state, "Coder", f"Extracted {len(codes)} code(s): {[c.code for c in codes]}"
                       + (" (revised)" if fb else "") + ".")
