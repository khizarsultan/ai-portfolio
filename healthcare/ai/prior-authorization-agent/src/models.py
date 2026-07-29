"""Pydantic data schemas shared across agents, payer, and eval."""
from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class Condition(BaseModel):
    code: str = Field(description="ICD-10 diagnosis code, e.g. M23.2")
    display: str = ""


class PriorTreatment(BaseModel):
    type: str = Field(description="e.g. conservative_treatment, sleep_questionnaire")
    date: str = ""
    description: str = ""


class Order(BaseModel):
    cpt: str = Field(description="CPT procedure code being requested, e.g. 73721")
    display: str = ""


class PatientCase(BaseModel):
    patient_id: str
    age: int
    sex: str
    plan_id: str
    coverage_active: bool = True
    conditions: list[Condition] = []
    order: Order
    prior_treatments: list[PriorTreatment] = []
    notes: str = ""
    # GDPR purpose limitation (planv2 B2): processing is refused if either is missing.
    purpose: Optional[str] = None
    lawful_basis: Optional[str] = None


class Packet(BaseModel):
    """The prior-authorization request the payer evaluates."""
    patient_id: str
    order: Order
    diagnosis_codes: list[str] = []
    prior_treatments: list[str] = []          # treatment types cited as evidence
    clinical_justification: str = ""
    attachments: list[str] = []
    appeal_letter: Optional[str] = None


class Outcome(str, Enum):
    APPROVED = "APPROVED"
    DENIED = "DENIED"
    NEEDS_INFO = "NEEDS_INFO"


class Decision(BaseModel):
    outcome: Outcome
    reason: str = ""
    missing: list[str] = []                    # what would flip NEEDS_INFO/DENIED
