"""Per-agent scoped identity and least-privilege permissions (planv2 B3.3).

Each agent may touch only the tools and patient-data fields its job needs. Enforced at call
time by compliance.access. Examples of the guarantees this encodes:
  - the Appealer cannot call the payer's decision/approve path,
  - the Checker cannot read the clinical notes it doesn't need."""
from __future__ import annotations
from pydantic import BaseModel


class AgentIdentity(BaseModel):
    name: str
    allowed_tools: frozenset[str]
    allowed_fields: frozenset[str]      # PatientCase fields this agent may read


AGENTS: dict[str, AgentIdentity] = {
    "checker": AgentIdentity(
        name="checker",
        allowed_tools=frozenset({"rules.pa_lookup"}),
        allowed_fields=frozenset({"plan_id", "order"})),                 # no clinical notes
    "verifier": AgentIdentity(
        name="verifier",
        allowed_tools=frozenset({"payer.eligibility"}),
        allowed_fields=frozenset({"plan_id", "order", "coverage_active"})),
    "assembler": AgentIdentity(
        name="assembler",
        allowed_tools=frozenset({"records.read"}),
        allowed_fields=frozenset({"patient_id", "order", "conditions",
                                  "prior_treatments", "notes"})),
    "submitter": AgentIdentity(
        name="submitter",
        allowed_tools=frozenset({"payer.decide"}),
        allowed_fields=frozenset({"order"})),
    "appealer": AgentIdentity(
        name="appealer",
        allowed_tools=frozenset({"records.read"}),                       # NOT payer.decide
        allowed_fields=frozenset({"order", "conditions", "prior_treatments",
                                  "notes", "denial_reason"})),
}


def can_use_tool(agent_name: str, tool: str) -> bool:
    ident = AGENTS.get(agent_name)
    return bool(ident and tool in ident.allowed_tools)


def can_read_field(agent_name: str, field: str) -> bool:
    ident = AGENTS.get(agent_name)
    return bool(ident and field in ident.allowed_fields)
