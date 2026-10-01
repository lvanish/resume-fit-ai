import pytest

from app.config import Settings
from app.models.candidate_profile import CandidateProfile
from app.models.job_profile import JobProfile
from app.services.llm_service import ExtractionValidationError, LLMService
from app.services.profile_validation import (
    validate_candidate_profile,
    validate_job_profile,
    validate_skill_against_source,
)
from evaluation.test_real_extraction import JOB_DESCRIPTION as RELATIONSHIP_MANAGER_JD


class _Chain:
    def __init__(self, result):
        self.result = result

    def invoke(self, payload):
        return self.result


def test_candidate_role_must_be_present_when_the_resume_states_one():
    profile = CandidateProfile(skills=["Java"])
    with pytest.raises(ExtractionValidationError, match="states a role"):
        validate_candidate_profile(profile, "Software Engineer. Skills: Java.")


def test_candidate_skill_missing_from_the_resume_is_rejected():
    profile = CandidateProfile(role="Software Engineer", skills=["Kafka"])
    with pytest.raises(ExtractionValidationError, match="Kafka"):
        validate_candidate_profile(profile, "Software Engineer who uses Java.")


PRODUCTION_SOURCE = (
    "Full-stack engineer with 3+ years of experience delivering production applications "
    "across Java, Spring Boot, React and TypeScript."
)


def test_exact_responsibility_excerpt_passes():
    profile = validate_candidate_profile(
        CandidateProfile(
            role="Full-stack engineer",
            years_of_experience=3,
            skills=["Java", "Spring Boot", "React", "TypeScript"],
            responsibilities=[
                "delivering production applications across Java, Spring Boot, React and TypeScript"
            ],
        ),
        PRODUCTION_SOURCE,
    )
    assert "delivering production applications" in profile.responsibilities[0]


def test_paraphrased_responsibility_fails():
    profile = CandidateProfile(
        role="Full-stack engineer",
        responsibilities=[
            "Delivered production applications across Java, Spring Boot, React and TypeScript"
        ],
    )
    with pytest.raises(ExtractionValidationError, match="does not appear"):
        validate_candidate_profile(profile, PRODUCTION_SOURCE)


def test_responsibility_whitespace_variation_passes():
    profile = validate_candidate_profile(
        CandidateProfile(
            role="Full-stack engineer",
            responsibilities=[
                "delivering   production\napplications across Java, Spring Boot, React and TypeScript"
            ],
        ),
        PRODUCTION_SOURCE,
    )
    assert profile.responsibilities


def test_responsibility_punctuation_variation_passes():
    profile = validate_candidate_profile(
        CandidateProfile(
            role="Full-stack engineer",
            responsibilities=[
                "delivering production applications across Java Spring Boot React and TypeScript"
            ],
        ),
        "Full-stack engineer. “delivering production applications across Java, Spring Boot, React and TypeScript.”",
    )
    assert profile.responsibilities


def test_fabricated_responsibility_fails():
    with pytest.raises(ExtractionValidationError, match="does not appear"):
        validate_candidate_profile(
            CandidateProfile(
                role="Full-stack engineer",
                responsibilities=["Owned the payments platform migration"],
            ),
            PRODUCTION_SOURCE,
        )


def test_job_responsibility_excerpt_and_paraphrase():
    source = "Conduct village surveys and do prospecting in selected villages."
    exact = validate_job_profile(
        JobProfile(
            role="Area Sales Manager",
            responsibilities=["Conduct village surveys and do prospecting in selected villages."],
        ),
        "Area Sales Manager\n" + source,
    )
    assert exact.responsibilities[0].startswith("Conduct village surveys")
    with pytest.raises(ExtractionValidationError, match="does not appear"):
        validate_job_profile(
            JobProfile(
                role="Area Sales Manager",
                responsibilities=["Perform field-level customer prospecting."],
            ),
            "Area Sales Manager\n" + source,
        )


