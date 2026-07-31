"""Evaluate the agent system vs the single-prompt baseline (plan §10).

Metrics: SOAP completeness, coding precision/recall/F1 vs reference codes, code-existence
(hallucinated-code) rate. Needs a live LLM key; prints a hint if none is set.
"""
from __future__ import annotations

import json

from eval import baseline
from src.config import ROOT
from src.graph import run
from src.llm.client import LLMError, get_llm
from src.models import EncounterCase


def _prf(pred: list[str], ref: list[str]) -> tuple[float, float, float]:
    p, r = set(pred), set(ref)
    if not p and not r:
        return 1.0, 1.0, 1.0
    tp = len(p & r)
    prec = tp / len(p) if p else 0.0
    rec = tp / len(r) if r else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    return round(prec, 3), round(rec, 3), round(f1, 3)


def _complete(soap: dict) -> bool:
    return all(len(soap.get(s, "")) >= 8 for s in ("subjective", "objective", "assessment", "plan"))


def main() -> None:
    cases = [EncounterCase(**c) for c in json.loads((ROOT / "eval" / "test_cases.json").read_text())]
    try:
        chat = get_llm()
    except LLMError as e:
        print(f"No LLM configured ({e}). Set NVIDIA_API_KEY or use LLM_PROVIDER=ollama.")
        return

    def signoff_fn(_s: dict) -> dict:
        return {"action": "sign", "signer": "Dr. Eval (clinician)"}

    agg = {"agent_f1": [], "base_f1": [], "agent_complete": 0, "base_complete": 0,
           "agent_invalid": 0, "base_invalid": 0}
    for case in cases:
        ref = case.reference_codes
        st = run(case, chat, signoff_fn)
        a_codes = [c.code for c in st["codes"]]
        _, _, af1 = _prf(a_codes, ref)
        agg["agent_f1"].append(af1)
        agg["agent_complete"] += int(_complete(st["soap"].sections()))
        agg["agent_invalid"] += len(st.get("flags", []))  # guard-dropped invented codes surface here

        b = baseline.run(chat, case.source_note)
        _, _, bf1 = _prf(b["codes"], ref)
        agg["base_f1"].append(bf1)
        agg["base_complete"] += int(_complete(b["soap"]))
        agg["base_invalid"] += len(b["invalid_codes"])
        print(f"{case.encounter_id}: agent F1={af1}  baseline F1={bf1}  status={st['status']}")

    n = len(cases)
    mean = lambda xs: round(sum(xs) / len(xs), 3) if xs else 0.0
    print("\n=== summary ===")
    print(f"coding F1        agent={mean(agg['agent_f1'])}   baseline={mean(agg['base_f1'])}")
    print(f"SOAP complete    agent={agg['agent_complete']}/{n}   baseline={agg['base_complete']}/{n}")
    print(f"invalid codes    agent(guarded)={agg['agent_invalid']}   baseline(unguarded)={agg['base_invalid']}")
    print("Note: the agent system also adds a mandatory sign-off gate the baseline cannot provide.")


if __name__ == "__main__":
    main()
