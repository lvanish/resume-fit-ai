"""Turns raw resume and job-description text into validated profiles."""

from app.models.candidate_profile import CandidateProfile
from app.models.job_profile import JobProfile
from app.services.llm_service import LLMService


class ProfileExtractionService:
    def __init__(self, llm_service: LLMService) -> None:
        self._llm = llm_service

    def extract_candidate_profile(self, resume: str) -> CandidateProfile:
        return self._llm.extract_candidate_profile(resume)

    def extract_job_profile(self, job_description: str) -> JobProfile:
        return self._llm.extract_job_profile(job_description)
