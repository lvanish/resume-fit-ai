"""Compare Laya noul with a neutral two-option choice on the same requirements.

This does not score matches and does not change REQUIREMENT_MATCHING_ENABLED.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from app.config import Settings
from app.models.candidate_profile import CandidateProfile
from app.services.laya_service import LayaInferenceError, LayaInvalidResponseError, _predict_lock, _shared_router

MATCH = "MATCH"
NO_MATCH = "NO_MATCH"
SUPPORT = "the candidate evidence supports the requirement"
REJECT = "the candidate evidence does not support the requirement"
NOUL_THRESHOLD = 0.5


@dataclass(frozen=True)
class DecisionCase:
    test_id: str
    candidate: CandidateProfile
    requirement: str
    expected: str
    group: str


def noul_question(requirement: str) -> dict:
    return {
        "type": "noul",
        "instructions": _instruction(requirement),
        "criteria": {"false": REJECT, "true": SUPPORT},
    }


def choice_question(requirement: str, *, swapped: bool = False) -> dict:
    """Neutral labels A and B. Swapped keeps the same meanings on the opposite labels."""
    criteria = {"A": REJECT, "B": SUPPORT} if swapped else {"A": SUPPORT, "B": REJECT}
    return {
        "type": "choice",
        "instructions": _instruction(requirement),
        "criteria": criteria,
    }


def noul_decision(probability: float) -> str:
    return MATCH if probability >= NOUL_THRESHOLD else NO_MATCH


def choice_decision(selected: str, criteria: dict[str, str]) -> str:
    meaning = criteria.get(selected)
    if meaning == SUPPORT:
        return MATCH
    if meaning == REJECT:
        return NO_MATCH
    return "INVALID"


def confusion_matrix(expected: list[str], predicted: list[str]) -> dict[str, dict[str, int]]:
    matrix = {MATCH: {MATCH: 0, NO_MATCH: 0}, NO_MATCH: {MATCH: 0, NO_MATCH: 0}}
    for truth, guess in zip(expected, predicted, strict=True):
        column = guess if guess in (MATCH, NO_MATCH) else NO_MATCH
        if truth in matrix:
            matrix[truth][column] += 1
    return matrix


def summarize(rows: list[dict]) -> dict:
    expected = [row["expected"] for row in rows]
    noul_predicted = [row["noul_result"] for row in rows]
    choice_predicted = [row["choice_result"] for row in rows]
    return {
        "count": len(rows),
        "noul_accuracy": _accuracy(expected, noul_predicted),
        "choice_accuracy": _accuracy(expected, choice_predicted),
        "noul_false_positives": _count(expected, noul_predicted, truth=NO_MATCH, guess=MATCH),
        "noul_false_negatives": _count(expected, noul_predicted, truth=MATCH, guess=NO_MATCH),
        "choice_false_positives": _count(expected, choice_predicted, truth=NO_MATCH, guess=MATCH),
        "choice_false_negatives": _count(expected, choice_predicted, truth=MATCH, guess=NO_MATCH),
        "noul_confusion": confusion_matrix(expected, noul_predicted),
        "choice_confusion": confusion_matrix(expected, choice_predicted),
        "label_swap_stable": sum(1 for row in rows if row["choice_result"] == row["choice_swapped_result"]),
        "label_swap_changed": sum(1 for row in rows if row["choice_result"] != row["choice_swapped_result"]),
    }


class LayaDecisionBenchmark:
    def __init__(self, settings: Settings, router=None) -> None:
        self._settings = settings
        self._router = router

    def run(self, cases: list[DecisionCase]) -> list[dict]:
        router = self._router if self._router is not None else _shared_router(self._settings)
        model_name = (self._settings.laya_model or "").strip() or "typed-decisions"
        rows = []
        for group in _groups(cases):
            state = _state(group[0].candidate)
            paired = _paired_questions(group)
            paired_answers, paired_ms = _predict(router, state, paired, model_name)
            swapped = _swapped_questions(group)
            swapped_answers, swapped_ms = _predict(router, state, swapped, model_name)
            for case in group:
                noul_answer = paired_answers[_noul_key(case)]
                choice_answer = paired_answers[_choice_key(case)]
                swapped_answer = swapped_answers[_choice_key(case)]
                probability = float(noul_answer["noul"])
                normal_criteria = choice_question(case.requirement)["criteria"]
                swapped_criteria = choice_question(case.requirement, swapped=True)["criteria"]
                rows.append(
                    {
                        "test_id": case.test_id,
                        "group": case.group,
                        "requirement": case.requirement,
                        "expected": case.expected,
                        "noul_result": noul_decision(probability),
                        "noul_probability": probability,
                        "choice_result": choice_decision(str(choice_answer.get("choice")), normal_criteria),
                        "choice_swapped_result": choice_decision(str(swapped_answer.get("choice")), swapped_criteria),
                        "elapsed_ms": round(paired_ms, 1),
                        "swap_elapsed_ms": round(swapped_ms, 1),
                    }
                )
        return rows


def controlled_cases() -> list[DecisionCase]:
    java_profile = CandidateProfile(skills=["Java", "Spring Boot", "PostgreSQL"])
    react_profile = CandidateProfile(skills=["React", "TypeScript"])
    backend_work = CandidateProfile(responsibilities=["Built backend REST APIs using Spring Boot"])
    react_work = CandidateProfile(responsibilities=["Built React user interfaces"])
    software_role = CandidateProfile(role="Software Engineer")
    return [
        DecisionCase("java-explicit", java_profile, "Java", MATCH, "controlled"),
        DecisionCase("java-profile-kafka", java_profile, "Kafka", NO_MATCH, "controlled"),
        DecisionCase("react-explicit", react_profile, "React", MATCH, "controlled"),
        DecisionCase("react-profile-spring", react_profile, "Spring Boot", NO_MATCH, "controlled"),
        DecisionCase("backend-services", backend_work, "Develop backend services", MATCH, "controlled"),
        DecisionCase("react-work-backend", react_work, "Develop backend services", NO_MATCH, "controlled"),
        DecisionCase("role-software", software_role, "Software Engineer", MATCH, "controlled"),
        DecisionCase("role-relationship-manager", software_role, "Relationship Manager", NO_MATCH, "controlled"),
        DecisionCase("rabbitmq-not-kafka", CandidateProfile(skills=["RabbitMQ"]), "Kafka", NO_MATCH, "controlled"),
        DecisionCase(
            "event-driven-not-kafka",
            CandidateProfile(responsibilities=["Built event-driven services"]),
            "Kafka experience",
            NO_MATCH,
            "controlled",
        ),
        DecisionCase("java-profile-postgresql", java_profile, "PostgreSQL", MATCH, "controlled"),
        DecisionCase("react-profile-java", react_profile, "Java", NO_MATCH, "controlled"),
        DecisionCase(
            "frontend-role-backend",
            CandidateProfile(role="Frontend Engineer"),
            "Backend Engineer",
            NO_MATCH,
            "controlled",
        ),
        DecisionCase("rest-apis", backend_work, "Build REST APIs", MATCH, "controlled"),
        DecisionCase("java-not-spring", CandidateProfile(skills=["Java"]), "Spring Boot", NO_MATCH, "controlled"),
    ]


def relationship_manager_cases() -> list[DecisionCase]:
    candidate = CandidateProfile(
        role="Full-stack engineer",
        years_of_experience=3,
        skills=[
            "React",
            "TypeScript",
            "Spring Boot",
            "Java",
            "MySQL",
            "Kafka",
            "RabbitMQ",
            "Redis",
            "Docker",
            "Azure",
            "AWS",
            "Kubernetes",
            "LangChain",
            "LangGraph",
            "RAG retrieval",
            "PostgreSQL",
        ],
        responsibilities=[
            "Built an agentic assistant using LangChain, LangGraph and LLMs over fintech policy and product documents, with RAG retrieval and multi-step tool calling.",
            "Worked with React, Spring Boot, MySQL, Kafka, RabbitMQ, GraphQL, Redis, Docker, Azure, AWS, Kubernetes, CI/CD, JUnit, Mockito, Prometheus and Grafana.",
            "Built the TDM Admin Tool using React, Spring Boot, PostgreSQL and SQLite.",
        ],
    )
    requirements = [
        "Customer Relationships",
        "Loans",
        "LOS",
        "Relationship Manager",
        "Data Entry",
        "Customer Queries",
        "Village surveys",
        "Customer sourcing",
        "Collections",
        "Recoveries",
    ]
    return [
        DecisionCase(f"rm-{index}", candidate, name, NO_MATCH, "relationship-manager")
        for index, name in enumerate(requirements, start=1)
    ]


def strong_backend_cases() -> list[DecisionCase]:
    candidate = CandidateProfile(
        role="Backend Engineer",
        skills=["Java", "Spring Boot", "PostgreSQL", "Kafka", "Docker"],
        responsibilities=["Built REST APIs", "Built backend services", "Worked with event-driven systems"],
    )
    return [
        DecisionCase(f"backend-{name}", candidate, name, MATCH, "strong-backend")
        for name in ["Java", "Spring Boot", "PostgreSQL", "Kafka", "REST APIs"]
    ]


def format_confusion(title: str, matrix: dict[str, dict[str, int]]) -> str:
    match_row = matrix[MATCH]
    miss_row = matrix[NO_MATCH]
    return (
        f"{title}\n"
        "                     predicted MATCH    predicted NO_MATCH\n"
        f"expected MATCH       {match_row[MATCH]:<18} {match_row[NO_MATCH]}\n"
        f"expected NO_MATCH    {miss_row[MATCH]:<18} {miss_row[NO_MATCH]}"
    )


def _instruction(requirement: str) -> str:
    return (
        f"Does the candidate profile explicitly support this requirement: '{requirement}'? "
        "Use only the candidate profile. "
        "Do not infer a related technology. "
        "Insufficient evidence means the requirement is not supported."
    )


def _state(candidate: CandidateProfile) -> dict:
    return {
        "role": candidate.role,
        "years_of_experience": candidate.years_of_experience,
        "skills": list(candidate.skills),
        "responsibilities": list(candidate.responsibilities),
    }


def _groups(cases: list[DecisionCase]) -> list[list[DecisionCase]]:
    groups: list[list[DecisionCase]] = []
    index: dict[tuple, int] = {}
    for case in cases:
        key = (
            case.candidate.role,
            case.candidate.years_of_experience,
            tuple(case.candidate.skills),
            tuple(case.candidate.responsibilities),
        )
        if key not in index:
            index[key] = len(groups)
            groups.append([])
        groups[index[key]].append(case)
    return groups


def _paired_questions(cases: list[DecisionCase]) -> dict[str, dict]:
    questions = {}
    for case in cases:
        questions[_noul_key(case)] = noul_question(case.requirement)
        questions[_choice_key(case)] = choice_question(case.requirement)
    return questions


def _swapped_questions(cases: list[DecisionCase]) -> dict[str, dict]:
    return {_choice_key(case): choice_question(case.requirement, swapped=True) for case in cases}


def _noul_key(case: DecisionCase) -> str:
    return f"noul_{case.test_id}"


def _choice_key(case: DecisionCase) -> str:
    return f"choice_{case.test_id}"


def _predict(router, state: dict, questions: dict, model_name: str) -> tuple[dict, float]:
    started = time.perf_counter()
    try:
        with _predict_lock:
            result = router.predict(state, questions, model=model_name)
    except (LayaInferenceError, LayaInvalidResponseError):
        raise
    except Exception as exc:
        raise LayaInferenceError("Laya could not answer the decision benchmark.") from exc
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    if not isinstance(result, dict) or not isinstance(result.get("answers"), dict):
        raise LayaInvalidResponseError("Laya decision benchmark response is missing answers.")
    return result["answers"], elapsed_ms


def _accuracy(expected: list[str], predicted: list[str]) -> float:
    if not expected:
        return 0.0
    correct = sum(1 for truth, guess in zip(expected, predicted, strict=True) if truth == guess)
    return correct / len(expected)


def _count(expected: list[str], predicted: list[str], *, truth: str, guess: str) -> int:
    return sum(
        1
        for expected_label, predicted_label in zip(expected, predicted, strict=True)
        if expected_label == truth and predicted_label == guess
    )
