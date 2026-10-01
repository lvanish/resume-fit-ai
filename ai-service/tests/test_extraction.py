import httpx
import pytest

from app.config import Settings
from app.models.candidate_profile import CandidateProfile
from app.models.job_profile import JobProfile
from app.prompts.job_prompt import JOB_SYSTEM, job_prompt
from app.prompts.resume_prompt import RESUME_SYSTEM, resume_prompt
from app.services.laya_service import LayaService
from app.services.llm_service import (
    ExtractionValidationError,
    LLMService,
    ModelNotAvailableError,
    OllamaUnavailableError,
    _map_provider_error,
)
from app.services.profile_extraction_service import ProfileExtractionService
from app.services.profile_text import render_candidate_profile, render_job_profile
from evaluation.extraction_cases import candidate_flags, job_flags


class _Chain:
    def __init__(self, result):
        self.result = result
        self.seen = None

    def invoke(self, payload):
        self.seen = payload
        return self.result


def test_prompts_forbid_inference_and_keep_source_text_delimited():
    assert "Do not infer unstated technologies or experience." in RESUME_SYSTEM
    assert "Do not score the candidate." in RESUME_SYSTEM
    assert "REQUIRED" in JOB_SYSTEM
    assert "PREFERRED" in JOB_SYSTEM
    assert "Do not treat every technology mentioned only in a company description" in JOB_SYSTEM
    rendered = resume_prompt.invoke({"resume": "Built services using Kafka."})
    assert "Built services using Kafka." in rendered.to_string()
    job_rendered = job_prompt.invoke({"job_description": "Kafka is preferred."})
    assert "Kafka is preferred." in job_rendered.to_string()


def test_extraction_service_returns_validated_profiles():
    candidate_chain = _Chain(
        CandidateProfile(skills=["Java"], years_of_experience=4, role="Software Engineer")
    )
    job_chain = _Chain(
        JobProfile(role="Backend Engineer", required_skills=["Java"], preferred_skills=["Kafka"])
    )
    service = ProfileExtractionService(
        LLMService(Settings(), candidate_chain=candidate_chain, job_chain=job_chain)
    )
    candidate = service.extract_candidate_profile("Software Engineer with Java.")
    job = service.extract_job_profile("Backend Engineer. Java is required. Kafka is preferred.")
    assert candidate_chain.seen == {"resume": "Software Engineer with Java."}
    assert job_chain.seen == {"job_description": "Backend Engineer. Java is required. Kafka is preferred."}
    assert candidate.skills == ["Java"]
    assert job.preferred_skills == ["Kafka"]
    assert "Kafka" not in job.required_skills


def test_dict_output_is_validated_and_invalid_output_is_rejected():
    service = LLMService(Settings(), candidate_chain=_Chain({"skills": ["Java"]}))
    profile = service.extract_candidate_profile("Built services with Java.")
    assert isinstance(profile, CandidateProfile)
    assert profile.skills == ["Java"]

    broken = LLMService(Settings(), candidate_chain=_Chain("not a profile"))
    with pytest.raises(ExtractionValidationError):
        broken.extract_candidate_profile("resume")


def test_provider_errors_do_not_invent_a_profile():
    assert isinstance(_map_provider_error(httpx.ConnectError("refused"), "llama3.1"), OllamaUnavailableError)
    assert isinstance(
        _map_provider_error(RuntimeError("model 'llama3.1' not found"), "llama3.1"),
        ModelNotAvailableError,
    )
    with pytest.raises(OllamaUnavailableError):
        LLMService(
            Settings(),
            candidate_chain=_ChainFail(httpx.ConnectError("refused")),
        ).extract_candidate_profile("resume")


def test_rendered_profile_contains_only_extracted_fields():
    text = render_candidate_profile(
        CandidateProfile(skills=["Java"], responsibilities=["Built REST APIs"])
    )
    assert "Java" in text
    assert "Kafka" not in text
    job = render_job_profile(
        JobProfile(required_skills=["Java", "Spring Boot"], preferred_skills=["Kafka"])
    )
    assert "Required skills: Java; Spring Boot" in job
    assert "Preferred skills: Kafka" in job


def test_guardrail_checks_catch_invented_kafka_and_misplaced_preferred_skill():
    assert candidate_flags({"absent_skills": ["Kafka"]}, ["Java"], []) == []
    assert "unexpected skill Kafka" in candidate_flags({"absent_skills": ["Kafka"]}, ["Kafka"], [])[0]
    assert candidate_flags({"present_skills": ["Kafka"]}, ["Kafka consumers"], []) == []
    flags = job_flags(
        {"preferred_skills": ["Kafka"], "required_skills": ["Java"], "absent_required_skills": ["Kafka"]},
        ["Java", "Kafka"],
        [],
    )
    assert any("Kafka" in flag and "required" in flag for flag in flags)


def test_disabled_extraction_keeps_the_original_text():
    service = LayaService(Settings(llm_extraction_enabled=False))
    resume, job = service._texts_for_scoring("original resume", "original job")
    assert resume == "original resume"
    assert job == "original job"


def test_failed_extraction_falls_back_to_raw_text(monkeypatch):
    class Unavailable:
        def __init__(self, settings):
            self.settings = settings

        def extract_candidate_profile(self, resume):
            raise OllamaUnavailableError("down")

        def extract_job_profile(self, job_description):
            raise AssertionError("job extraction should not run after the resume call fails")

    monkeypatch.setattr("app.services.laya_service.LLMService", Unavailable)
    service = LayaService(Settings(llm_extraction_enabled=True))
    resume, job = service._texts_for_scoring("original resume", "original job")
    assert resume == "original resume"
    assert job == "original job"


def test_successful_extraction_compacts_text_for_scoring(monkeypatch):
    class Ready:
        def __init__(self, settings):
            self.settings = settings

        def extract_candidate_profile(self, resume):
            return CandidateProfile(skills=["Java"], role="Software Engineer")

        def extract_job_profile(self, job_description):
            return JobProfile(role="Backend Engineer", required_skills=["Java"])

    monkeypatch.setattr("app.services.laya_service.LLMService", Ready)
    service = LayaService(Settings(llm_extraction_enabled=True))
    resume, job = service._texts_for_scoring("a long original resume", "a long original job")
    assert "Software Engineer" in resume
    assert "long original resume" not in resume
    assert "Backend Engineer" in job
    assert "long original job" not in job


class _ChainFail:
    def __init__(self, error):
        self.error = error

    def invoke(self, payload):
        raise self.error
