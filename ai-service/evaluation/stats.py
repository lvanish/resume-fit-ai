"""Pure summaries of evaluation records. No model calls."""

from __future__ import annotations

import statistics
from collections import defaultdict

CATEGORIES = ("VERY_STRONG", "STRONG", "MODERATE", "WEAK", "VERY_WEAK")
DIMENSIONS = (
    "required_skills",
    "experience",
    "responsibilities",
    "preferred_skills",
    "overall_alignment",
)
# Differences at or above these gaps are reported as flags. They are not
# assertions that the language model must satisfy a fixed score.
CLOSE_SCORE_GAP = 10
MATERIAL_MISMATCH_GAP = 15
LONG_DOCUMENT_GAP = 15

DOCUMENT_KEYS = frozenset({"resume", "jobDescription", "job_description"})


def category_summary(records: list[dict]) -> list[dict]:
    grouped: dict[str, list[int]] = defaultdict(list)
    for record in records:
        grouped[str(record["expectedCategory"])].append(int(record["final_score"]))
    rows = []
    for category in CATEGORIES:
        scores = grouped.get(category, [])
        if not scores:
            rows.append(
                {"category": category, "count": 0, "min": None, "max": None, "average": None}
            )
            continue
        rows.append(
            {
                "category": category,
                "count": len(scores),
                "min": min(scores),
                "max": max(scores),
                "average": round(statistics.fmean(scores), 2),
            }
        )
    return rows


def separation_flags(rows: list[dict]) -> list[str]:
    """Flag when a stronger category's average is below a weaker category's average."""
    present = [row for row in rows if row["count"]]
    flags = []
    for stronger, weaker in zip(present, present[1:]):
        if stronger["average"] < weaker["average"]:
            flags.append(
                f"{stronger['category']} average {stronger['average']} is below "
                f"{weaker['category']} average {weaker['average']}"
            )
    return flags


def score_distribution(scores: list[int]) -> dict:
    if not scores:
        return {
            "count": 0,
            "lowest": None,
            "highest": None,
            "average": None,
            "median": None,
            "standard_deviation": None,
            "bands": {label: 0 for label in _band_labels()},
        }
    return {
        "count": len(scores),
        "lowest": min(scores),
        "highest": max(scores),
        "average": round(statistics.fmean(scores), 2),
        "median": statistics.median(scores),
        "standard_deviation": round(statistics.pstdev(scores), 2) if len(scores) > 1 else 0.0,
        "bands": band_counts(scores),
    }


def band_counts(scores: list[int]) -> dict[str, int]:
    counts = {label: 0 for label in _band_labels()}
    for score in scores:
        counts[_band(score)] += 1
    return counts


def dimension_averages(records: list[dict]) -> dict[str, float | None]:
    averages: dict[str, float | None] = {}
    for name in DIMENSIONS:
        values = [float(record[name]) for record in records if name in record]
        averages[name] = round(statistics.fmean(values), 4) if values else None
    return averages


def monotonicity_flags(series: list[dict]) -> list[str]:
    """Flag a later, intentionally stronger version that scores lower."""
    flags = []
    ordered = sorted(series, key=lambda item: item["step"])
    for previous, current in zip(ordered, ordered[1:]):
        if int(current["final_score"]) < int(previous["final_score"]):
            flags.append(
                f"{current['series']} step {current['step']} scored {current['final_score']}, "
                f"below step {previous['step']} score {previous['final_score']}"
            )
    return flags


def pair_flag(label: str, left: int, right: int, limit: int) -> str | None:
    gap = abs(left - right)
    if gap >= limit:
        return f"{label} scores {left} and {right} differ by {gap} (flag at {limit})"
    return None


def repeatability_summary(scores: list[int]) -> dict:
    if not scores:
        return {"runs": [], "min": None, "max": None, "average": None, "range": None}
    return {
        "runs": scores,
        "min": min(scores),
        "max": max(scores),
        "average": round(statistics.fmean(scores), 2),
        "range": max(scores) - min(scores),
    }


def assert_no_document_text(payload: object) -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in DOCUMENT_KEYS:
                raise ValueError(f"Evaluation output must not store '{key}'.")
            assert_no_document_text(value)
    elif isinstance(payload, list):
        for item in payload:
            assert_no_document_text(item)


def _band(score: int) -> str:
    if score <= 20:
        return "0-20"
    if score <= 40:
        return "21-40"
    if score <= 60:
        return "41-60"
    if score <= 80:
        return "61-80"
    return "81-100"


def _band_labels() -> tuple[str, ...]:
    return ("0-20", "21-40", "41-60", "61-80", "81-100")
