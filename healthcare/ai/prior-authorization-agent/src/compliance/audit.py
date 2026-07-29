"""Append-only, timestamped audit trail (planv2 B2/B3.4): who / what / when for every
agent action and data access. Entries can be added and read, never mutated or removed."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class AuditEntry:
    ts: str
    actor: str
    action: str
    target: str = ""
    detail: str = ""

    def render(self) -> str:
        tail = f" — {self.detail}" if self.detail else ""
        tgt = f" [{self.target}]" if self.target else ""
        return f"{self.ts} {self.actor}: {self.action}{tgt}{tail}"


class AuditTrail:
    """Append-only. No public mutator other than record(); entries() returns a copy."""

    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []

    def record(self, actor: str, action: str, target: str = "", detail: str = "") -> AuditEntry:
        entry = AuditEntry(
            ts=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            actor=actor, action=action, target=target, detail=detail)
        self._entries.append(entry)
        return entry

    def entries(self) -> tuple[AuditEntry, ...]:
        return tuple(self._entries)

    def render(self) -> list[str]:
        return [f"[{i + 1:02d}] {e.render()}" for i, e in enumerate(self._entries)]

    def __len__(self) -> int:
        return len(self._entries)
