"""Turn a JobProfile into explicit requirements. This does not call Laya."""

from __future__ import annotations

import re

from app.models.candidate_profile import CandidateProfile
from app.models.job_profile import JobProfile
from app.models.matching_context import MatchingContext
from app.models.requirement import Requirement, RequirementCategory

_PLACEHOLDER = re.compile(
    r"^(?:none|n/?a|na|unknown|null|not specified|not available|no preferred skills?|-+)$",
    re.IGNORECASE,
)


def build_requirements(job: JobProfile) -> list[Requirement]:
    """Convert job facts into unique requirements. Preferred skills already required are dropped."""
    requirements: list[Requirement] = []
    seen: set[tuple[str, str]] = set()
    required_names: set[str] = set()

    _add(requirements, seen, job.role, RequirementCategory.ROLE)
    for skill in job.required_skills:
        if _add(requirements, seen, skill, RequirementCategory.REQUIRED_SKILL):
            required_names.add(_norm(skill))
    for skill in job.preferred_skills:
        if _norm(skill) in required_names:
            continue
        _add(requirements, seen, skill, RequirementCategory.PREFERRED_SKILL)
    for duty in job.responsibilities:
        _add(requirements, seen, duty, RequirementCategory.RESPONSIBILITY)
    if job.minimum_years_experience is not None:
        _add(
            requirements,
            seen,
            _experience_name(job.minimum_years_experience),
            RequirementCategory.EXPERIENCE,
        )
    return requirements


def build_matching_context(candidate: CandidateProfile, job: JobProfile) -> MatchingContext:
    """Assemble the shared matching input without scoring it."""
    return MatchingContext(candidate=candidate, job=job, requirements=build_requirements(job))


def _add(
    requirements: list[Requirement],
    seen: set[tuple[str, str]],
    name: str | None,
    category: RequirementCategory,
) -> bool:
    if name is None:
        return False
    cleaned = name.strip()
    if not cleaned or _PLACEHOLDER.match(cleaned):
        return False
    key = (category.value, _norm(cleaned))
    if key in seen:
        return False
    seen.add(key)
    requirements.append(Requirement(name=cleaned, category=category))
    return True


def _experience_name(years: float) -> str:
    shown = str(int(years)) if float(years).is_integer() else str(years)
    unit = "year" if shown == "1" else "years"
    return f"minimum {shown} {unit}"


def _norm(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()