def test_role_normalization_stays_grounded():
    profile = validate_candidate_profile(
        CandidateProfile(role="Full-stack engineer", skills=["Java"]),
        "Full-Stack Software Engineer. Skills: Java.",
    )
    assert profile.role == "Full-stack engineer"
    with pytest.raises(ExtractionValidationError, match="Data Scientist"):
        validate_candidate_profile(
            CandidateProfile(role="Data Scientist", skills=["Java"]),
            "Full-Stack Software Engineer. Skills: Java.",
        )
    job = validate_job_profile(
        JobProfile(role="Senior Relationship Manager - GL North", required_skills=["Compliance"]),
        "Senior Relationship Manager - GL North\nKey Skills:\nCompliance",
    )
    assert job.role == "Senior Relationship Manager - GL North"
    titled = validate_job_profile(
        JobProfile(role="Area Sales Manager (B2B)", required_skills=["Compliance"]),
        "Area Sales Manager\nRole: Area Sales Manager (B2B)\nKey Skills:\nCompliance",
    )
    assert titled.role == "Area Sales Manager"
    kept = validate_job_profile(
        JobProfile(role="Relationship Manager", required_skills=["Compliance"]),
        "Senior Relationship Manager - GL North\nRole: Relationship Manager\nKey Skills:\nCompliance",
    )
    assert kept.role == "Senior Relationship Manager - GL North"


def test_repeated_skill_is_listed_once():
    profile = validate_candidate_profile(
        CandidateProfile(role="Software Engineer", skills=["Java", "Java", "Spring Boot"]),
        "Software Engineer. Skills: Java, Spring Boot.",
    )
    assert profile.skills == ["Java", "Spring Boot"]


def test_skill_normalization_does_not_require_an_exact_excerpt():
    profile = validate_candidate_profile(
        CandidateProfile(
            role="Software Engineer",
            skills=["Spring Boot", "React", "TypeScript"],
        ),
        "Software Engineer. Skills: Spring Boot 3, React/TypeScript.",
    )
    assert profile.skills == ["Spring Boot", "React", "TypeScript"]
    with pytest.raises(ExtractionValidationError, match="Kafka"):
        validate_candidate_profile(
            CandidateProfile(role="Software Engineer", skills=["Kafka"]),
            "Software Engineer. Skills: Spring Boot 3, React/TypeScript.",
        )


def test_responsibility_must_be_copied_from_the_source():
    profile = CandidateProfile(
        role="Software Engineer",
        responsibilities=["Managed microservices at scale."],
    )
    with pytest.raises(ExtractionValidationError, match="does not appear"):
        validate_candidate_profile(
            profile,
            "Software Engineer. Built REST APIs using Java and Spring Boot.",
        )


def test_empty_candidate_profile_is_rejected():
    with pytest.raises(ExtractionValidationError, match="empty candidate profile"):
        validate_candidate_profile(CandidateProfile(), "No title is written here.")


def test_job_placeholder_and_industry_label_are_rejected():
    with pytest.raises(ExtractionValidationError, match="placeholder"):
        validate_job_profile(
            JobProfile(role="Relationship Manager", preferred_skills=["None"]),
            "Relationship Manager\nKey Skills:\nCompliance",
        )
    with pytest.raises(ExtractionValidationError, match="industry"):
        validate_job_profile(
            JobProfile(role="Relationship Manager", required_skills=["Banking"]),
            "Relationship Manager\nIndustry: Banking\nKey Skills:\nCompliance",
        )


def test_job_responsibilities_must_be_strings_and_role_must_be_grounded():
    with pytest.raises(ExtractionValidationError, match="list of strings"):
        validate_job_profile(
            JobProfile.model_construct(
                role="Relationship Manager",
                required_skills=[],
                preferred_skills=[],
                responsibilities=[1],
            ),
            "Relationship Manager",
        )
    grounded = validate_job_profile(
        JobProfile(
            role="Senior Relationship Manager - GL North",
            required_skills=["Compliance"],
            responsibilities=["Conduct village surveys and prospecting in selected villages."],
        ),
        "Senior Relationship Manager - GL North\nKey Skills:\nCompliance\n"
        "Conduct village surveys and prospecting in selected villages.",
    )
    assert grounded.responsibilities[0].startswith("Conduct village surveys")


