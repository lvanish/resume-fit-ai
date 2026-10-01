"""Aggregate requirement probabilities into one Match Score. This module does not call Laya."""

from __future__ import annotations

from dataclasses import dataclass

NEUTRAL = 0.5


@dataclass(frozen=True)
class RequirementWeights:
    required_skills: float = 0.55
    responsibilities: float = 0.15
    experience: float = 0.15
    role: float = 0.10
    preferred_skills: float = 0.05

    def as_tuple(self) -> tuple[tuple[str, float], ...]:
        return (
            ("required_skills", self.required_skills),
            ("responsibilities", self.responsibilities),
            ("experience", self.experience),
            ("role", self.role),
            ("preferred_skills", self.preferred_skills),
        )


def average_or_neutral(values: list[float]) -> float:
    if not values:
        return NEUTRAL
    return sum(values) / len(values)


def aggregate_match_score(
    *,
    required_skill_score: float,
    responsibility_score: float,
    experience_score: float,
    role_score: float,
    preferred_skill_score: float,
    weights: RequirementWeights,
) -> int:
    """Weight five 0–1 signals and round to an integer from 0 to 100."""
    parts = {
        "required_skills": required_skill_score,
        "responsibilities": responsibility_score,
        "experience": experience_score,
        "role": role_score,
        "preferred_skills": preferred_skill_score,
    }
    weighted = 0.0
    for name, weight in weights.as_tuple():
        weighted += _unit(name, parts[name]) * weight
    match_score = round(weighted * 100)
    if match_score < 0:
        return 0
    if match_score > 100:
        return 100
    return match_score


def _unit(name: str, value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} score must be numeric.")
    number = float(value)
    if number < 0 or number > 1:
        raise ValueError(f"{name} score {number} is outside 0-1.")
    return number
