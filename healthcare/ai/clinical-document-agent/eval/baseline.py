"""Single-prompt baseline: note in -> SOAP + codes out, no validation, no sign-off gate."""
from __future__ import annotations

from typing import Callable

from src.codes import code_lookup
from src.llm.structured import extract

SYS = ("You are a clinical assistant. From the encounter note, produce a SOAP note and the "
       "ICD-10/CPT codes in one shot. Respond ONLY with a JSON object.")


def run(chat: Callable[[str, str], str], note: str) -> dict:
    user = (f"Encounter note:\n{note}\n\n"
            'Return JSON: {"subjective":"","objective":"","assessment":"","plan":"",'
            '"codes":["ICD-10 or CPT codes"]}')
    out = extract(chat, SYS, user, ["subjective", "codes"])
    codes = [str(c).strip().upper() for c in (out.get("codes") or []) if str(c).strip()]
    soap = {k: str(out.get(k, "")).strip() for k in ("subjective", "objective", "assessment", "plan")}
    return {"soap": soap, "codes": codes,
            "invalid_codes": [c for c in codes if not code_lookup.is_valid(c)]}
