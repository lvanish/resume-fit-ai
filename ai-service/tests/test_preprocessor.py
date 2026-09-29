from app.services.input_preprocessor import (
    OMISSION_MARKER,
    InputPreprocessor,
    allocate_budget,
    compact_document,
    detect_job_sections,
    detect_resume_sections,
    fit_section,
)
from app.services.token_utils import count_tokens
from tests.test_token_utils import CharTokenizer

_RESUME_ALIASES = None


def _tokenizer():
    return CharTokenizer()


def test_resume_section_detection_is_case_insensitive():
    resume = """
Jane Doe
PROFESSIONAL SUMMARY
Backend engineer with API experience.

Technical Skills:
Java, Spring Boot

Work Experience
Built production services.

Education
BSc Computer Science
"""
    sections = detect_resume_sections(resume)
    assert [section.category for section in sections] == [
        "summary",
        "summary",
        "skills",
        "experience",
        "education",
    ]
    assert "Java, Spring Boot" in sections[2].body


def test_resume_without_headings_is_one_section():
    sections = detect_resume_sections("Jane Doe builds Java services and nothing else.")
    assert len(sections) == 1
    assert sections[0].category == "body"


def test_job_section_detection():
    job = """
Backend Engineer
About the Role
Build APIs for the payments platform.

Requirements
Java and PostgreSQL are required.

Preferred Skills
Docker is nice to have.

About the company
We are a fast-growing company with a great culture and many offices worldwide.
"""
    sections = detect_job_sections(job)
    categories = [section.category for section in sections]
    assert categories[0] == "role"
    assert "requirements" in categories
    assert "preferred" in categories
    assert categories[-1] == "other"


def test_job_without_headings_is_one_section():
    sections = detect_job_sections("Backend engineer who knows Java.")
    assert len(sections) == 1
    assert sections[0].category == "body"


def test_resume_prioritization_keeps_skills_over_a_long_project_list():
    resume = (
        "Skills\nJava, Spring Boot, PostgreSQL\n\n"
        "Projects\n" + ("Migrated a legacy billing workflow. " * 30)
    )
    compacted = compact_document(
        resume,
        80,
        _tokenizer(),
        aliases=_resume_aliases(),
        priorities=_resume_priorities(),
        preamble_category="summary",
        whole_category="body",
    )
    assert "Java, Spring Boot, PostgreSQL" in compacted
    assert count_tokens(compacted, _tokenizer()) <= 80
    assert compacted.count("Migrated") < resume.count("Migrated")


def test_jd_prioritization_keeps_requirements_over_company_text():
    job = (
        "About the company\n" + ("We are a market-leading employer with a global mission. " * 20) + "\n\n"
        "Requirements\nJava, Spring Boot, and PostgreSQL are required.\n"
    )
    compacted = compact_document(
        job,
        90,
        _tokenizer(),
        aliases=_jd_aliases(),
        priorities=_jd_priorities(),
        preamble_category="role",
        whole_category="body",
    )
    assert "Java, Spring Boot, and PostgreSQL are required." in compacted
    assert count_tokens(compacted, _tokenizer()) <= 90
    assert compacted.count("market-leading") < job.count("market-leading")


def test_budget_redistribution_gives_unused_resume_room_to_the_jd():
    resume_alloc, job_alloc = allocate_budget(100, resume_tokens=20, job_tokens=200)
    assert resume_alloc == 20
    assert job_alloc == 80
    assert resume_alloc + job_alloc == 100


def test_budget_split_when_both_documents_are_long():
    resume_alloc, job_alloc = allocate_budget(100, resume_tokens=400, job_tokens=400)
    assert resume_alloc == 55
    assert job_alloc == 45


def test_short_resume_is_not_compacted():
    prepared = InputPreprocessor().prepare_for_laya(
        "Java developer",
        "Backend engineer",
        _tokenizer(),
        content_budget=200,
    )
    assert prepared.resume == "Java developer"
    assert prepared.job_description == "Backend engineer"
    assert prepared.compacted is False
    assert prepared.final_resume_tokens + prepared.final_job_description_tokens <= 200


def test_long_resume_is_compacted_inside_the_budget():
    prepared = InputPreprocessor().prepare_for_laya(
        "Skills\nJava\n\nWork Experience\n" + ("Built APIs. " * 80),
        "Requirements\nJava",
        _tokenizer(),
        content_budget=120,
    )
    assert prepared.compacted
    assert "Java" in prepared.resume
    assert prepared.final_resume_tokens + prepared.final_job_description_tokens <= 120


def test_long_job_description_is_compacted_inside_the_budget():
    prepared = InputPreprocessor().prepare_for_laya(
        "Skills\nJava",
        "Requirements\nPostgreSQL\n\nAbout the company\n" + ("Great culture. " * 80),
        _tokenizer(),
        content_budget=120,
    )
    assert prepared.compacted
    assert "PostgreSQL" in prepared.job_description
    assert prepared.final_resume_tokens + prepared.final_job_description_tokens <= 120


def test_both_long_documents_stay_inside_the_budget():
    prepared = InputPreprocessor().prepare_for_laya(
        "Summary\nBackend engineer.\n\nWork Experience\n" + ("Owned services. " * 100),
        "Requirements\nJava and Spring Boot.\n\nAbout us\n" + ("Global team. " * 100),
        _tokenizer(),
        content_budget=160,
    )
    assert prepared.compacted
    assert "Backend engineer." in prepared.resume
    assert "Java and Spring Boot." in prepared.job_description
    assert prepared.final_resume_tokens + prepared.final_job_description_tokens <= 160


def test_fit_section_keeps_beginning_and_end_when_there_is_room():
    text = "START " + ("middle " * 40) + "END"
    fitted = fit_section(text, 80, _tokenizer())
    assert count_tokens(fitted, _tokenizer()) <= 80
    assert fitted.startswith("START")
    assert fitted.rstrip().endswith("END")
    assert OMISSION_MARKER in fitted


def _resume_aliases():
    from app.services.input_preprocessor import _RESUME_ALIASES

    return _RESUME_ALIASES


def _resume_priorities():
    from app.services.input_preprocessor import _RESUME_PRIORITY

    return _RESUME_PRIORITY


def _jd_aliases():
    from app.services.input_preprocessor import _JD_ALIASES

    return _JD_ALIASES


def _jd_priorities():
    from app.services.input_preprocessor import _JD_PRIORITY

    return _JD_PRIORITY
