"""Shared input for a later requirement-level match. Laya is not called here."""

from pydantic import BaseModel, Field

from app.models.candidate_profile import CandidateProfile
from app.models.job_profile import JobProfile
from app.models.requirement import Requirement


class MatchingContext(BaseModel):
    """Candidate facts, job facts, and the job's explicit requirements."""

    candidate: CandidateProfile
    job: JobProfile
    requirements: list[Requirement] = Field(default_factory=list)
