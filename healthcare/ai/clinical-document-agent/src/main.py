"""Run one encounter through the pipeline (plan §12).

    python -m src.data_prep.extract_cases
    python -m src.main --case data/processed/enc_001.json --signoff sign
"""
from __future__ import annotations

import argparse
import json

from src.graph import run
from src.llm.client import get_llm
from src.models import EncounterCase


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True, help="path to an EncounterCase json")
    ap.add_argument("--signoff", choices=["sign", "reject", "edit"], default="sign",
                    help="what the clinician does at the mandatory gate")
    ap.add_argument("--feedback", default="Downcode to a low-complexity visit.",
                    help="edit feedback (only used with --signoff edit)")
    args = ap.parse_args()

    case = EncounterCase(**json.loads(open(args.case).read()))
    chat = get_llm()

    def signoff_fn(_state: dict) -> dict:
        return {"action": args.signoff, "signer": "Dr. Demo (clinician)",
                "feedback": args.feedback, "reason": "clinician requests further review"}

    state = run(case, chat, signoff_fn)

    print(f"\n=== {case.encounter_id} · {case.specialty} ===")
    soap = state["soap"]
    for name in ("subjective", "objective", "assessment", "plan"):
        print(f"\n[{name.upper()}]\n{getattr(soap, name)}")
    print("\n[CODES]")
    for c in state["codes"]:
        print(f"  {c.code:8} ({c.system})  {c.rationale}")
    print(f"\n[STATUS] {state['status']}   confidence={state.get('confidence')}   "
          f"record={state.get('record_id')}")
    print("\n[RATIONALE]\n" + state["rationale"])


if __name__ == "__main__":
    main()