def test_slash_and_parentheses_stay_inside_a_skill_phrase():
    source = "Fluency in the regional language (Hindi/English)"
    assert validate_skill_against_source("Fluency in the regional language (Hindi/English)", source)
    profile = validate_job_profile(
        JobProfile(
            role="Area Sales Manager",
            required_skills=["Fluency in the regional language (Hindi/English)"],
        ),
        "Area Sales Manager\n" + source,
    )
    assert profile.required_skills == ["Fluency in the regional language (Hindi/English)"]


def test_slash_delimited_technologies_and_aliases():
    assert validate_skill_against_source("CI/CD", "Experience with CI/CD pipelines.")
    assert validate_skill_against_source("React", "Experience with React/TypeScript.")
    assert validate_skill_against_source("TypeScript", "Experience with React/TypeScript.")
    assert validate_skill_against_source("C/C++", "Skills: C/C++")
    assert validate_skill_against_source("Node.js", "Built services with Node.js")
    assert validate_skill_against_source("OAuth 2.0", "Implemented OAuth 2.0")
    assert validate_skill_against_source("AWS/Azure", "Cloud: AWS/Azure")
    assert validate_skill_against_source("Spring Boot", "Spring Boot 3")
    assert validate_skill_against_source("Spring Boot 3", "Spring Boot")
    assert validate_skill_against_source("React", "React.js")
    assert validate_skill_against_source("React.js", "React")
    assert validate_skill_against_source("React", "ReactJS")
    assert validate_skill_against_source("PostgreSQL", "Postgres")
    assert validate_skill_against_source("Postgres", "PostgreSQL")
    assert validate_skill_against_source("JavaScript", "JS")
    assert validate_skill_against_source("JS", "JavaScript")
    assert not validate_skill_against_source("Kafka", "Experience with React/TypeScript.")


def test_multiword_skills_are_not_split_apart():
    source = "Key skills: Customer Relationship Management, Customer Service, Government Sales, Data Entry"
    for skill in (
        "Customer Relationship Management",
        "Customer Service",
        "Government Sales",
        "Data Entry",
    ):
        assert validate_skill_against_source(skill, source)


KEY_SKILLS_GLUED = (
    "Key Skills\n"
    "Sales\n"
    "UpsellingTargetOutbound SalesTelesalesRelationship ManagerRenewalsRetentionRevenue Generation"
)


def test_glued_job_board_skills_match_each_skill():
    source = KEY_SKILLS_GLUED
    for skill in (
        "Sales",
        "Upselling",
        "Target",
        "Outbound Sales",
        "Telesales",
        "Relationship Manager",
        "Renewals",
        "Retention",
        "Revenue Generation",
    ):
        assert validate_skill_against_source(skill, source), skill
    profile = validate_job_profile(
        JobProfile(role="Relationship Manager", required_skills=["Upselling", "Telesales", "Sales"]),
        "Relationship Manager\n" + source,
    )
    assert profile.required_skills == ["Upselling", "Telesales", "Sales"]


def test_fabricated_and_lookalike_skills_fail():
    assert not validate_skill_against_source("Kafka", "Experience with React and TypeScript.")
    assert not validate_skill_against_source("Java", "Experience with JavaScript.")
    assert not validate_skill_against_source("MongoDB", "Experience with PostgreSQL.")
    assert not validate_skill_against_source("RabbitMQ", "Experience with Kafka.")
    assert not validate_skill_against_source("Angular", "Experience with React.")
    assert not validate_skill_against_source("Django", "Experience with Spring Boot.")
    with pytest.raises(ExtractionValidationError, match="Kafka"):
        validate_candidate_profile(
            CandidateProfile(role="Software Engineer", skills=["Kafka"]),
            "Software Engineer. Experience with React and TypeScript.",
        )


