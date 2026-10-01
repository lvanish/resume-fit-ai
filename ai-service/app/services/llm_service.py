"""Local Ollama extraction through LangChain structured output.

The chat model is created once and reused. This module does not score matches.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Protocol

import httpx
from langchain_core.exceptions import OutputParserException
from pydantic import ValidationError

from app.config import Settings
from app.models.candidate_profile import CandidateProfile
from app.models.job_profile import JobProfile
from app.prompts.job_prompt import job_prompt
from app.prompts.resume_prompt import resume_prompt

logger = logging.getLogger(__name__)


class ExtractionError(Exception):
    """Base error for structured extraction. Never carries a substitute profile."""


class OllamaUnavailableError(ExtractionError):
    """Ollama is not running or cannot be reached."""


class ModelNotAvailableError(ExtractionError):
    """The configured chat model is not installed in Ollama."""


class ExtractionTimeoutError(ExtractionError):
    """The local model did not finish within the configured timeout."""


class ExtractionValidationError(ExtractionError):
    """The model output was not a valid CandidateProfile or JobProfile."""


class ExtractionFailedError(ExtractionError):
    """The extraction call failed for another reason."""


class SupportsInvoke(Protocol):
    def invoke(self, input: dict) -> object: ...


_model = None
_model_key: tuple[str, str, float, int] | None = None
_model_lock = threading.Lock()


class LLMService:
    def __init__(
        self,
        settings: Settings,
        candidate_chain: SupportsInvoke | None = None,
        job_chain: SupportsInvoke | None = None,
    ) -> None:
        self._settings = settings
        self._candidate_chain = candidate_chain
        self._job_chain = job_chain

    def extract_candidate_profile(self, resume: str) -> CandidateProfile:
        started = time.perf_counter()
        try:
            result = self._candidate().invoke({"resume": resume})
            profile = _as_profile(result, CandidateProfile)
            from app.services.profile_validation import validate_candidate_profile

            profile = validate_candidate_profile(profile, resume)
        except ExtractionError:
            raise
        except Exception as exc:
            raise _map_provider_error(exc, self._settings.llm_model) from exc
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        logger.info(
            "resume_extraction_ms=%.0f llm_model=%s",
            elapsed_ms,
            self._settings.llm_model,
        )
        return profile

    def extract_job_profile(self, job_description: str) -> JobProfile:
        started = time.perf_counter()
        try:
            result = self._job().invoke({"job_description": job_description})
            profile = _as_profile(result, JobProfile)
            from app.services.profile_validation import validate_job_profile

            profile = validate_job_profile(profile, job_description)
        except ExtractionError:
            raise
        except Exception as exc:
            raise _map_provider_error(exc, self._settings.llm_model) from exc
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        logger.info(
            "job_extraction_ms=%.0f llm_model=%s",
            elapsed_ms,
            self._settings.llm_model,
        )
        return profile

    def _candidate(self) -> SupportsInvoke:
        if self._candidate_chain is not None:
            return self._candidate_chain
        return resume_prompt | _structured_model(self._settings, CandidateProfile)

    def _job(self) -> SupportsInvoke:
        if self._job_chain is not None:
            return self._job_chain
        return job_prompt | _structured_model(self._settings, JobProfile)


def _structured_model(settings: Settings, schema: type):
    if settings.llm_provider.strip().lower() != "ollama":
        raise ExtractionFailedError(
            f"LLM_PROVIDER '{settings.llm_provider}' is not supported. Use ollama."
        )
    model_name = settings.llm_model.strip()
    if not model_name:
        raise ModelNotAvailableError("LLM_MODEL is empty. Set it to a local Ollama chat model.")
    chat = _shared_chat_model(settings)
    return chat.with_structured_output(schema)


def _shared_chat_model(settings: Settings):
    global _model, _model_key
    key = (
        settings.llm_model.strip(),
        settings.ollama_base_url.rstrip("/"),
        settings.llm_timeout_seconds,
        settings.llm_num_predict,
        settings.llm_num_ctx,
    )
    with _model_lock:
        if _model is not None and _model_key == key:
            return _model
        from langchain_ollama import ChatOllama

        _model = ChatOllama(
            model=key[0],
            base_url=key[1],
            temperature=0,
            num_ctx=settings.llm_num_ctx,
            num_predict=settings.llm_num_predict,
            client_kwargs={"timeout": settings.llm_timeout_seconds},
        )
        _model_key = key
        return _model


def _as_profile(result: object, schema: type[CandidateProfile] | type[JobProfile]):
    if isinstance(result, schema):
        return result
    if isinstance(result, dict):
        try:
            return schema.model_validate(result)
        except ValidationError as exc:
            raise ExtractionValidationError(
                f"The model output is not a valid {schema.__name__}."
            ) from exc
    raise ExtractionValidationError(
        f"The model did not return a {schema.__name__}."
    )


def _map_provider_error(exc: Exception, model_name: str) -> ExtractionError:
    if isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout)):
        return OllamaUnavailableError(
            "Ollama is not reachable. Start Ollama and confirm OLLAMA_BASE_URL."
        )
    if isinstance(exc, (httpx.ReadTimeout, httpx.TimeoutException, TimeoutError)):
        return ExtractionTimeoutError("The local model timed out during extraction.")
    if isinstance(exc, (OutputParserException, ValidationError)):
        return ExtractionValidationError("The model returned malformed structured output.")
    message = str(exc).lower()
    if "timed out" in message or "timeout" in message:
        return ExtractionTimeoutError("The local model timed out during extraction.")
    if "connection" in message or "connect" in message or "11434" in message:
        return OllamaUnavailableError(
            "Ollama is not reachable. Start Ollama and confirm OLLAMA_BASE_URL."
        )
    if "not found" in message and "model" in message:
        return ModelNotAvailableError(
            f"Ollama does not have model '{model_name}'. Pull it with: ollama pull {model_name}"
        )
    if "not found" in message:
        return ModelNotAvailableError(
            f"Ollama does not have model '{model_name}'. Pull it with: ollama pull {model_name}"
        )
    return ExtractionFailedError("Structured extraction failed.")
