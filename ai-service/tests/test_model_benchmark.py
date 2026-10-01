from app.models.candidate_profile import CandidateProfile
from app.models.job_profile import JobProfile
from evaluation.model_benchmark import (
    candidate_flags,
    grade_candidate,
    grade_job,
    is_low_information,
    job_flags,
)


def test_empty_profile_is_not_successful_information():
    assert is_low_information(CandidateProfile())
    assert is_low_information(JobProfile())
    filled = CandidateProfile(role="Software Engineer", skills=["Java"])
    assert not is_low_information(filled)


def test_missing_java_is_flagged_and_not_rewritten():
    profile = CandidateProfile(role="Software Engineer", skills=["React"])
    flags = candidate_flags(profile)
    assert "missing_obvious_skill" in flags
    assert profile.skills == ["React"]


def test_job_without_role_title_is_flagged():
    profile = JobProfile(responsibilities=["Conduct village surveys and collections."])
    assert "missing_obvious_role" in job_flags(profile)
    assert grade_job(
        {"outcome": "SUCCESS", "flags": job_flags(profile)}
    ) == "FAIL"


def test_hallucinated_backend_skill_fails_the_job_grade():
    profile = JobProfile(role="Relationship Manager", responsibilities=["Village surveys and collections."])
    profile = profile.model_copy(update={"required_skills": ["Java"]})
    flags = job_flags(profile)
    assert any(flag.startswith("hallucinated:") for flag in flags)
    assert grade_candidate({"outcome": "EMPTY_OR_LOW_INFORMATION", "flags": []}) == "FAIL"
