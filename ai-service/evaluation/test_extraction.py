"""Print CandidateProfile and JobProfile from the local Ollama model.

Usage, from ai-service:

    python -m evaluation.test_extraction

This does not change the public score API. It does not save resume text.
"""

from __future__ import annotations

import json
import sys

import httpx

from app.config import get_settings
from app.services.llm_service import LLMService
from app.services.profile_extraction_service import ProfileExtractionService
from evaluation.extraction_cases import (
    GUARDRAIL_CASES,
    QUALITY_CASES,
    RELATIONSHIP_MANAGER_JD,
    SOFTWARE_ENGINEER_RESUME,
    candidate_flags,
    job_flags,
)
def main() -> None:
    settings = get_settings()
    _require_ollama(settings.ollama_base_url, settings.llm_model)
    service = ProfileExtractionService(LLMService(settings))
    smoke = json.loads(
        __import__("pathlib").Path(__file__).resolve().parent.joinpath("smoke_case.json").read_text(
            encoding="utf-8"
        )
    )

    print(f"llm_model={settings.llm_model}")
    print(f"ollama_base_url={settings.ollama_base_url}")
    print("\n== sample resume and job description ==")
    candidate = service.extract_candidate_profile(smoke["resume"])
    job = service.extract_job_profile(smoke["jobDescription"])
    print("CandidateProfile:")
    print(candidate.model_dump_json(indent=2))
    print("JobProfile:")
    print(job.model_dump_json(indent=2))

    print("\n== quality cases ==")
    quality_flags = []
    for case in QUALITY_CASES:
        profile = service.extract_candidate_profile(case["resume"])
        flags = candidate_flags(case, profile.skills, profile.responsibilities)
        quality_flags.extend(f"{case['id']}: {flag}" for flag in flags)
        print(f"{case['id']}: {profile.model_dump_json()}")
        if flags:
            print("  flags: " + "; ".join(flags))

    print("\n== guardrails ==")
    guardrail_flags = []
    for case in GUARDRAIL_CASES:
        if case["kind"] == "resume":
            profile = service.extract_candidate_profile(case["text"])
            flags = candidate_flags(case, profile.skills, profile.responsibilities)
            print(f"{case['id']}: {profile.model_dump_json()}")
        else:
            profile = service.extract_job_profile(case["text"])
            flags = job_flags(case, profile.required_skills, profile.preferred_skills)
            print(f"{case['id']}: {profile.model_dump_json()}")
        guardrail_flags.extend(f"{case['id']}: {flag}" for flag in flags)
        if flags:
            print("  flags: " + "; ".join(flags))

    print("\n== software engineer vs Senior Relationship Manager - GL North ==")
    candidate = service.extract_candidate_profile(SOFTWARE_ENGINEER_RESUME)
    job = service.extract_job_profile(RELATIONSHIP_MANAGER_JD)
    print("CandidateProfile:")
    print(candidate.model_dump_json(indent=2))
    print("JobProfile:")
    print(job.model_dump_json(indent=2))
    sales_flags = candidate_flags(
        {
            "absent_skills": ["relationship management", "customer acquisition", "loan collection"],
            "absent_responsibilities": [
                "relationship management",
                "customer acquisition",
                "loan collection",
            ],
        },
        candidate.skills + [candidate.role or ""],
        candidate.responsibilities,
    )
    sales_flags.extend(
        job_flags(
            {
                "required_skills": ["relationship management"],
                "absent_required_skills": ["Java", "Spring Boot", "React"],
            },
            job.required_skills + job.responsibilities + [job.role or ""],
            job.preferred_skills,
        )
    )
    if sales_flags:
        print("flags: " + "; ".join(sales_flags))
    else:
        print("flags: none")

    print("\n== summary ==")
    print(f"quality_flags={len(quality_flags)} guardrail_flags={len(guardrail_flags)} sales_flags={len(sales_flags)}")


def _require_ollama(base_url: str, model_name: str) -> None:
    url = base_url.rstrip("/") + "/api/tags"
    try:
        response = httpx.get(url, timeout=5)
        response.raise_for_status()
    except httpx.HTTPError:
        print(
            "Ollama is not reachable at "
            f"{base_url}. Install Ollama, start it, then run: ollama pull {model_name}"
        )
        raise SystemExit(1)
    payload = response.json()
    names = [str(item.get("name", "")) for item in payload.get("models", [])]
    if not _model_present(names, model_name):
        print(
            f"Ollama is running but '{model_name}' is not installed. "
            f"Pull it with: ollama pull {model_name}"
        )
        print("Installed models: " + (", ".join(names) if names else "(none)"))
        raise SystemExit(1)


def _model_present(names: list[str], model_name: str) -> bool:
    target = model_name.casefold()
    for name in names:
        normalized = name.casefold()
        if normalized == target or normalized.split(":", 1)[0] == target or normalized == f"{target}:latest":
            return True
    return False


if __name__ == "__main__":
    main()
