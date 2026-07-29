"""Versioned Pydantic handoff contracts (planv2 B3.1 agent interoperability).

Agents exchange data through a single validated HandoffContext, not loose dicts. Every node
handoff is validated against this contract; a mismatch escalates to human review. Handoffs
are idempotent — re-validating the same state yields the same context (safe under retries)."""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel

from src.models import PatientCase, Packet, Decision

CONTRACT_VERSION = "1.0.0"


class HandoffContext(BaseModel):
    """The full inter-agent contract. Carries state + audit so no agent loses context."""
    version: str = CONTRACT_VERSION
    case: PatientCase
    needs_pa: Optional[bool] = None
    coverage_ok: Optional[bool] = None
    packet: Optional[Packet] = None
    decision: Optional[Decision] = None
    denial_reason: Optional[str] = None
    attempt: int = 0
    needs_info_loops: int = 0
    appeal_loops: int = 0
    status: str = "running"
    audit: list[str] = []


def validate_handoff(state: dict) -> HandoffContext:
    """Validate a graph state against the contract. Raises pydantic.ValidationError if invalid."""
    return HandoffContext(
        case=state["case"],
        needs_pa=state.get("needs_pa"),
        coverage_ok=state.get("coverage_ok"),
        packet=state.get("packet"),
        decision=state.get("decision"),
        denial_reason=state.get("denial_reason"),
        attempt=state.get("attempt", 0),
        needs_info_loops=state.get("needs_info_loops", 0),
        appeal_loops=state.get("appeal_loops", 0),
        status=state.get("status", "running"),
        audit=state.get("audit_log", []),
    )
