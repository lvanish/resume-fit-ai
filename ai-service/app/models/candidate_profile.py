"""Factual fields extracted from a resume. Unstated facts stay empty."""

from pydantic import BaseModel, Field


class CandidateProfile(BaseModel):
    """Minimum candidate facts used for later requirement matching."""

    role: str | None = Field(
        default=None,
        description="Stated role or job title from the resume, lightly normalized, otherwise null.",
    )
    years_of_experience: float | None = Field(
        default=None,
        description="Years of experience stated in the resume, otherwise null.",
    )
    responsibilities: list[str] = Field(
        default_factory=list,
        description="Exact copied sentences or phrases from the resume about work performed. Do not paraphrase. Do not leave this empty when the resume describes work.",
    )
    skills: list[str] = Field(
        default_factory=list,
        description="Technology names explicitly written in the resume. List each skill once.",
    )
