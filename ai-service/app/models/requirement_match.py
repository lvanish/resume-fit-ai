"""Internal requirement-level match details. The public API does not return this."""

from pydantic import BaseModel, Field

from app.models.requirement import RequirementCategory


class RequirementMatchResult(BaseModel):
    """One requirement decision. `probability_yes` is Laya's continuous noul value."""

    requirement: str
    category: RequirementCategory
    probability_yes: float | None = None
    decision: str | None = None


class RequirementMatchAnalysis(BaseModel):
    """Aggregated requirement signals and the integer Match Score."""

    required_skill_score: float
    preferred_skill_score: float
    responsibility_score: float
    experience_score: float
    role_score: float
    final_score: int
    requirements: list[RequirementMatchResult] = Field(default_factory=list)
    batch_count: int = 0
    batch_latency_ms: list[float] = Field(default_factory=list)
    total_latency_ms: float = 0.0
