import pytest

from app.config import Settings
from app.models.analyze import AnalyzeResponse
from app.models.candidate_profile import CandidateProfile
from app.models.job_profile import JobProfile
from app.models.requirement import Requirement, RequirementCategory
from app.services.experience_score import calculate_experience_score
from app.services.laya_service import BroadLayaScoringService
from app.services.match_scoring import public_match_score
from app.services.requirement_builder import build_requirements
from app.services.requirement_matching_service import RequirementMatchingService
from app.services.requirement_questions import build_questions, laya_requirements, plan_batches
from app.services.requirement_score import RequirementWeights, aggregate_match_score


class _Agent:
    cfg = {"max_len": 1024, "head_max_len": 256}


class _Router:
    def __init__(self, answers_for):
        self.answers_for = answers_for
        self.calls = []

    def load(self, model):
        return _Agent()

    def predict(self, state, questions, model=None):
        self.calls.append(list(questions))
        assert "resume" not in state
        assert "job_description" not in state
        answers = {}
        for key, spec in questions.items():
            answers[key] = self.answers_for(key, spec)
        return {"answers": answers}


def test_experience_score_uses_the_stated_gaps_and_does_not_invent_years():
    assert calculate_experience_score(None, 4) == 0.5
    assert calculate_experience_score(4, None) == 0.5
    assert calculate_experience_score(4, 4) == 1.0
    assert calculate_experience_score(5, 4) == 1.0
    assert calculate_experience_score(3.2, 4) == 0.7
    assert calculate_experience_score(3, 4) == 0.4
    assert calculate_experience_score(2, 4) == 0.4
    assert calculate_experience_score(1.9, 4) == 0.15


def test_required_skill_weight_separates_high_and_low_evidence():
    weights = RequirementWeights()
    strong = aggregate_match_score(
        required_skill_score=0.9,
        responsibility_score=0.8,
        experience_score=1.0,
        role_score=1.0,
        preferred_skill_score=0.8,
        weights=weights,
    )
    frontend = aggregate_match_score(
        required_skill_score=0.1,
        responsibility_score=0.2,
        experience_score=1.0,
        role_score=0.0,
        preferred_skill_score=0.1,
        weights=weights,
    )
    assert strong > frontend


def test_questions_skip_experience_and_batch_in_category_order():
    requirements = [
        Requirement(name="Source new customers", category=RequirementCategory.RESPONSIBILITY),
        Requirement(name="Kafka", category=RequirementCategory.PREFERRED_SKILL),
        Requirement(name="Java", category=RequirementCategory.REQUIRED_SKILL),
        Requirement(name="Backend Engineer", category=RequirementCategory.ROLE),
        Requirement(name="minimum 4 years", category=RequirementCategory.EXPERIENCE),
    ]
    ordered = laya_requirements(requirements)
    assert [item.category for item in ordered] == [
        RequirementCategory.REQUIRED_SKILL,
        RequirementCategory.PREFERRED_SKILL,
        RequirementCategory.RESPONSIBILITY,
        RequirementCategory.ROLE,
    ]
    questions = build_questions(requirements, "Backend Engineer")
    assert all(spec["type"] == "noul" for key, spec in questions.items() if not key.startswith("role_"))
    assert next(spec["type"] for key, spec in questions.items() if key.startswith("role_")) == "choice"
    batches = plan_batches(questions, 2)
    assert len(batches) == 2
    assert list(batches[0])[0].startswith("required_skill_")
    assert "minimum 4 years" not in questions


def test_matching_keeps_continuous_probabilities_and_batches_calls():
    def answers_for(key, spec):
        if spec["type"] == "choice":
            return {"type": "choice", "choice": "NO_MATCH"}
        if "java" in key:
            return {"type": "noul", "noul": 0.94}
        return {"type": "noul", "noul": 0.08}

    router = _Router(answers_for)
    job = JobProfile(
        role="Backend Engineer",
        minimum_years_experience=4,
        required_skills=["Java", "Spring Boot"],
        preferred_skills=[],
        responsibilities=["Build backend services."],
    )
    analysis = RequirementMatchingService(
        Settings(requirement_questions_per_batch=2),
        router=router,
    ).match(
        CandidateProfile(role="Backend Engineer", years_of_experience=6, skills=["Java"], responsibilities=[]),
        job,
        build_requirements(job),
    )
    assert len(router.calls) == 2
    java = next(item for item in analysis.requirements if item.requirement == "Java")
    spring = next(item for item in analysis.requirements if item.requirement == "Spring Boot")
    assert java.probability_yes == 0.94
    assert spring.probability_yes == 0.08
    assert analysis.required_skill_score == pytest.approx(0.51)
    assert analysis.role_score == 0.0
    assert analysis.experience_score == 1.0
    assert analysis.preferred_skill_score == 0.5
    assert "score" in AnalyzeResponse(score=analysis.final_score).model_dump()
    assert set(AnalyzeResponse.model_fields) == {"score"}


def test_missing_role_decision_stays_neutral():
    def answers_for(key, spec):
        if spec["type"] == "choice":
            return {"type": "choice", "choice": "UNSURE"}
        return {"type": "noul", "noul": 0.2}

    job = JobProfile(role="Relationship Manager", required_skills=["Compliance"])
    analysis = RequirementMatchingService(Settings(), router=_Router(answers_for)).match(
        CandidateProfile(role="Full-stack engineer", skills=["Java"]),
        job,
        build_requirements(job),
    )
    assert analysis.role_score == 0.5
    assert analysis.batch_count == 1


def test_public_flag_selects_the_scorer(monkeypatch):
    monkeypatch.setattr("app.services.match_scoring.score_requirement_match", lambda settings, resume, job: 41)
    monkeypatch.setattr(BroadLayaScoringService, "calculate_match_score", lambda self, resume, job: 80)
    assert public_match_score(Settings(requirement_matching_enabled=True), "resume", "job") == 41
    assert public_match_score(Settings(requirement_matching_enabled=False), "resume", "job") == 80
