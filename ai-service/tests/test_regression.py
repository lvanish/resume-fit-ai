import json
from pathlib import Path

from app.config import Settings
from app.services.laya_service import QUESTION_IDS, LayaService
from app.services.scoring import DIMENSIONS

SMOKE_PATH = Path(__file__).resolve().parents[1] / "evaluation" / "smoke_case.json"


def test_smoke_case_file_is_present():
    smoke = json.loads(SMOKE_PATH.read_text(encoding="utf-8"))
    assert smoke["id"] == "smoke-backend-java"
    assert "Java" in smoke["resume"]
    assert "Spring Boot" in smoke["jobDescription"]


def test_smoke_case_returns_a_valid_internal_analysis():
    smoke = json.loads(SMOKE_PATH.read_text(encoding="utf-8"))
    seen = {}

    class Agent:
        cfg = {"max_len": 1024, "head_max_len": 256}
        tok = _Tokenizer()

    class Router:
        def load(self, name):
            seen["model"] = name
            return Agent()

        def predict(self, state, questions, model=None):
            seen["called"] = True
            return {
                "answers": {
                    question_id: {"score": 2.5}
                    for question_id in QUESTION_IDS
                }
            }

    details = LayaService(Settings(), router=Router()).score(smoke["resume"], smoke["jobDescription"])
    assert seen["called"] is True
    assert isinstance(details.score, int)
    assert 0 <= details.score <= 100
    assert details.score == details.analysis.final_score
    payload = details.analysis.as_dict()
    assert set(payload) == set(DIMENSIONS) | {"final_score"}
    for name in DIMENSIONS:
        assert 0 <= payload[name] <= 4
    assert "resume" not in payload
    assert "jobDescription" not in payload
    assert details.state_tokens <= details.state_token_budget


class _Tokenizer:
    def __call__(self, text, add_special_tokens=False):
        return {"input_ids": [ord(character) for character in text]}

    def encode(self, text, add_special_tokens=False):
        return [ord(character) for character in text]
