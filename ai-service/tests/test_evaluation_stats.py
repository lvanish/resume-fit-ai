import json
from pathlib import Path

import pytest

from evaluation.stats import (
    CATEGORIES,
    assert_no_document_text,
    band_counts,
    category_summary,
    dimension_averages,
    monotonicity_flags,
    pair_flag,
    repeatability_summary,
    score_distribution,
    separation_flags,
)

DATASET_PATH = Path(__file__).resolve().parents[1] / "evaluation" / "dataset.json"


def test_dataset_has_fifteen_labeled_synthetic_cases():
    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    assert len(dataset) >= 15
    assert {case["expectedCategory"] for case in dataset} == set(CATEGORIES)
    ids = [case["id"] for case in dataset]
    assert len(ids) == len(set(ids))
    for case in dataset:
        assert case["resume"].strip()
        assert case["jobDescription"].strip()
        assert set(case) == {"id", "resume", "jobDescription", "expectedCategory"}


def test_category_summary_and_separation_flag():
    records = [
        {"expectedCategory": "VERY_STRONG", "final_score": 90},
        {"expectedCategory": "VERY_STRONG", "final_score": 80},
        {"expectedCategory": "STRONG", "final_score": 70},
        {"expectedCategory": "MODERATE", "final_score": 55},
        {"expectedCategory": "WEAK", "final_score": 40},
        {"expectedCategory": "VERY_WEAK", "final_score": 15},
    ]
    rows = category_summary(records)
    assert rows[0]["category"] == "VERY_STRONG"
    assert rows[0]["min"] == 80
    assert rows[0]["max"] == 90
    assert rows[0]["average"] == 85
    assert separation_flags(rows) == []

    collapsed = category_summary(
        [
            {"expectedCategory": "VERY_STRONG", "final_score": 40},
            {"expectedCategory": "WEAK", "final_score": 70},
        ]
    )
    assert separation_flags(collapsed)


def test_distribution_bands_and_dimension_averages():
    distribution = score_distribution([10, 25, 50, 70, 95])
    assert distribution["lowest"] == 10
    assert distribution["highest"] == 95
    assert distribution["median"] == 50
    assert band_counts([0, 20, 21, 40, 41, 60, 61, 80, 81, 100]) == {
        "0-20": 2,
        "21-40": 2,
        "41-60": 2,
        "61-80": 2,
        "81-100": 2,
    }
    averages = dimension_averages(
        [
            {
                "required_skills": 4,
                "experience": 2,
                "responsibilities": 2,
                "preferred_skills": 0,
                "overall_alignment": 0,
            },
            {
                "required_skills": 2,
                "experience": 2,
                "responsibilities": 2,
                "preferred_skills": 2,
                "overall_alignment": 2,
            },
        ]
    )
    assert averages["required_skills"] == 3
    assert averages["experience"] == 2


def test_monotonicity_and_pair_flags():
    series = [
        {"series": "required_skills", "step": "A", "final_score": 40},
        {"series": "required_skills", "step": "B", "final_score": 55},
        {"series": "required_skills", "step": "C", "final_score": 50},
    ]
    flags = monotonicity_flags(series)
    assert len(flags) == 1
    assert "step C" in flags[0]
    assert pair_flag("order", 70, 72, 10) is None
    assert pair_flag("order", 70, 85, 10) is not None


def test_repeatability_summary():
    summary = repeatability_summary([72, 72, 73, 72, 72])
    assert summary["min"] == 72
    assert summary["max"] == 73
    assert summary["range"] == 1
    assert summary["runs"] == [72, 72, 73, 72, 72]


def test_results_payload_rejects_document_text():
    assert_no_document_text({"dataset": [{"id": "case-001", "final_score": 80}]})
    with pytest.raises(ValueError, match="resume"):
        assert_no_document_text({"resume": "secret"})
    with pytest.raises(ValueError, match="jobDescription"):
        assert_no_document_text([{"jobDescription": "secret"}])
