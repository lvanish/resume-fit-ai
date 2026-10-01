"""Deterministic experience comparison. This module does not call Laya."""


def calculate_experience_score(candidate_years: float | None, required_years: float | None) -> float:
    """Return a 0.0–1.0 score. Missing years stay neutral. Nothing is invented."""
    if required_years is None or candidate_years is None:
        return 0.5
    if candidate_years >= required_years:
        return 1.0
    gap = required_years - candidate_years
    if gap < 1:
        return 0.7
    if gap <= 2:
        return 0.4
    return 0.15
