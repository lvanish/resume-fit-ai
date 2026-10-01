"""Requirement-level Laya decisions and the deterministic Match Score.

Experience is not sent to Laya. Every other requirement is a question in as few
Router.predict calls as the checkpoint allows. The public API never returns this detail.
"""

from __future__ import annotations

import logging
import time

from app.config import Settings
from app.models.candidate_profile import CandidateProfile
from app.models.job_profile import JobProfile
from app.models.requirement import Requirement, RequirementCategory
from app.models.requirement_match import RequirementMatchAnalysis, RequirementMatchResult
from app.services.experience_score import calculate_experience_score
from app.services.laya_service import (
    LayaInferenceError,
    LayaInitializationError,
    LayaInvalidResponseError,
    _checkpoint_limits,
    _predict_lock,
    _shared_router,
)
from app.services.requirement_questions import (
    build_questions,
    candidate_state,
    laya_requirements,
    plan_batches,
)
from app.services.requirement_score import RequirementWeights, aggregate_match_score, average_or_neutral

logger = logging.getLogger(__name__)

_ROLE_SCORES = {"MATCH": 1.0, "PARTIAL_MATCH": 0.5, "NO_MATCH": 0.0}


class RequirementMatchingService:
    def __init__(self, settings: Settings, router=None) -> None:
        self._settings = settings
        self._router = router

    def match(
        self,
        candidate: CandidateProfile,
        job: JobProfile,
        requirements: list[Requirement],
    ) -> RequirementMatchAnalysis:
        weights = _weights(self._settings)
        experience = calculate_experience_score(candidate.years_of_experience, job.minimum_years_experience)
        ordered = laya_requirements(requirements)
        try:
            questions = build_questions(requirements, job.role)
        except Exception as exc:
            logger.exception(
                "requirement_matching_failed stage=laya_question_creation exception_type=%s message=%s",
                type(exc).__name__,
                exc,
            )
            raise
        logger.info("requirement_questions_created count=%s", len(questions))
        state = candidate_state(
            candidate.role,
            candidate.years_of_experience,
            candidate.skills,
            candidate.responsibilities,
        )
        router = self._router if self._router is not None else _shared_router(self._settings)
        model_name = (self._settings.laya_model or "").strip() or "typed-decisions"
        try:
            agent = router.load(model_name)
        except LayaInitializationError:
            raise
        except Exception as exc:
            logger.exception("Laya checkpoint failed to load")
            raise LayaInitializationError(
                "The Laya model could not be loaded. Check network access to the typed-decisions checkpoint and try again."
            ) from exc
        max_len, head_max_len = _checkpoint_limits(agent)
        batches = plan_batches(questions, self._settings.requirement_questions_per_batch)
        logger.info(
            "requirement_match requirements=%s laya_questions=%s batches=%s max_len=%s head_max_len=%s",
            len(requirements),
            len(questions),
            len(batches),
            max_len,
            head_max_len,
        )

        answers: dict[str, dict] = {}
        batch_latency: list[float] = []
        started = time.perf_counter()
        logger.info("requirement_laya_started count=%s", len(questions))
        for batch in batches:
            batch_started = time.perf_counter()
            try:
                with _predict_lock:
                    result = router.predict(state, batch, model=model_name)
            except (LayaInferenceError, LayaInvalidResponseError):
                raise
            except Exception as exc:
                logger.exception(
                    "requirement_matching_failed stage=laya_prediction exception_type=%s message=%s",
                    type(exc).__name__,
                    exc,
                )
                raise LayaInferenceError("Laya could not answer the requirement questions.") from exc
            batch_ms = (time.perf_counter() - batch_started) * 1000.0
            batch_latency.append(batch_ms)
            answers.update(_answers(result))
            logger.info("requirement_batch questions=%s latency_ms=%.0f", len(batch), batch_ms)
        total_ms = (time.perf_counter() - started) * 1000.0
        logger.info("requirement_laya_completed")

        try:
            results = _results(ordered, questions, answers)
        except Exception as exc:
            logger.exception(
                "requirement_matching_failed stage=laya_result_parsing exception_type=%s message=%s",
                type(exc).__name__,
                exc,
            )
            raise
        logger.info("requirement_results_parsed count=%s", len(results))
        required_probs = _probabilities(results, RequirementCategory.REQUIRED_SKILL)
        preferred_probs = _probabilities(results, RequirementCategory.PREFERRED_SKILL)
        responsibility_probs = _probabilities(results, RequirementCategory.RESPONSIBILITY)
        role_score = _role_score(results)
        required_score = average_or_neutral(required_probs)
        preferred_score = average_or_neutral(preferred_probs)
        responsibility_score = average_or_neutral(responsibility_probs)
        try:
            final_score = aggregate_match_score(
                required_skill_score=required_score,
                responsibility_score=responsibility_score,
                experience_score=experience,
                role_score=role_score,
                preferred_skill_score=preferred_score,
                weights=weights,
            )
        except Exception as exc:
            logger.exception(
                "requirement_matching_failed stage=score_aggregation exception_type=%s message=%s",
                type(exc).__name__,
                exc,
            )
            raise
        logger.info("score_calculation_completed score=%s", final_score)
        experience_result = RequirementMatchResult(
            requirement=_experience_label(job.minimum_years_experience),
            category=RequirementCategory.EXPERIENCE,
            probability_yes=experience,
            decision="deterministic",
        )
        logger.info(
            "requirement_match final_score=%s required_skill_score=%.4f preferred_skill_score=%.4f "
            "responsibility_score=%.4f experience_score=%.4f role_score=%.4f batches=%s total_latency_ms=%.0f",
            final_score,
            required_score,
            preferred_score,
            responsibility_score,
            experience,
            role_score,
            len(batches),
            total_ms,
        )
        return RequirementMatchAnalysis(
            required_skill_score=required_score,
            preferred_skill_score=preferred_score,
            responsibility_score=responsibility_score,
            experience_score=experience,
            role_score=role_score,
            final_score=final_score,
            requirements=[*results, experience_result],
            batch_count=len(batches),
            batch_latency_ms=[round(value, 1) for value in batch_latency],
            total_latency_ms=round(total_ms, 1),
        )


