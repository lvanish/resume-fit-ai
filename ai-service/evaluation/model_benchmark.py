"""Benchmark local Ollama models on one resume and one job description.

Does not call Laya and does not store the source text.

    python -m evaluation.model_benchmark
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

from app.config import Settings
from app.models.candidate_profile import CandidateProfile
from app.models.job_profile import JobProfile
from app.services import llm_service
from app.services.llm_service import (
    ExtractionError,
    ExtractionTimeoutError,
    ExtractionValidationError,
    LLMService,
)
from app.services.profile_extraction_service import ProfileExtractionService
from evaluation.test_real_extraction import JOB_DESCRIPTION, RESUME

MODELS = (
    "qwen2.5:1.5b-instruct-q5_K_M",
    "llama3.2:1b",
    "llama3.2:3b",
)
RESULTS_PATH = Path(__file__).resolve().parent / "model_benchmark_results.json"
CALL_TIMEOUT_SECONDS = 120

CANDIDATE_SKILLS = (
    "Java",
    "Spring Boot",
    "React",
    "PostgreSQL",
    "MySQL",
    "Kafka",
    "Redis",
    "Docker",
    "Kubernetes",
    "AWS",
    "Azure",
    "LangChain",
    "LangGraph",
    "RAG",
)
CANDIDATE_FORBIDDEN = (
    "Relationship Manager",
    "customer acquisition",
    "village survey",
    "collections",
    "loan recovery",
)
JOB_CONCEPTS = (
    "customer acquisition",
    "village survey",
    "loan sourcing",
    "collections",
    "recoveries",
    "customer relationship",
    "compliance",
    "reporting",
)
JOB_FORBIDDEN = ("Java", "Spring Boot", "React", "Kafka", "AWS")


def main() -> None:
    schema_note = inspect_schemas()
    print(schema_note, flush=True)
    ollama = ollama_executable()
    results = []
    for model_name in MODELS:
        print(f"\n== {model_name} ==", flush=True)
        results.append(benchmark_model(ollama, model_name))
        stop_model(ollama, model_name)
    payload = {"schema": schema_note, "structured_output_mode": "json_schema", "models": results}
    RESULTS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print("\n== summary ==", flush=True)
    print("| Model | Resume Extraction | JD Extraction | Total Time | Quality | Notes |")
    print("| --- | --- | --- | --- | --- | --- |")
    for row in results:
        print(
            f"| {row['model']} | {row['resume_grade']} | {row['job_grade']} | "
            f"{row['total_ms']} ms | {row['quality']} | {row['notes']} |"
        )
    print(f"\nwrote {RESULTS_PATH}", flush=True)


def inspect_schemas() -> str:
    candidate = CandidateProfile.model_json_schema()
    job = JobProfile.model_json_schema()
    return (
        "Schema inspection: CandidateProfile has "
        f"{len(candidate.get('properties', {}))} fields and "
        f"{len(candidate.get('required', []))} required keys. "
        "JobProfile has "
        f"{len(job.get('properties', {}))} fields and "
        f"{len(job.get('required', []))} required keys. "
        "Descriptions are one sentence. No fields were removed."
    )


def benchmark_model(ollama: str, model_name: str) -> dict:
    pull = subprocess.run([ollama, "pull", model_name], check=False)
    if pull.returncode != 0:
        return _failed_row(model_name, "EXCEPTION", "EXCEPTION", f"ollama pull exited {pull.returncode}")
    llm_service._model = None
    llm_service._model_key = None
    settings = Settings(llm_model=model_name, llm_timeout_seconds=CALL_TIMEOUT_SECONDS)
    service = ProfileExtractionService(LLMService(settings))
    resume_result = _extract(service.extract_candidate_profile, RESUME, "candidate")
    job_result = _extract(service.extract_job_profile, JOB_DESCRIPTION, "job")
    memory = loaded_model_size(ollama, model_name)
    resume_grade = grade_candidate(resume_result)
    job_grade = grade_job(job_result)
    quality = combine_grades(resume_grade, job_grade)
    total_ms = None
    if resume_result["elapsed_ms"] is not None and job_result["elapsed_ms"] is not None:
        total_ms = round(resume_result["elapsed_ms"] + job_result["elapsed_ms"], 1)
    notes = "; ".join(flag for flag in resume_result["flags"] + job_result["flags"] if flag)
    if not notes:
        notes = "no quality flags"
    row = {
        "model": model_name,
        "model_size": memory,
        "structured_output_mode": "json_schema",
        "post_processed": False,
        "resume_outcome": resume_result["outcome"],
        "resume_validation": resume_result["validation"],
        "resume_ms": resume_result["elapsed_ms"],
        "resume_grade": resume_grade,
        "resume_flags": resume_result["flags"],
        "job_outcome": job_result["outcome"],
        "job_validation": job_result["validation"],
        "job_ms": job_result["elapsed_ms"],
        "job_grade": job_grade,
        "job_flags": job_result["flags"],
        "total_ms": total_ms,
        "quality": quality,
        "notes": notes,
        "candidate_profile": resume_result["profile"],
        "job_profile": job_result["profile"],
    }
    print(
        f"resume={resume_result['outcome']} {resume_grade} {resume_result['elapsed_ms']} ms; "
        f"job={job_result['outcome']} {job_grade} {job_result['elapsed_ms']} ms; "
        f"size={memory}",
        flush=True,
    )
    return row


def _extract(method, text: str, kind: str) -> dict:
    started = time.perf_counter()
    try:
        profile = method(text)
    except ExtractionTimeoutError as exc:
        return _call_result("TIMEOUT", "not_validated", None, (time.perf_counter() - started) * 1000, [str(exc)])
    except ExtractionValidationError as exc:
        return _call_result("INVALID", "failed", None, (time.perf_counter() - started) * 1000, [str(exc)])
    except ExtractionError as exc:
        return _call_result("EXCEPTION", "not_validated", None, (time.perf_counter() - started) * 1000, [type(exc).__name__])
    except Exception as exc:
        return _call_result("EXCEPTION", "not_validated", None, (time.perf_counter() - started) * 1000, [type(exc).__name__])
    elapsed_ms = (time.perf_counter() - started) * 1000
    payload = profile.model_dump()
    flags = candidate_flags(profile) if kind == "candidate" else job_flags(profile)
    outcome = "EMPTY_OR_LOW_INFORMATION" if is_low_information(profile) else "SUCCESS"
    return _call_result(outcome, "succeeded", payload, elapsed_ms, flags)


def _call_result(outcome: str, validation: str, profile, elapsed_ms: float, flags: list[str]) -> dict:
    return {
        "outcome": outcome,
        "validation": validation,
        "profile": profile,
        "elapsed_ms": round(elapsed_ms, 1),
        "flags": flags,
    }


def is_low_information(profile: CandidateProfile | JobProfile) -> bool:
    if isinstance(profile, CandidateProfile):
        return not profile.skills and not profile.role and not profile.responsibilities
    return not profile.role and not profile.responsibilities and not profile.required_skills


def candidate_flags(profile: CandidateProfile) -> list[str]:
    flags = []
    skills = profile.skills
    everywhere = _blob(
        skills,
        profile.responsibilities,
        [profile.role or ""],
    )
    if not _has_term(skills, "Java"):
        flags.append("missing_obvious_skill")
    if not _has_term([profile.role or ""], "Software Engineer"):
        flags.append("missing_obvious_title")
    for skill in CANDIDATE_SKILLS:
        if not _has_term(skills, skill):
            flags.append(f"missing_skill:{skill}")
    for phrase in CANDIDATE_FORBIDDEN:
        if _has_term(everywhere, phrase):
            flags.append(f"hallucinated:{phrase}")
    return flags


def job_flags(profile: JobProfile) -> list[str]:
    flags = []
    role = profile.role or ""
    duty_blob = _blob(profile.responsibilities, profile.required_skills, profile.preferred_skills, [role])
    everywhere = _blob(
        profile.required_skills,
        profile.preferred_skills,
        profile.responsibilities,
        [role],
    )
    if not _has_term([role], "Relationship Manager"):
        flags.append("missing_obvious_role")
    for concept in JOB_CONCEPTS:
        if concept == "loan sourcing":
            present = _has_term(duty_blob, "loan sourcing") or _has_term(duty_blob, "source new customers") or _has_term(duty_blob, "sourcing")
        elif concept == "customer acquisition":
            present = _has_term(duty_blob, "customer acquisition") or _has_term(duty_blob, "new customers")
        elif concept == "reporting":
            present = _has_term(duty_blob, "reporting") or _has_term(duty_blob, "daily reports")
        elif concept == "village survey":
            present = _has_term(duty_blob, "village survey")
        else:
            present = _has_term(duty_blob, concept)
        if not present:
            flags.append(f"missing_concept:{concept}")
    for phrase in JOB_FORBIDDEN:
        if _has_term(everywhere, phrase):
            flags.append(f"hallucinated:{phrase}")
    return flags


def grade_candidate(result: dict) -> str:
    if result["outcome"] != "SUCCESS":
        return "FAIL"
    flags = result["flags"]
    if any(flag.startswith("hallucinated:") for flag in flags):
        return "FAIL"
    if "missing_obvious_skill" in flags or "missing_obvious_title" in flags:
        return "PARTIAL" if _found_skill_count(flags) >= 6 else "FAIL"
    missing = [flag for flag in flags if flag.startswith("missing_skill:")]
    if len(missing) <= 3:
        return "PASS"
    if len(missing) <= 8:
        return "PARTIAL"
    return "FAIL"


def grade_job(result: dict) -> str:
    if result["outcome"] != "SUCCESS":
        return "FAIL"
    flags = result["flags"]
    if any(flag.startswith("hallucinated:") for flag in flags):
        return "FAIL"
    missing = [flag for flag in flags if flag.startswith("missing_concept:")]
    if "missing_obvious_role" in flags:
        return "FAIL"
    if not missing:
        return "PASS"
    if len(missing) <= 3:
        return "PARTIAL"
    return "FAIL"


def combine_grades(resume_grade: str, job_grade: str) -> str:
    if resume_grade == "FAIL" or job_grade == "FAIL":
        return "FAIL"
    if resume_grade == "PARTIAL" or job_grade == "PARTIAL":
        return "PARTIAL"
    return "PASS"


def _found_skill_count(flags: list[str]) -> int:
    missing = {flag.split(":", 1)[1] for flag in flags if flag.startswith("missing_skill:")}
    return len(CANDIDATE_SKILLS) - len(missing)


def _blob(*groups: list[str]) -> list[str]:
    values: list[str] = []
    for group in groups:
        values.extend(group)
    return values


def _has_term(values: list[str], term: str) -> bool:
    haystack = " \n".join(values).casefold()
    pattern = rf"(?<![a-z0-9]){re.escape(term.casefold())}s?(?![a-z0-9])"
    return re.search(pattern, haystack) is not None


def _failed_row(model_name: str, resume_outcome: str, job_outcome: str, notes: str) -> dict:
    return {
        "model": model_name,
        "model_size": None,
        "structured_output_mode": "json_schema",
        "post_processed": False,
        "resume_outcome": resume_outcome,
        "resume_validation": "not_validated",
        "resume_ms": None,
        "resume_grade": "FAIL",
        "resume_flags": [],
        "job_outcome": job_outcome,
        "job_validation": "not_validated",
        "job_ms": None,
        "job_grade": "FAIL",
        "job_flags": [],
        "total_ms": None,
        "quality": "FAIL",
        "notes": notes,
        "candidate_profile": None,
        "job_profile": None,
    }


def ollama_executable() -> str:
    found = shutil.which("ollama")
    if found:
        return found
    local = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"
    if local.exists():
        return str(local)
    raise SystemExit("Ollama is not installed.")


def stop_model(ollama: str, model_name: str) -> None:
    subprocess.run([ollama, "stop", model_name], check=False)
    llm_service._model = None
    llm_service._model_key = None


def loaded_model_size(ollama: str, model_name: str) -> str | None:
    completed = subprocess.run([ollama, "ps"], check=False, capture_output=True, text=True)
    for line in completed.stdout.splitlines():
        if model_name.split(":", 1)[0] in line:
            parts = line.split()
            if len(parts) >= 3:
                return " ".join(parts[2:4])
    return None


if __name__ == "__main__":
    main()
