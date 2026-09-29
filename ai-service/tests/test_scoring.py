import pytest

from app.config import Settings
from app.services.laya_service import (
    QUESTION_IDS,
    LayaInputError,
    LayaInvalidResponseError,
    LayaService,
    extract_scores,
    state_token_budget,
    weighted_match_score,
)


def _answers(**overrides: float) -> dict:
    scores = {question_id: 0.0 for question_id in QUESTION_IDS}
    scores.update(overrides)
    return {"answers": {question_id: {"score": score} for question_id, score in scores.items()}}


def test_score_normalization_endpoints():
    assert weighted_match_score({question_id: 0 for question_id in QUESTION_IDS}) == 0
    assert weighted_match_score({question_id: 4 for question_id in QUESTION_IDS}) == 100
    assert weighted_match_score({question_id: 2 for question_id in QUESTION_IDS}) == 50


def test_weighted_score_uses_documented_weights():
    scores = {
        "required_skills": 4,       # 1.00 * 0.40 = 0.40
        "experience": 3,            # 0.75 * 0.20 = 0.15
        "responsibilities": 2,      # 0.50 * 0.20 = 0.10
        "preferred_skills": 1,      # 0.25 * 0.10 = 0.025
        "overall_alignment": 0,     # 0
    }
    assert weighted_match_score(scores) == 68


def test_fractional_laya_expected_score_is_weighted():
    scores = {question_id: 0.0 for question_id in QUESTION_IDS}
    scores["required_skills"] = 2.0
    assert weighted_match_score(scores) == 20


def test_invalid_laya_response_shape():
    with pytest.raises(LayaInvalidResponseError):
        extract_scores(["not", "an", "object"])
    with pytest.raises(LayaInvalidResponseError):
        extract_scores({"model": "typed-decisions"})
    with pytest.raises(LayaInvalidResponseError):
        extract_scores({"answers": []})


def test_score_out_of_range_is_rejected():
    payload = _answers(required_skills=4.1)
    with pytest.raises(LayaInvalidResponseError, match="outside 0-4"):
        extract_scores(payload)
    with pytest.raises(LayaInvalidResponseError, match="outside 0-4"):
        weighted_match_score({question_id: 0 for question_id in QUESTION_IDS} | {"required_skills": -0.1})


def test_non_numeric_score_is_rejected():
    payload = _answers()
    payload["answers"]["experience"]["score"] = "high"
    with pytest.raises(LayaInvalidResponseError, match="not numeric"):
        extract_scores(payload)


def test_missing_laya_answer_is_rejected():
    payload = _answers()
    del payload["answers"]["responsibilities"]
    with pytest.raises(LayaInvalidResponseError, match="responsibilities"):
        extract_scores(payload)


def test_blank_input_does_not_call_the_model():
    calls = []

    class Router:
        def load(self, name):
            calls.append(("load", name))
            raise AssertionError("blank input must not load Laya")

        def predict(self, state, questions, model=None):
            calls.append("predict")
            raise AssertionError("blank input must not call predict")

    service = LayaService(Settings(), router=Router())
    with pytest.raises(LayaInputError, match="resume must not be blank"):
        service.calculate_match_score("   ", "Backend engineer")
    with pytest.raises(LayaInputError, match="job description must not be blank"):
        service.calculate_match_score("Java developer", "  ")
    assert calls == []


class CharTokenizer:
    def __call__(self, text, add_special_tokens=False):
        return {"input_ids": [ord(character) for character in text]}

    def encode(self, text, add_special_tokens=False):
        return [ord(character) for character in text]


def test_one_predict_call_scores_every_question():
    seen = {}

    class Agent:
        cfg = {"max_len": 1024, "head_max_len": 192}
        tok = CharTokenizer()

    class Router:
        def load(self, name):
            seen["model"] = name
            return Agent()

        def predict(self, state, questions, model=None):
            seen["state"] = state
            seen["questions"] = questions
            seen["predict_model"] = model
            return _answers(**{question_id: 4 for question_id in QUESTION_IDS})

    details = LayaService(Settings(laya_model="typed-decisions"), router=Router()).score(
        "Java developer",
        "Backend engineer",
    )
    assert details.score == 100
    assert seen["predict_model"] == "typed-decisions"
    assert set(seen["questions"]) == set(QUESTION_IDS)
    assert all(question["type"] == "score" for question in seen["questions"].values())
    assert all(len(question["criteria"]) == 5 for question in seen["questions"].values())
    assert seen["state"]["resume"] == "Java developer"
    assert seen["state"]["job_description"] == "Backend engineer"
    assert seen["state"]["resume_role"] == "candidate evidence"
    assert seen["state"]["job_description_role"] == "target requirements"


def test_long_input_is_compacted_and_still_scored():
    seen = {}

    class Agent:
        cfg = {"max_len": 240, "head_max_len": 40}
        tok = CharTokenizer()

    class Router:
        def load(self, name):
            return Agent()

        def predict(self, state, questions, model=None):
            seen["state"] = state
            return _answers()

    service = LayaService(
        Settings(laya_input_token_budget=80, laya_token_safety_margin=0),
        router=Router(),
    )
    details = service.score("Skills\n" + ("Java " * 80), "Requirements\n" + ("Kafka " * 80))
    assert details.compacted
    assert details.final_resume_tokens + details.final_job_description_tokens <= 80
    assert details.state_tokens <= state_token_budget(240, 40)
    assert seen["state"]["resume"]
    assert seen["state"]["job_description"]


def test_state_token_budget_matches_checkpoint_formula():
    assert state_token_budget(1024, 192) == 824