def test_village_survey_responsibility_stays_extractive():
    source = "Conduct village surveys and do prospecting in selected villages."
    assert validate_job_profile(
        JobProfile(role="Area Sales Manager", responsibilities=[source]),
        "Area Sales Manager\n" + source,
    ).responsibilities == [source]
    with pytest.raises(ExtractionValidationError, match="does not appear"):
        validate_job_profile(
            JobProfile(
                role="Area Sales Manager",
                responsibilities=["Manage village customer acquisition."],
            ),
            "Area Sales Manager\n" + source,
        )


RAW_RESUME = """
Jordan Hale
jordan.hale@example.com | +91 98400 11022 | Bengaluru

Profile summary
Software engineer with 4 years of experience building backend services.

Technical skills
Java, Spring Boot 3, React/TypeScript, PostgreSQL, Docker, CI/CD

Work experience
Software Engineer, Northline Payments, 2022-present
Built REST APIs with Java and Spring Boot.
Maintained a React admin screen backed by PostgreSQL.

Associate System Engineer, Harbor Ledger, 2020-2022
Wrote Java services and Docker deployment notes.

Projects
Payments ledger: Spring Boot services and a React client.

Education
B.S. Computer Science, 2020
"""

RAW_ION_EXCHANGE_JD = """
Area Sales Manager
Ion Exchange
4.1 · 1,240 reviews
₹8-12 Lacs PA
Hyderabad, Telangana
Posted 2 days ago · 86 applicants
Apply
Continue with Google

Company description
Ion Exchange is a water treatment company. This about-company block is long portal text
and is duplicated again at the bottom. It mentions offices, awards, and history that are
not hiring requirements.

Role description
Own project sales and corporate sales for water treatment systems.
Conduct village surveys and do prospecting in selected villages.

Qualifications
Fluency in the regional language (Hindi/English)
Graduate in any discipline

Key skills
Customer Relationship Management
Customer Service
Government Sales
Corporate Sales
Water Treatment
Project Sales
Data Entry

About company
Ion Exchange builds water treatment plants. The same company description is repeated
here with footer text, an email careers@example.com, and a phone number +91 22 0000 0000.
"""


def test_raw_resume_and_job_board_paste_validate_without_cleaning():
    candidate = validate_candidate_profile(
        CandidateProfile(
            role="Software Engineer",
            years_of_experience=4,
            skills=["Java", "Spring Boot", "React", "TypeScript", "PostgreSQL", "CI/CD"],
            responsibilities=["Built REST APIs with Java and Spring Boot."],
        ),
        RAW_RESUME,
    )
    assert candidate.skills[1] == "Spring Boot"
    assert "Built REST APIs" in candidate.responsibilities[0]
    job = validate_job_profile(
        JobProfile(
            role="Area Sales Manager",
            required_skills=[
                "Fluency in the regional language (Hindi/English)",
                "Customer Relationship Management",
                "Water Treatment",
                "Data Entry",
            ],
            responsibilities=["Conduct village surveys and do prospecting in selected villages."],
        ),
        RAW_ION_EXCHANGE_JD,
    )
    assert job.role == "Area Sales Manager"
    assert "Hindi/English" in job.required_skills[0]
    assert job.responsibilities[0].startswith("Conduct village surveys")


def test_senior_relationship_manager_raw_posting_keeps_grounded_fields():
    profile = validate_job_profile(
        JobProfile(
            role="Relationship Manager",
            required_skills=["Compliance", "Customer Relationships", "Loans"],
            responsibilities=["Conduct village surveys and prospecting in selected villages."],
        ),
        RELATIONSHIP_MANAGER_JD,
    )
    assert profile.role == "Senior Relationship Manager - GL North"
    assert "Compliance" in profile.required_skills


def test_service_rejects_placeholder_output():
    service = LLMService(
        Settings(),
        job_chain=_Chain({"role": "Relationship Manager", "preferred_skills": ["N/A"]}),
    )
    with pytest.raises(ExtractionValidationError):
        service.extract_job_profile("Relationship Manager")
