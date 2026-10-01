"""Build one Laya question per skill, responsibility, and role. Experience stays deterministic."""

from __future__ import annotations

import re

from app.models.requirement import Requirement, RequirementCategory

_LAYA_CATEGORIES = (
    RequirementCategory.REQUIRED_SKILL,
    RequirementCategory.PREFERRED_SKILL,
    RequirementCategory.RESPONSIBILITY,
    RequirementCategory.ROLE,
)

_EVIDENCE_RULES = (
    "Base the decision ONLY on the candidate profile. "
    "Explicit evidence is required. "
    "Do not infer a skill from a vaguely related technology. "
    "Do not assume knowledge of a framework because another framework is present. "
    "If there is insufficient evidence, answer NO."
)


def laya_requirements(requirements: list[Requirement]) -> list[Requirement]:
    """Return non-experience requirements in batch order, keeping input order inside a category."""
    grouped: dict[RequirementCategory, list[Requirement]] = {category: [] for category in _LAYA_CATEGORIES}
    for requirement in requirements:
        if requirement.category in grouped:
            grouped[requirement.category].append(requirement)
    ordered: list[Requirement] = []
    for category in _LAYA_CATEGORIES:
        ordered.extend(grouped[category])
    return ordered


def build_questions(requirements: list[Requirement], target_role: str | None) -> dict[str, dict]:
    """Map requirement names to Laya question specs. Keys are stable within one call."""
    questions: dict[str, dict] = {}
    for index, requirement in enumerate(laya_requirements(requirements)):
        key = _question_key(requirement, index)
        if requirement.category == RequirementCategory.ROLE:
            questions[key] = _role_question(target_role or requirement.name)
        elif requirement.category == RequirementCategory.RESPONSIBILITY:
            questions[key] = _responsibility_question(requirement.name)
        elif requirement.category == RequirementCategory.PREFERRED_SKILL:
            questions[key] = _skill_question("preferred", requirement.name)
        else:
            questions[key] = _skill_question("required", requirement.name)
    return questions


def plan_batches(questions: dict[str, dict], max_per_batch: int | None) -> list[dict[str, dict]]:
    """Split an ordered question map. None sends every question in one predict call."""
    if not questions:
        return []
    items = list(questions.items())
    if max_per_batch is None or max_per_batch >= len(items):
        return [dict(items)]
    if max_per_batch < 1:
        raise ValueError("Requirement question batch size must be at least 1.")
    return [dict(items[start : start + max_per_batch]) for start in range(0, len(items), max_per_batch)]


def candidate_state(role: str | None, years_of_experience: float | None, skills: list[str], responsibilities: list[str]) -> dict:
    """The only state sent to requirement-level Laya."""
    return {
        "role": role,
        "years_of_experience": years_of_experience,
        "skills": list(skills),
        "responsibilities": list(responsibilities),
    }


def _skill_question(kind: str, skill: str) -> dict:
    return {
        "type": "noul",
        "instructions": (
            f"Does the candidate evidence demonstrate experience with the {kind} skill '{skill}'? "
            + _EVIDENCE_RULES
        ),
        "criteria": {
            "false": "The candidate profile does not explicitly demonstrate this skill.",
            "true": "The candidate profile explicitly demonstrates this skill.",
        },
    }


def _responsibility_question(responsibility: str) -> dict:
    return {
        "type": "noul",
        "instructions": (
            "Does the candidate evidence demonstrate experience performing work relevant to "
            f"this responsibility: '{responsibility}'? "
            "Base the decision ONLY on the candidate profile. "
            "Answer YES only for directly demonstrated experience. "
            "Answer NO for loosely related experience and for no evidence. "
            "Do not infer generic professional skills from unrelated engineering work. "
            "If there is insufficient evidence, answer NO."
        ),
        "criteria": {
            "false": "The profile does not directly demonstrate this responsibility.",
            "true": "The profile directly demonstrates this responsibility.",
        },
    }


def _role_question(target_role: str) -> dict:
    return {
        "type": "choice",
        "instructions": (
            "How closely does the candidate's role/background align with the target role "
            f"'{target_role}'? "
            "MATCH means the same or a clearly equivalent role family. "
            "PARTIAL_MATCH means some overlap exists but the background is materially different. "
            "NO_MATCH means the background is unrelated to the target role. "
            "Base the decision ONLY on the candidate profile."
        ),
        "criteria": {
            "MATCH": "Candidate has the same or clearly equivalent role family.",
            "PARTIAL_MATCH": "Some overlap exists but the candidate's background is materially different.",
            "NO_MATCH": "The candidate's background is unrelated to the target role.",
        },
    }


def _question_key(requirement: Requirement, index: int) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", requirement.name.casefold()).strip("_")[:48]
    prefix = requirement.category.value.lower()
    if not slug:
        slug = "item"
    return f"{prefix}_{index}_{slug}"