def _weights(settings: Settings) -> RequirementWeights:
    return RequirementWeights(
        required_skills=settings.requirement_weight_required_skills,
        responsibilities=settings.requirement_weight_responsibilities,
        experience=settings.requirement_weight_experience,
        role=settings.requirement_weight_role,
        preferred_skills=settings.requirement_weight_preferred_skills,
    )


def _answers(result: object) -> dict[str, dict]:
    if not isinstance(result, dict):
        raise LayaInvalidResponseError("Laya returned a response that is not an object.")
    answers = result.get("answers")
    if not isinstance(answers, dict):
        raise LayaInvalidResponseError("Laya response is missing the answers object.")
    return answers


def _results(ordered: list[Requirement], questions: dict[str, dict], answers: dict[str, dict]) -> list[RequirementMatchResult]:
    results: list[RequirementMatchResult] = []
    for requirement, key in zip(ordered, questions, strict=True):
        answer = answers.get(key)
        if not isinstance(answer, dict):
            raise LayaInvalidResponseError(f"Laya response is missing the '{key}' answer.")
        if requirement.category == RequirementCategory.ROLE:
            decision = str(answer.get("choice") or "")
            results.append(
                RequirementMatchResult(
                    requirement=requirement.name,
                    category=requirement.category,
                    probability_yes=_ROLE_SCORES.get(decision),
                    decision=decision or None,
                )
            )
            continue
        if "noul" not in answer:
            raise LayaInvalidResponseError(f"Laya response is missing the noul probability for '{key}'.")
        probability = answer["noul"]
        if isinstance(probability, bool) or not isinstance(probability, (int, float)):
            raise LayaInvalidResponseError(f"Laya noul probability for '{key}' is not numeric.")
        value = float(probability)
        if value < 0 or value > 1:
            raise LayaInvalidResponseError(f"Laya noul probability for '{key}' is outside 0-1.")
        results.append(
            RequirementMatchResult(
                requirement=requirement.name,
                category=requirement.category,
                probability_yes=value,
            )
        )
    return results


def _probabilities(results: list[RequirementMatchResult], category: RequirementCategory) -> list[float]:
    values = []
    for result in results:
        if result.category == category and result.probability_yes is not None:
            values.append(result.probability_yes)
    return values


def _role_score(results: list[RequirementMatchResult]) -> float:
    scores = [
        result.probability_yes
        for result in results
        if result.category == RequirementCategory.ROLE and result.probability_yes is not None
    ]
    if not scores:
        return 0.5
    return sum(scores) / len(scores)


def _experience_label(required_years: float | None) -> str:
    if required_years is None:
        return "experience not stated"
    shown = str(int(required_years)) if float(required_years).is_integer() else str(required_years)
    return f"minimum {shown} years"
