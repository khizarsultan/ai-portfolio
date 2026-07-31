"""Build EncounterCase json from a source dataset.

Fallback now (public/synthetic notes), MIMIC when credentialing is granted — the output shape
is identical, so switching to MIMIC is a data swap, not a code change (plan §6).
"""
from __future__ import annotations

import json

from src.config import DATA
from src.models import EncounterCase


def load_fallback() -> list[EncounterCase]:
    with open(DATA / "fallback" / "notes.json") as f:
        return [EncounterCase(**row) for row in json.load(f)]


def main() -> None:
    out_dir = DATA / "processed"
    out_dir.mkdir(parents=True, exist_ok=True)
    cases = load_fallback()
    for case in cases:
        (out_dir / f"{case.encounter_id}.json").write_text(case.model_dump_json(indent=2))
    print(f"Wrote {len(cases)} EncounterCase file(s) to {out_dir}")


if __name__ == "__main__":
    main()
