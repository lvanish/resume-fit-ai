"""Laya match scoring.

The public API returns one integer Match Score. The five question scores stay
inside this module and are not part of the HTTP response.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass

from app.config import Settings
from app.services.input_preprocessor import InputPreprocessor
from app.services.llm_service import ExtractionError, LLMService
from app.services.profile_extraction_service import ProfileExtractionService
from app.services.profile_text import render_candidate_profile, render_job_profile
from app.services.scoring import (
    DIMENSIONS as QUESTION_IDS,
    MAX_LEVEL,
    MIN_LEVEL,
    WEIGHTS,
    MatchAnalysis,
    calculate_match_score,
    match_analysis,
)
from app.services.token_utils import count_tokens

logger = logging.getLogger(__name__)

MODEL_NAME = "typed-decisions"
# Agent.predict_long documents this as the state tokens that fit beside a full question head.
_STATE_TOKEN_OVERHEAD = 8

_router = None
_router_revision: str | None = None
_router_lock = threading.Lock()
_predict_lock = threading.Lock()


class LayaServiceError(Exception):
    """Base error for scoring failures. Never carries a substitute score."""


class LayaInputError(LayaServiceError):
    """The resume or job description cannot be scored as submitted."""


class LayaInitializationError(LayaServiceError):
    """The typed-decisions checkpoint could not be loaded."""


class LayaInferenceError(LayaServiceError):
    """Laya failed while answering the score questions."""


class LayaInvalidResponseError(LayaServiceError):
    """Laya returned a payload that does not contain five valid scores."""


@dataclass(frozen=True)
class MatchScoreDetails:
    """Internal scoring result. Only `score` is returned by the HTTP API."""

    score: int
    analysis: MatchAnalysis
    answers: dict[str, float]
    model: str
    elapsed_ms: float
    max_len: int
    head_max_len: int
    state_tokens: int
    state_token_budget: int
    original_resume_tokens: int
    original_job_description_tokens: int
    final_resume_tokens: int
    final_job_description_tokens: int
    compacted: bool


def score_questions() -> dict[str, dict]:
    """The five ordinal score questions, answered together in one predict call."""
    return {
        "required_skills": {
            "type": "score",
            "instructions": (
                "The state field 'resume' is candidate evidence. "
                "The state field 'job_description' is the target role's requirements. "
                "How strongly does the candidate's demonstrated technical skill set match "
                "the requirements explicitly required by the job description?"
            ),
            "criteria": [
                "Almost none of the explicitly required skills are demonstrated.",
                "A small portion of the explicitly required skills are demonstrated.",
                "A moderate portion of the explicitly required skills are demonstrated.",
                "Most of the explicitly required skills are demonstrated.",
                "Nearly all of the explicitly required skills are clearly demonstrated.",
            ],
        },
        "experience": {
            "type": "score",
            "instructions": (
                "The state field 'resume' is candidate evidence. "
                "The state field 'job_description' is the target role's requirements. "
                "How well does the candidate's demonstrated professional experience satisfy "
                "the experience requirements of the job description?"
            ),
            "criteria": [
                "Experience requirements are not satisfied and there is little relevant experience.",
                "Experience is substantially below or only weakly relevant to the requirement.",
                "Experience is partially aligned with the requirement.",
                "Experience substantially satisfies the requirement.",
                "Experience clearly satisfies or exceeds the requirement.",
            ],
        },
        "responsibilities": {
            "type": "score",
            "instructions": (
                "The state field 'resume' is candidate evidence. "
                "The state field 'job_description' is the target role's requirements. "
                "How closely does the candidate's demonstrated work align with the "
                "responsibilities described in the job description?"
            ),
            "criteria": [
                "The demonstrated work is largely unrelated to the responsibilities.",
                "Only limited responsibility overlap is evident.",
                "There is meaningful but incomplete responsibility overlap.",
                "Most responsibilities have relevant evidence.",
                "The demonstrated responsibilities closely align with the role.",
            ],
        },
        "preferred_skills": {
            "type": "score",
            "instructions": (
                "The state field 'resume' is candidate evidence. "
                "The state field 'job_description' is the target role's requirements. "
                "How strongly does the candidate's demonstrated skills align with additional "
                "preferred or nice-to-have requirements in the job description? "
                "If the job description contains no preferred or nice-to-have requirements, "
                "assign the middle score (2) instead of treating that absence as a deficiency."
            ),
            "criteria": [
                "Almost none of the preferred requirements are demonstrated.",
                "A small portion of preferred requirements are demonstrated.",
                "Some preferred requirements are demonstrated.",
                "Most preferred requirements are demonstrated.",
                "Nearly all preferred requirements are demonstrated.",
            ],
        },
        "overall_alignment": {
            "type": "score",
            "instructions": (
                "The state field 'resume' is candidate evidence. "
                "The state field 'job_description' is the target role. "
                "Considering the resume as evidence and the job description as the target role, "
                "how strong is the candidate's overall qualification alignment?"
            ),
            "criteria": [
                "Very poor overall alignment.",
                "Weak overall alignment.",
                "Moderate overall alignment.",
                "Strong overall alignment.",
                "Very strong overall alignment.",
            ],
        },
    }


def build_state(resume: str, job_description: str) -> dict[str, str]:
    return {
        "resume_role": "candidate evidence",
        "job_description_role": "target requirements",
        "resume": resume,
        "job_description": job_description,
    }


def extract_scores(result: object) -> dict[str, float]:
    """Read the five score answers. Raise if any answer is missing or out of range."""
    if not isinstance(result, dict):
        raise LayaInvalidResponseError("Laya returned a response that is not an object.")
    answers = result.get("answers")
    if not isinstance(answers, dict):
        raise LayaInvalidResponseError("Laya response is missing the answers object.")

    scores: dict[str, float] = {}
    for question_id in QUESTION_IDS:
        answer = answers.get(question_id)
        if not isinstance(answer, dict) or "score" not in answer:
            raise LayaInvalidResponseError(
                f"Laya response is missing the '{question_id}' score."
            )
        raw_score = answer["score"]
        if isinstance(raw_score, bool) or not isinstance(raw_score, (int, float)):
            raise LayaInvalidResponseError(
                f"Laya score for '{question_id}' is not numeric."
            )
        score = float(raw_score)
        if score < MIN_LEVEL or score > MAX_LEVEL:
            raise LayaInvalidResponseError(
                f"Laya score for '{question_id}' is outside {MIN_LEVEL}-{MAX_LEVEL}."
            )
        scores[question_id] = score
    return scores


def weighted_match_score(scores: dict[str, float]) -> int:
    """Convert 0-4 question scores into one integer from 0 to 100."""
    if set(scores) != set(QUESTION_IDS):
        missing = [question_id for question_id in QUESTION_IDS if question_id not in scores]
        raise LayaInvalidResponseError(
            "Cannot weight scores because these answers are missing: " + ", ".join(missing)
        )
    try:
        return calculate_match_score(
            required_skills=scores["required_skills"],
            experience=scores["experience"],
            responsibilities=scores["responsibilities"],
            preferred_skills=scores["preferred_skills"],
            overall_alignment=scores["overall_alignment"],
        )
    except ValueError as exc:
        raise LayaInvalidResponseError(str(exc)) from exc


def state_token_budget(max_len: int, head_max_len: int) -> int:
    budget = max_len - head_max_len - _STATE_TOKEN_OVERHEAD
    if budget < 1:
        raise LayaInitializationError(
            "The loaded Laya checkpoint does not leave room for resume and job description text."
        )
    return budget


class LayaService:
    def __init__(self, settings: Settings, router=None) -> None:
        self._settings = settings
        self._router = router

    def calculate_match_score(self, resume: str, job_description: str) -> int:
        return self.score(resume, job_description).score

    def score(self, resume: str, job_description: str) -> MatchScoreDetails:
        cleaned_resume = _require_text(resume, "resume")
        cleaned_job = _require_text(job_description, "job description")
        scoring_resume, scoring_job = self._texts_for_scoring(cleaned_resume, cleaned_job)
        model_name = self._model_name()

        try:
            router = self._router if self._router is not None else _shared_router(self._settings)
            agent = router.load(model_name)
        except LayaServiceError:
            raise
        except Exception as exc:
            logger.exception("Laya checkpoint failed to load")
            raise LayaInitializationError(
                "The Laya model could not be loaded. Check network access to the "
                "typed-decisions checkpoint and try again."
            ) from exc

        tokenizer = getattr(agent, "tok", None)
        if tokenizer is None:
            raise LayaInitializationError("The loaded Laya checkpoint has no tokenizer.")

        max_len, head_max_len = _checkpoint_limits(agent)
        state_limit = state_token_budget(max_len, head_max_len)
        content_budget = self._content_budget(state_limit)
        try:
            prepared = InputPreprocessor().prepare_for_laya(
                scoring_resume,
                scoring_job,
                tokenizer,
                content_budget=content_budget,
                state_limit=state_limit,
                measure_state=lambda resume_text, job_text: _count_state_tokens(
                    tokenizer,
                    build_state(resume_text, job_text),
                ),
            )
        except ValueError as exc:
            raise LayaInputError(str(exc)) from exc

        state = build_state(prepared.resume, prepared.job_description)
        state_tokens = _count_state_tokens(tokenizer, state)
        if state_tokens > state_limit:
            raise LayaInputError(
                "Preprocessing could not fit the resume and job description into the Laya context limit."
            )

        started = time.perf_counter()
        try:
            with _predict_lock:
                result = router.predict(state, score_questions(), model=model_name)
        except LayaServiceError:
            raise
        except Exception as exc:
            logger.exception("Laya predict failed")
            raise LayaInferenceError(
                "Laya could not score this resume against the job description."
            ) from exc
        elapsed_ms = (time.perf_counter() - started) * 1000.0

        scores = extract_scores(result)
        analysis = match_analysis(scores)
        match_score = analysis.final_score
        reported_model = model_name
        if isinstance(result, dict):
            routing = result.get("routing")
            if isinstance(routing, dict) and routing.get("model"):
                reported_model = str(routing["model"])

        logger.info(
            "Laya match scored model=%s final_score=%s required_skills=%.4f "
            "experience=%.4f responsibilities=%.4f preferred_skills=%.4f "
            "overall_alignment=%.4f elapsed_ms=%.0f "
            "original_resume_tokens=%s original_job_description_tokens=%s "
            "final_resume_tokens=%s final_job_description_tokens=%s "
            "compacted=%s state_tokens=%s state_limit=%s max_len=%s head_max_len=%s",
            reported_model,
            analysis.final_score,
            analysis.required_skills,
            analysis.experience,
            analysis.responsibilities,
            analysis.preferred_skills,
            analysis.overall_alignment,
            elapsed_ms,
            prepared.original_resume_tokens,
            prepared.original_job_description_tokens,
            prepared.final_resume_tokens,
            prepared.final_job_description_tokens,
            prepared.compacted,
            state_tokens,
            state_limit,
            max_len,
            head_max_len,
        )
        return MatchScoreDetails(
            score=match_score,
            analysis=analysis,
            answers=scores,
            model=reported_model,
            elapsed_ms=elapsed_ms,
            max_len=max_len,
            head_max_len=head_max_len,
            state_tokens=state_tokens,
            state_token_budget=state_limit,
            original_resume_tokens=prepared.original_resume_tokens,
            original_job_description_tokens=prepared.original_job_description_tokens,
            final_resume_tokens=prepared.final_resume_tokens,
            final_job_description_tokens=prepared.final_job_description_tokens,
            compacted=prepared.compacted,
        )

    def _texts_for_scoring(self, resume: str, job_description: str) -> tuple[str, str]:
        """Use extracted profiles when enabled. Fall back to the original text."""
        if not self._settings.llm_extraction_enabled:
            return resume, job_description
        try:
            extraction = ProfileExtractionService(LLMService(self._settings))
            candidate = extraction.extract_candidate_profile(resume)
            job = extraction.extract_job_profile(job_description)
        except ExtractionError:
            logger.warning(
                "Structured extraction failed. Scoring will use the original resume and job description. llm_model=%s",
                self._settings.llm_model,
            )
            return resume, job_description
        rendered_resume = render_candidate_profile(candidate)
        rendered_job = render_job_profile(job)
        if not rendered_resume.strip() or not rendered_job.strip():
            logger.warning("Structured profiles were empty. Scoring will use the original text.")
            return resume, job_description
        logger.info("Scoring will use extracted profiles. llm_model=%s", self._settings.llm_model)
        return rendered_resume, rendered_job

    def _content_budget(self, state_limit: int) -> int:
        margin = self._settings.laya_token_safety_margin
        if margin < 0:
            margin = 0
        derived = max(1, state_limit - margin)
        configured = self._settings.laya_input_token_budget
        if configured is None:
            return derived
        if configured < 1:
            raise LayaInputError("LAYA_INPUT_TOKEN_BUDGET must be a positive integer.")
        return min(configured, state_limit)

    def _model_name(self) -> str:
        configured = (self._settings.laya_model or "").strip()
        return configured or MODEL_NAME


def _require_text(value: str, label: str) -> str:
    if value is None or not str(value).strip():
        raise LayaInputError(f"{label} must not be blank")
    return str(value).strip()


def _checkpoint_limits(agent) -> tuple[int, int]:
    config = getattr(agent, "cfg", None) or {}
    try:
        max_len = int(config.get("max_len", 1024))
        head_max_len = int(config.get("head_max_len", 192))
    except (TypeError, ValueError) as exc:
        raise LayaInitializationError(
            "The loaded Laya checkpoint did not report a usable context length."
        ) from exc
    return max_len, head_max_len


def _count_state_tokens(tokenizer, state: dict) -> int:
    from laya.common import serialize_state

    return count_tokens(serialize_state(state), tokenizer)


class BroadLayaScoringService(LayaService):
    """Baseline broad Laya scoring. Requirement matching is compared against this path."""


def _shared_router(settings: Settings):
    global _router, _router_revision
    revision = (settings.laya_checkpoint or "").strip() or None
    with _router_lock:
        if _router is None or _router_revision != revision:
            from laya import Router

            kwargs = {}
            if revision is not None:
                kwargs["revision"] = revision
            _router = Router(**kwargs)
            _router_revision = revision
        return _router
