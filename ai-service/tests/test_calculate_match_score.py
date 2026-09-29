import pytest

from app.services.scoring import MatchAnalysis, calculate_match_score, match_analysis


def test_all_zeros_score_zero():
    assert calculate_match_score(0, 0, 0, 0, 0) == 0


def test_all_fours_score_one_hundred():
    assert calculate_match_score(4, 4, 4, 4, 4) == 100


def test_each_boundary_weight():
    assert calculate_match_score(4, 0, 0, 0, 0) == 40
    assert calculate_match_score(0, 4, 0, 0, 0) == 20
    assert calculate_match_score(0, 0, 4, 0, 0) == 20
    assert calculate_match_score(0, 0, 0, 4, 0) == 10
    assert calculate_match_score(0, 0, 0, 0, 4) == 10
    assert calculate_match_score(0, 0, 0, 0, 0) == 0
    assert calculate_match_score(4, 4, 4, 4, 4) == 100


def test_midpoint_levels_score_fifty():
    assert calculate_match_score(2, 2, 2, 2, 2) == 50


def test_decimal_expected_values_match_the_documented_example():
    # 3.1243, 3.3289, 3.164, 3.0774, 3.3072 weight to 79.669 and round to 80.
    assert calculate_match_score(3.1243, 3.3289, 3.164, 3.0774, 3.3072) == 80


def test_half_point_uses_half_to_even_rounding():
    # Every dimension at 2.5 is 62.5 on the 0-100 scale. round() goes to 62.
    assert calculate_match_score(2.5, 2.5, 2.5, 2.5, 2.5) == 62


def test_values_outside_zero_to_four_are_rejected():
    with pytest.raises(ValueError, match="outside 0-4"):
        calculate_match_score(-0.01, 0, 0, 0, 0)
    with pytest.raises(ValueError, match="outside 0-4"):
        calculate_match_score(4.01, 0, 0, 0, 0)


def test_non_numeric_values_are_rejected():
    with pytest.raises(ValueError, match="not numeric"):
        calculate_match_score(True, 0, 0, 0, 0)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="not numeric"):
        calculate_match_score("3", 0, 0, 0, 0)  # type: ignore[arg-type]


def test_analysis_object_carries_dimensions_and_final_score():
    analysis = match_analysis(
        {
            "required_skills": 3.12,
            "experience": 3.33,
            "responsibilities": 3.16,
            "preferred_skills": 3.08,
            "overall_alignment": 3.31,
        }
    )
    assert isinstance(analysis, MatchAnalysis)
    payload = analysis.as_dict()
    assert payload["final_score"] == calculate_match_score(3.12, 3.33, 3.16, 3.08, 3.31)
    assert set(payload) == {
        "required_skills",
        "experience",
        "responsibilities",
        "preferred_skills",
        "overall_alignment",
        "final_score",
    }
    assert "resume" not in payload
