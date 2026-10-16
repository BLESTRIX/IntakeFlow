from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.api import Category

SCHEMA_VERSION = "extraction-v1"
ExtractionField = Literal[
    "category",
    "room_or_area",
    "affected_item",
    "symptoms",
    "reported_onset",
    "reported_impact",
    "summary",
    "multiple_issues_detected",
    "needs_staff_attention",
    "attention_reason",
]
MissingField = Literal[
    "category", "room_or_area", "affected_item", "symptoms", "reported_onset", "reported_impact"
]


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: ExtractionField
    message_id: str
    quote: str = Field(min_length=1, max_length=5000)


class Extraction(BaseModel):
    """All fields required for strict native JSON Schema; absent facts are null/empty."""

    model_config = ConfigDict(extra="forbid")
    category: Category
    room_or_area: str | None
    affected_item: str | None
    symptoms: list[str]
    reported_onset: str | None
    reported_impact: str | None
    multiple_issues_detected: bool
    needs_staff_attention: bool
    attention_reason: str | None
    summary: str = Field(min_length=1, max_length=1000)
    missing_information: list[MissingField]
    follow_up_questions: list[str] = Field(max_length=3)
    evidence: list[Evidence]


class EvidenceError(ValueError):
    pass


def validate_evidence(extraction, messages):
    source = {m["id"]: m["body"] for m in messages}
    for item in extraction.evidence:
        if item.message_id not in source or item.quote not in source[item.message_id]:
            raise EvidenceError("Invalid message reference or non-exact source quotation")
    # Quote matching proves provenance, not semantic correctness.
    return extraction
