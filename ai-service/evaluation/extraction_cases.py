"""Synthetic extraction cases. These are fictional and are not real resumes."""

from __future__ import annotations

SOFTWARE_ENGINEER_RESUME = """
Jordan Hale
Software Engineer
Professional Summary
Software engineer with 4 years of experience building backend services.
Technical Skills
Java, Spring Boot, React, PostgreSQL, Docker, Kubernetes
Work Experience
Software Engineer, Northline Payments, 2022-present
- Built REST APIs with Java and Spring Boot.
- Maintained a React admin screen backed by PostgreSQL.
Associate System Engineer, Harbor Ledger, 2020-2022
- Wrote Java services and Docker deployment notes.
Education
B.S. Computer Science, 2020
"""

RELATIONSHIP_MANAGER_JD = """
Senior Relationship Manager - GL North
About the role
Own a portfolio of commercial banking clients in the GL North region.

Required Qualifications
- 6 years of relationship management in commercial banking.
- Experience with credit proposals, deposit growth, and loan collection follow-up.
- Proven customer acquisition in a branch or regional market.

Responsibilities
- Manage client relationships and review credit requests.
- Grow deposits and coordinate loan collection with the credit team.
- Prepare call reports for the regional head.

Preferred Qualifications
- Series 7 is a plus.
- Experience with treasury products is preferred.

About the company
We are a retail and commercial bank. This posting does not ask for software engineering.
"""

STRONG_BACKEND_RESUME = """
Priya Shah
Professional Summary
Backend engineer with 6 years of experience.
Technical Skills
Java, Spring Boot, PostgreSQL, Kafka
Work Experience
Senior Backend Engineer, Northwind, 2019-present
- Designed Spring Boot APIs and PostgreSQL schemas.
- Operated Kafka consumers for payment events.
Education
B.S. Computer Science, 2018
"""

FRONTEND_RESUME = """
Lina Ortiz
Professional Summary
Frontend engineer with 4 years of experience.
Technical Skills
React, TypeScript, CSS
Work Experience
Frontend Engineer, Paperplane, 2021-present
- Built React screens and CSS layouts.
- Wrote TypeScript component tests.
Education
B.A. Design and Technology, 2021
"""

FULL_STACK_RESUME = """
Sofia Alvarez
Professional Summary
Full stack engineer with 5 years of experience.
Technical Skills
Java, Spring Boot, React, PostgreSQL
Work Experience
Full Stack Engineer, Cedar Health, 2019-present
- Built Spring Boot APIs and the React client that calls them.
Education
B.S. Information Systems, 2019
"""

RELATIONSHIP_MANAGER_RESUME = """
Taylor Brooks
Professional Summary
Relationship manager with 8 years in commercial banking.
Work Experience
Senior Relationship Manager, GL North, Summit Bank, 2018-present
- Managed a book of commercial clients.
- Led customer acquisition campaigns and deposit reviews.
- Coordinated loan collection follow-ups with credit officers.
Education
B.A. Business Administration, 2016
"""

GENERAL_SOFTWARE_RESUME = """
Elena Cho
Professional Summary
Software engineer with 7 years of experience on internal business applications.
Technical Skills
Java, SQL, Git
Work Experience
Software Engineer, Fieldstone Systems, 2017-present
- Built internal tools for operations teams.
- Wrote SQL reports and supported releases.
Education
B.S. Computer Science, 2017
"""

EVENT_DRIVEN_RESUME = """
Work Experience
Software Engineer, 2021-present
- Worked on event-driven architecture for internal notifications.
"""

KAFKA_RESUME = """
Work Experience
Software Engineer, 2021-present
- Built Kafka consumers and producers for order events.
"""

PREFERRED_KAFKA_JD = """
Backend Engineer
Requirements
Experience with Java and Spring Boot is required.
Preferred Qualifications
Kafka is preferred.
"""

REQUIRED_JAVA_JD = """
Backend Engineer
Requirements
Experience with Java and Spring Boot is required.
Responsibilities
Build and support backend services.
"""

QUALITY_CASES = [
    {
        "id": "strong-backend",
        "resume": STRONG_BACKEND_RESUME,
        "present_skills": ["Java", "Spring Boot", "PostgreSQL", "Kafka"],
        "absent_skills": ["React"],
    },
    {
        "id": "frontend",
        "resume": FRONTEND_RESUME,
        "present_skills": ["React", "TypeScript", "CSS"],
        "absent_skills": ["Java", "Spring Boot", "Kafka"],
    },
    {
        "id": "full-stack",
        "resume": FULL_STACK_RESUME,
        "present_skills": ["Java", "Spring Boot", "React", "PostgreSQL"],
        "absent_skills": ["Kafka"],
    },
    {
        "id": "relationship-manager",
        "resume": RELATIONSHIP_MANAGER_RESUME,
        "present_skills": [],
        "absent_skills": ["Java", "Spring Boot", "React", "Kafka"],
        "present_responsibilities": ["customer acquisition", "loan collection"],
    },
    {
        "id": "general-software",
        "resume": GENERAL_SOFTWARE_RESUME,
        "present_skills": ["Java", "SQL"],
        "absent_skills": ["Kafka", "React", "Spring Boot"],
    },
]

GUARDRAIL_CASES = [
    {
        "id": "event-driven-no-kafka",
        "kind": "resume",
        "text": EVENT_DRIVEN_RESUME,
        "absent_skills": ["Kafka"],
    },
    {
        "id": "kafka-consumers",
        "kind": "resume",
        "text": KAFKA_RESUME,
        "present_skills": ["Kafka"],
    },
    {
        "id": "kafka-preferred",
        "kind": "job",
        "text": PREFERRED_KAFKA_JD,
        "preferred_skills": ["Kafka"],
        "absent_required_skills": ["Kafka"],
        "required_skills": ["Java", "Spring Boot"],
    },
    {
        "id": "java-spring-required",
        "kind": "job",
        "text": REQUIRED_JAVA_JD,
        "required_skills": ["Java", "Spring Boot"],
    },
]


def _contains(values: list[str], expected: str) -> bool:
    needle = expected.casefold()
    return any(needle in value.casefold() for value in values)


def candidate_flags(case: dict, skills: list[str], responsibilities: list[str]) -> list[str]:
    flags = []
    for skill in case.get("present_skills", []):
        if not _contains(skills, skill):
            flags.append(f"missing skill {skill}")
    for skill in case.get("absent_skills", []):
        if _contains(skills, skill):
            flags.append(f"unexpected skill {skill}")
    for phrase in case.get("present_responsibilities", []):
        if not _contains(responsibilities, phrase):
            flags.append(f"missing responsibility {phrase}")
    for phrase in case.get("absent_responsibilities", []):
        if _contains(responsibilities, phrase) or _contains(skills, phrase):
            flags.append(f"unexpected claim {phrase}")
    return flags


def job_flags(case: dict, required: list[str], preferred: list[str]) -> list[str]:
    flags = []
    for skill in case.get("required_skills", []):
        if not _contains(required, skill):
            flags.append(f"missing required skill {skill}")
    for skill in case.get("preferred_skills", []):
        if not _contains(preferred, skill):
            flags.append(f"missing preferred skill {skill}")
        if _contains(required, skill):
            flags.append(f"{skill} was marked required instead of preferred")
    for skill in case.get("absent_required_skills", []):
        if _contains(required, skill):
            flags.append(f"{skill} should not be required")
    return flags
