"""Loads and evaluates the YAML payer rules. Pure, deterministic — no LLM, no I/O beyond
reading the rule files once. This is what makes denials/appeals meaningful and testable."""
from __future__ import annotations
from functools import lru_cache
import yaml

from src.config import RULES_DIR
from src.models import Packet, Decision, Outcome


@lru_cache(maxsize=1)
def _load() -> tuple[dict, dict, dict]:
    with open(RULES_DIR / "pa_required.yaml") as f:
        pa_required = yaml.safe_load(f) or {}
    with open(RULES_DIR / "medical_necessity.yaml") as f:
        necessity = yaml.safe_load(f) or {}
    with open(RULES_DIR / "plans.yaml") as f:
        plans = yaml.safe_load(f) or {}
    return pa_required, necessity, plans


def requires_pa(plan_id: str, cpt: str) -> bool:
    pa_required, _, _ = _load()
    return cpt in (pa_required.get(plan_id) or [])


def is_covered(plan_id: str, cpt: str) -> bool:
    _, _, plans = _load()
    plan = plans.get(plan_id) or {}
    return cpt in (plan.get("covered_cpt") or [])


def criteria_for(cpt: str) -> dict:
    _, necessity, _ = _load()
    return necessity.get(cpt) or {}


def evaluate(packet: Packet) -> Decision:
    """Approve / needs-info / deny a submitted packet against medical-necessity rules."""
    crit = criteria_for(packet.order.cpt)
    if not crit:
        return Decision(outcome=Outcome.DENIED,
                        reason=f"No medical-necessity policy on file for CPT {packet.order.cpt}.")

    req_dx = set(crit.get("required_diagnoses") or [])
    req_tx = set(crit.get("required_prior_treatments") or [])
    have_dx = set(packet.diagnosis_codes)
    have_tx = set(packet.prior_treatments)

    # 1) Diagnosis must justify the procedure at all.
    if req_dx and not (req_dx & have_dx):
        return Decision(
            outcome=Outcome.DENIED,
            reason=("Submitted diagnosis codes do not establish medical necessity for "
                    f"{crit.get('display', packet.order.cpt)}. Need one of: {sorted(req_dx)}."),
            missing=[f"diagnosis:{c}" for c in sorted(req_dx)],
        )

    # 2) Required prior treatment / documentation must be present.
    missing_tx = sorted(req_tx - have_tx)
    if missing_tx:
        return Decision(
            outcome=Outcome.NEEDS_INFO,
            reason=("Diagnosis supports the request, but required documentation is missing: "
                    f"{missing_tx}."),
            missing=[f"prior_treatment:{t}" for t in missing_tx],
        )

    # 3) A written clinical justification is mandatory.
    if not packet.clinical_justification.strip():
        return Decision(outcome=Outcome.NEEDS_INFO,
                        reason="Clinical justification narrative is blank.",
                        missing=["clinical_justification"])

    return Decision(outcome=Outcome.APPROVED,
                    reason=f"All medical-necessity criteria met for {crit.get('display', packet.order.cpt)}.")
