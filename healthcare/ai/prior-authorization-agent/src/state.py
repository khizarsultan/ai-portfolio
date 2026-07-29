"""Shared LangGraph state. Every node reads/updates this and appends to audit_log."""
from __future__ import annotations
from typing import Optional, TypedDict
from src.models import PatientCase, Packet, Decision


class PAState(TypedDict, total=False):
    case: PatientCase
    needs_pa: Optional[bool]
    coverage_ok: Optional[bool]
    packet: Optional[Packet]
    decision: Optional[Decision]
    denial_reason: Optional[str]
    actor_role: str              # RBAC role that submitted this request
    attempt: int                 # total agent steps taken (efficiency metric)
    needs_info_loops: int        # count of needs-info resubmission cycles
    appeal_loops: int            # count of appeal resubmission cycles
    audit_log: list[str]         # append-only, human-readable trail
    status: str                  # running | done | human_review


def log(state: PAState, agent: str, message: str) -> None:
    """Append a timestamped-style entry. Step index keeps the trail ordered."""
    trail = state.setdefault("audit_log", [])
    trail.append(f"[{len(trail) + 1:02d}] {agent}: {message}")
