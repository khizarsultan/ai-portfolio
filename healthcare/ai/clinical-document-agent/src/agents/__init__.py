"""Agent functions operate on EncounterState in place and append to the audit log."""
from __future__ import annotations


def log(state: dict, agent: str, message: str) -> None:
    trail = state.setdefault("audit_log", [])
    trail.append(f"[{len(trail) + 1:02d}] {agent}: {message}")
