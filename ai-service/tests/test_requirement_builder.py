from app.models.candidate_profile import CandidateProfile
from app.models.job_profile import JobProfile
from app.models.requirement import RequirementCategory
from app.services.requirement_builder import build_matching_context, build_requirements

BAJAJ_JOB = JobProfile(
    role="Senior Relationship Manager - GL North",
    required_skills=[
        "Compliance",
        "Customer Relationships",
        "Loans",
        "LOS",
        "Relationship Manager",
        "Data Entry",
        "Customer Queries",
    ],
    preferred_skills=[],
    responsibilities=[
        "Conduct village surveys and prospecting in selected villages.",
        "Source new customers and form JLG groups.",
        "Collect information needed for sourcing and validate documents.",
        "Plan customer center meetings.",
        "Ensure collections and recoveries are completed on schedule.",
        "Carry out end-use monitoring of loans.",
        "Maintain customer relationships and compliance.",
        "Prepare daily reports.",
    ],
)


def test_required_preferred_responsibility_experience_and_role():
    job = JobProfile(
        role="Backend Engineer",
        minimum_years_experience=4,
        required_skills=["Java", "Spring Boot"],
        preferred_skills=["Kafka"],
        responsibilities=["Customer sourcing"],
    )
    requirements = build_requirements(job)
    by_category = {}
    for requirement in requirements:
        by_category.setdefault(requirement.category, []).append(requirement.name)
    assert by_category[RequirementCategory.REQUIRED_SKILL] == ["Java", "Spring Boot"]
    assert by_category[RequirementCategory.PREFERRED_SKILL] == ["Kafka"]
    assert by_category[RequirementCategory.RESPONSIBILITY] == ["Customer sourcing"]
    assert by_category[RequirementCategory.EXPERIENCE] == ["minimum 4 years"]
    assert by_category[RequirementCategory.ROLE] == ["Backend Engineer"]


def test_duplicate_removal_keeps_one_required_skill():
    job = JobProfile(
        role="Backend Engineer",
        required_skills=["Java", "Java", "java"],
        preferred_skills=["Java", "Kafka"],
    )
    requirements = build_requirements(job)
    names = [(item.category, item.name) for item in requirements]
    assert names.count((RequirementCategory.REQUIRED_SKILL, "Java")) == 1
    assert (RequirementCategory.PREFERRED_SKILL, "Java") not in names
    assert (RequirementCategory.PREFERRED_SKILL, "Kafka") in names


def test_empty_preferred_skills_and_responsibilities_add_nothing():
    requirements = build_requirements(JobProfile(role="Backend Engineer", required_skills=["Java"]))
    categories = {item.category for item in requirements}
    assert RequirementCategory.PREFERRED_SKILL not in categories
    assert RequirementCategory.RESPONSIBILITY not in categories
    assert RequirementCategory.EXPERIENCE not in categories


def test_bajaj_requirements_represent_the_job_not_the_candidate():
    context = build_matching_context(
        CandidateProfile(role="Full-stack engineer", skills=["Java", "Spring Boot", "Kafka"]),
        BAJAJ_JOB,
    )
    names = [item.name.casefold() for item in context.requirements]
    joined = " ".join(names)
    assert context.candidate.skills == ["Java", "Spring Boot", "Kafka"]
    assert any(item.category == RequirementCategory.ROLE and "relationship manager" in item.name.casefold() for item in context.requirements)
    for skill in ["compliance", "customer relationships", "loans", "los", "data entry", "customer queries"]:
        assert any(item.category == RequirementCategory.REQUIRED_SKILL and skill in item.name.casefold() for item in context.requirements)
    for concept in ["village survey", "source new customers", "validate documents", "meetings", "collections", "recoveries", "end-use", "daily reports"]:
        assert concept in joined
    for invented in ["spring boot", "react", "kafka", "aws"]:
        assert invented not in joined
    assert "none" not in names
