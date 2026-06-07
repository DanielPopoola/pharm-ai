from dataclasses import dataclass

from pydantic import BaseModel, Field


class PharmacistQuery(BaseModel):
    drug_name: str = Field(
        min_length=1,
        description="Generic or brand drug name the pharmacist wants reviewed.",
    )
    patient_allergies: list[str] = Field(
        default_factory=list,
        description="Known patient allergies relevant to drug substitution decisions.",
    )
    patient_conditions: list[str] = Field(
        default_factory=list,
        description=(
            "Known patient diagnoses or clinical conditions relevant to contraindication review."
        ),
    )


class DrugProfile(BaseModel):
    drug_name: str = Field(description="Normalized generic name of the requested drug.")
    brand_names: list[str] = Field(
        default_factory=list,
        description="Known brand names from the drug label.",
    )
    therapeutic_class: str = Field(description="FDA established pharmacologic class for the drug.")
    summary: str = Field(
        default="", description="Write a 2-3 sentence clinical summary grounded in retrieved_context."
    )


class AlternativeDrug(BaseModel):
    drug_name: str = Field(description="Normalized generic name of the therapeutically similar drug.")
    brand_names: list[str] = Field(
        default_factory=list,
        description="Known brand names for the alternative drug.",
    )
    therapeutic_class: str = Field(
        description="FDA established pharmacologic class for the alternative drug."
    )
    rationale: str = Field(
        default="",
        description="Write one sentence explaining why this is a relevant alternative,\
              grounded in indications_context.",
    )
    cautions: list[str] = Field(
        default_factory=list,
        description="Patient-specific cautions found for this alternative.",
    )


class ContraindicationFlag(BaseModel):
    drug_name: str
    condition: str  # one short phrase, e.g. "bronchial asthma"


class ContraindicationEvidence(BaseModel):
    drug_name: str
    raw_text: str  # keep short — first 200 chars of the chunk only


class DrugResponse(BaseModel):
    requested_drug: DrugProfile = Field(description="Profile for the drug requested by the pharmacist.")
    alternatives: list[AlternativeDrug] = Field(
        default_factory=list,
        description="Therapeutically similar drugs in the same FDA established pharmacologic class.",
    )
    contraindication_flags: list[ContraindicationFlag] = Field(default_factory=list)
    clinical_caveats: list[str] = Field(
        default_factory=list,
        description="Safety caveats, missing-data notes, or pharmacist review reminders.",
    )
    cache_miss: bool = False


@dataclass(frozen=True)
class PharmAIDeps:
    drug_name: str
    patient_allergies: list[str]
    patient_conditions: list[str]
