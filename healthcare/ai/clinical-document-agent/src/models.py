"""Versioned Pydantic contracts exchanged between agents (plan §7, §B3.1)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class EncounterCase(BaseModel):
    encounter_id: str
    age: int
    sex: str
    specialty: str
    source_note: str                       # raw visit input (transcript / notes)
    reference_codes: list[str] = Field(default_factory=list)  # ground truth for eval (optional)


class SOAPNote(BaseModel):
    subjective: str = ""
    objective: str = ""
    assessment: str = ""
    plan: str = ""

    def sections(self) -> dict[str, str]:
        return {"subjective": self.subjective, "objective": self.objective,
                "assessment": self.assessment, "plan": self.plan}


class Code(BaseModel):
    system: str                            # "ICD-10" | "CPT"
    code: str
    rationale: str = ""


class Record(BaseModel):
    """FHIR-shaped record written to the mock EHR only after sign-off."""
    resource_type: str = "Composition"
    record_id: str
    subject: str
    section: dict[str, str]
    codes: list[Code]
    attester: str
