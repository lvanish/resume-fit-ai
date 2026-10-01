"""Factual hiring requirements extracted from a job description."""

from pydantic import BaseModel, Field


class JobProfile(BaseModel):
    """Minimum job facts used to build explicit requirements."""

    role: str | None = Field(
        default=None,
        description="Advertised position title. Do not append the company name or shorten away seniority.",
    )
    minimum_years_experience: float | None = Field(
        default=None,
        description="Minimum years stated in the description, otherwise null.",
    )
    required_skills: list[str] = Field(
        default_factory=list,
        description="Skills the description requires or lists as key skills.",
    )
    preferred_skills: list[str] = Field(
        default_factory=list,
        description="Skills the description marks as preferred or nice to have.",
    )
    responsibilities: list[str] = Field(
        default_factory=list,
        description="Exact copied duty sentences from the job description. Do not paraphrase.",
    )
