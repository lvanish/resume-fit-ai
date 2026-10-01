from app.config import Settings
from app.models.candidate_profile import CandidateProfile
from app.services.laya_decision_benchmark import (
    DecisionCase,
    LayaDecisionBenchmark,
    choice_question,
    confusion_matrix,
    controlled_cases,
    noul_question,
    summarize,
)


class _Router:
    def __init__(self):
        self.calls = []

    def predict(self, state, questions, model=None):
        self.calls.append(list(questions))
        answers = {}
        for key, spec in questions.items():
            if spec["type"] == "noul":
                probability = 0.9 if "Java" in spec["instructions"] else 0.1
                answers[key] = {"type": "noul", "noul": probability}
            else:
                support_label = next(label for label, text in spec["criteria"].items() if "supports the requirement" in text and "does not" not in text)
                answers[key] = {"type": "choice", "choice": support_label if "Java" in spec["instructions"] else _reject_label(spec)}
        return {"answers": answers}


def _reject_label(spec: dict) -> str:
    return next(label for label, text in spec["criteria"].items() if text.startswith("the candidate evidence does not"))


def test_choice_uses_neutral_labels_and_swap_keeps_meanings():
    normal = choice_question("Java")
    swapped = choice_question("Java", swapped=True)
    assert list(normal["criteria"]) == ["A", "B"]
    assert "YES" not in normal["criteria"]
    assert "NO" not in normal["criteria"]
    assert normal["criteria"]["A"].startswith("the candidate evidence supports")
    assert swapped["criteria"]["A"].startswith("the candidate evidence does not")
    assert swapped["criteria"]["B"].startswith("the candidate evidence supports")
    assert noul_question("Java")["type"] == "noul"
    assert Settings().requirement_matching_enabled is False


def test_benchmark_metrics_and_confusion_ignore_candidate_text():
    cases = [
        DecisionCase("java", CandidateProfile(skills=["Java"]), "Java", "MATCH", "controlled"),
        DecisionCase("kafka", CandidateProfile(skills=["Java"]), "Kafka", "NO_MATCH", "controlled"),
    ]
    router = _Router()
    rows = LayaDecisionBenchmark(Settings(), router=router).run(cases)
    assert len(router.calls) == 2
    summary = summarize(rows)
    assert summary["noul_accuracy"] == 1
    assert summary["choice_accuracy"] == 1
    assert summary["noul_false_positives"] == 0
    assert summary["label_swap_changed"] == 0
    assert "skills" not in rows[0]
    matrix = confusion_matrix(["MATCH", "NO_MATCH"], ["MATCH", "NO_MATCH"])
    assert matrix["MATCH"]["MATCH"] == 1
    assert matrix["NO_MATCH"]["NO_MATCH"] == 1
    assert len(controlled_cases()) >= 10
