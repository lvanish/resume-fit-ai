"""Deterministic Match Score math.

This module does not import Laya. It turns five expected values, each on a 0–4
scale, into one integer from 0 to 100.
"""

from __future__ import annotations

from dataclasses import dataclass

DIMENSIONS = (
    "required_skills",
    "experience",
    "responsibilities",
    "preferred_skills",
    "overall_alignment",
)
WEIGHTS = {
    "required_skills": 0.40,
    "experience": 0.20,
    "responsibilities": 0.20,
    "preferred_skills": 0.10,
    "overall_alignment": 0.10,
}
MIN_LEVEL = 0
MAX_LEVEL = 4


@dataclass(frozen=True)
class MatchAnalysis:
    """Internal dimension scores plus the weighted Match Score.

    This object is for tests, logs, and evaluation. The public API returns
    only the integer score.
    """

    required_skills: float
    experience: float
    responsibilities: float
    preferred_skills: float
    overall_alignment: float
    final_score: int

    def as_dict(self) -> dict[str, float | int]:
        return {
            "required_skills": self.required_skills,
            "experience": self.experience,
            "responsibilities": self.responsibilities,
            "preferred_skills": self.preferred_skills,
            "overall_alignment": self.overall_alignment,
            "final_score": self.final_score,
        }


def calculate_match_score(
    required_skills: float,
    experience: float,
    responsibilities: float,
    preferred_skills: float,
    overall_alignment: float,
) -> int:
    """Weight five 0–4 expected values and round to an integer from 0 to 100.

    Rounding uses Python's half-to-even rule.
    """
    values = {
        "required_skills": required_skills,
        "experience": experience,
        "responsibilities": responsibilities,
        "preferred_skills": preferred_skills,
        "overall_alignment": overall_alignment,
    }
    weighted = 0.0
    for name, weight in WEIGHTS.items():
        weighted += (_validated_level(name, values[name]) / MAX_LEVEL) * weight
    match_score = round(weighted * 100)
    if match_score < 0 or match_score > 100:
        raise ValueError(f"Weighted match score {match_score} is outside 0-100.")
    return match_score


def match_analysis(scores: dict[str, float]) -> MatchAnalysis:
    """Build the internal analysis object from a dimension-score mapping."""
    missing = [name for name in DIMENSIONS if name not in scores]
    if missing:
        raise ValueError("Missing dimension scores: " + ", ".join(missing))
    ordered = {name: scores[name] for name in DIMENSIONS}
    final_score = calculate_match_score(
        required_skills=ordered["required_skills"],
        experience=ordered["experience"],
        responsibilities=ordered["responsibilities"],
        preferred_skills=ordered["preferred_skills"],
        overall_alignment=ordered["overall_alignment"],
    )
    return MatchAnalysis(
        required_skills=float(ordered["required_skills"]),
        experience=float(ordered["experience"]),
        responsibilities=float(ordered["responsibilities"]),
        preferred_skills=float(ordered["preferred_skills"]),
        overall_alignment=float(ordered["overall_alignment"]),
        final_score=final_score,
    )


def _validated_level(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Score for '{name}' is not numeric.")
    level = float(value)
    if level < MIN_LEVEL or level > MAX_LEVEL:
        raise ValueError(f"Score for '{name}' is outside {MIN_LEVEL}-{MAX_LEVEL}.")
    return level
