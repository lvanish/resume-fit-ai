"""Render extracted profiles as compact factual text for the existing Laya path."""

from app.models.candidate_profile import CandidateProfile
from app.models.job_profile import JobProfile


def render_candidate_profile(profile: CandidateProfile) -> str:
    lines = ["Candidate profile"]
    _line(lines, "Role", profile.role)
    if profile.years_of_experience is not None:
        lines.append(f"Years of experience: {profile.years_of_experience}")
    _list(lines, "Skills", profile.skills)
    _list(lines, "Responsibilities", profile.responsibilities)
    return "\n".join(lines)


def render_job_profile(profile: JobProfile) -> str:
    lines = ["Job profile"]
    _line(lines, "Role", profile.role)
    if profile.minimum_years_experience is not None:
        lines.append(f"Minimum years of experience: {profile.minimum_years_experience}")
    _list(lines, "Required skills", profile.required_skills)
    _list(lines, "Preferred skills", profile.preferred_skills)
    _list(lines, "Responsibilities", profile.responsibilities)
    return "\n".join(lines)


def _line(lines: list[str], label: str, value: str | None) -> None:
    if value and value.strip():
        lines.append(f"{label}: {value.strip()}")


def _list(lines: list[str], label: str, values: list[str]) -> None:
    cleaned = [value.strip() for value in values if value and value.strip()]
    if cleaned:
        lines.append(f"{label}: " + "; ".join(cleaned))
