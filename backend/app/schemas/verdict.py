"""The shape the language model's verdict answer must have."""

from typing import Literal

from pydantic import BaseModel, Field

VerdictLabel = Literal["likely_approved", "missing_information", "likely_denied"]
RequirementStatus = Literal["met", "not_met", "unclear"]

VERDICT_LABELS = ["likely_approved", "missing_information", "likely_denied"]


class RequirementCheck(BaseModel):
    """One policy requirement and whether the request satisfies it."""

    requirement: str = Field(min_length=3, max_length=400)
    status: RequirementStatus
    evidence_needed: str | None = Field(default=None, max_length=400)
    chunk_id: int | None = None


class Citation(BaseModel):
    """A quote from a policy chunk that supports the verdict."""

    chunk_id: int
    quote: str = Field(min_length=5, max_length=600)


class VerdictAnswer(BaseModel):
    """The full answer we ask the model for."""

    verdict: VerdictLabel
    reason: str = Field(min_length=10, max_length=1200)
    requirements: list[RequirementCheck] = Field(min_length=1)
    citations: list[Citation] = Field(min_length=1)
