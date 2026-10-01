"""Public score selection. The HTTP response is still only the integer score."""

from app.config import Settings
from app.services.laya_service import BroadLayaScoringService
from app.services.requirement_pipeline import score_requirement_match


def public_match_score(settings: Settings, resume: str, job_description: str) -> int:
    if settings.requirement_matching_enabled:
        return score_requirement_match(settings, resume, job_description)
    return BroadLayaScoringService(settings).calculate_match_score(resume, job_description)
