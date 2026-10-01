"""Extract profiles, build requirements, then score them. Each step stays separate."""

import logging

from app.config import Settings
from app.models.requirement_match import RequirementMatchAnalysis
from app.services.llm_service import LLMService
from app.services.profile_extraction_service import ProfileExtractionService
from app.services.requirement_builder import build_requirements
from app.services.requirement_matching_service import RequirementMatchingService

logger = logging.getLogger(__name__)


def analyze_requirements(settings: Settings, resume: str, job_description: str) -> RequirementMatchAnalysis:
    extraction = ProfileExtractionService(LLMService(settings))
    logger.info("candidate_extraction_started")
    try:
        candidate = extraction.extract_candidate_profile(resume)
    except Exception as exc:
        _log_stage_failure("candidate_extraction", exc)
        raise
    logger.info("candidate_extraction_completed")
    logger.info("job_extraction_started")
    try:
        job = extraction.extract_job_profile(job_description)
    except Exception as exc:
        _log_stage_failure("job_extraction", exc)
        raise
    logger.info("job_extraction_completed")
    try:
        requirements = build_requirements(job)
    except Exception as exc:
        _log_stage_failure("requirement_building", exc)
        raise
    logger.info("requirements_built count=%s", len(requirements))
    return RequirementMatchingService(settings).match(candidate, job, requirements)


def _log_stage_failure(stage: str, exc: Exception) -> None:
    logger.exception(
        "requirement_matching_failed stage=%s exception_type=%s message=%s",
        stage,
        type(exc).__name__,
        exc,
    )


def score_requirement_match(settings: Settings, resume: str, job_description: str) -> int:
    return analyze_requirements(settings, resume, job_description).final_score
