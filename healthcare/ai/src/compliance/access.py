"""Access control (planv2 B2 RBAC + B3.3 per-agent least privilege).

Two layers:
  - Human RBAC: clinician / reviewer / admin. Only reviewer/admin may approve, view full
    packets, or erase cases.
  - Agent tool policy: each agent may only call tools on its allow-list (see governance.identity).
Both are enforced at call time, never assumed."""
from __future__ import annotations
from src.governance import identity


class AccessDenied(PermissionError):
    pass


ROLE_PERMISSIONS: dict[str, set[str]] = {
    "clinician": {"submit"},
    "reviewer": {"submit", "approve", "view_full_packet", "delete"},
    "admin": {"submit", "approve", "view_full_packet", "delete", "manage"},
}


def can(role: str, action: str) -> bool:
    return action in ROLE_PERMISSIONS.get(role, set())


def enforce(role: str, action: str) -> None:
    if not can(role, action):
        raise AccessDenied(f"role '{role}' may not perform '{action}'")


def enforce_tool(agent_name: str, tool: str) -> None:
    """Policy-check an agent's tool call against its least-privilege scope."""
    if not identity.can_use_tool(agent_name, tool):
        raise AccessDenied(f"agent '{agent_name}' is not permitted to use tool '{tool}'")
