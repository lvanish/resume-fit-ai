"""Score short, normal, and long documents with the real typed-decisions model.

Scores are printed, not asserted. The check is that long inputs complete and the
state sent to Laya stays within the checkpoint budget.
"""

from app.config import get_settings
from app.services.laya_service import LayaService

SHORT_RESUME = (
    "Software Engineer with 4 years of experience building backend services using "
    "Java, Spring Boot, REST APIs, PostgreSQL and Docker. Developed and maintained "
    "production APIs and worked on database optimization."
)
SHORT_JOB = (
    "Backend Engineer. Requires 4+ years of experience, Java, Spring Boot, REST APIs "
    "and PostgreSQL. Experience with Docker is preferred. Kafka and AWS are also preferred."
)

NORMAL_RESUME = """
Alex Rivera
Professional Summary
Backend engineer with 6 years of experience designing REST APIs, relational data models, and production Java services.

Technical Skills
Java, Spring Boot, REST APIs, PostgreSQL, SQL, Docker, JUnit, Git, Linux

Work Experience
Senior Software Engineer, Northwind Payments, 2021-present
- Designed and maintained Spring Boot APIs used by billing and account services.
- Improved PostgreSQL queries and added indexes that reduced slow-report latency.
- Wrote integration tests and supported on-call incident response.

Software Engineer, Harbor Logistics, 2018-2021
- Built internal REST services for shipment tracking.
- Migrated a batch job to a scheduled Spring service.
- Partnered with analysts on data extracts from PostgreSQL.

Education
B.S. Computer Science, State University, 2018

Certifications
Oracle Certified Professional, Java SE
"""

NORMAL_JOB = """
Backend Engineer
About the Role
Build and operate customer account APIs for a payments product.

Requirements
5+ years of professional software experience.
Java, Spring Boot, REST APIs, and PostgreSQL.
Experience operating production services.

Responsibilities
Design API changes, review code, and improve database performance.
Participate in incident response and write automated tests.

Preferred Skills
Docker, Kafka, and AWS.
Experience with CI pipelines.

About the company
We build financial software for mid-size merchants and offer a collaborative engineering culture.
"""

LONG_RESUME = NORMAL_RESUME + "\nProjects\n" + (
    "Led a multi-quarter migration of billing workflows, documented rollback plans, "
    "and coordinated releases with operations. " * 80
)
LONG_JOB = NORMAL_JOB + "\nAbout the company\n" + (
    "Our company has offices in many cities, a long history, and a mission statement "
    "that describes culture, benefits, and community programs. " * 80
)


def _print_case(name: str, details) -> None:
    print(f"== {name} ==")
    print(f"score: {details.score}")
    print(f"elapsed_ms: {details.elapsed_ms:.0f}")
    print(
        "tokens: "
        f"resume {details.original_resume_tokens}->{details.final_resume_tokens}, "
        f"job {details.original_job_description_tokens}->{details.final_job_description_tokens}, "
        f"state {details.state_tokens}/{details.state_token_budget}, "
        f"compacted={details.compacted}"
    )
    if details.state_tokens > details.state_token_budget:
        raise SystemExit(f"{name} exceeded the Laya state budget")


def main() -> None:
    service = LayaService(get_settings())
    cases = [
        ("case 1 short", SHORT_RESUME, SHORT_JOB),
        ("case 2 normal", NORMAL_RESUME, NORMAL_JOB),
        ("case 3 long", LONG_RESUME, LONG_JOB),
    ]
    scored = []
    for name, resume, job in cases:
        details = service.score(resume, job)
        scored.append(details)
        _print_case(name, details)

    print("== stability (case 2 repeated) ==")
    repeats = [scored[1]]
    for index in range(2):
        details = service.score(NORMAL_RESUME, NORMAL_JOB)
        repeats.append(details)
        print(f"run {index + 2}: score={details.score} elapsed_ms={details.elapsed_ms:.0f}")
    scores = [item.score for item in repeats]
    print(f"stability_scores: {scores}")
    print(f"deterministic: {len(set(scores)) == 1}")


if __name__ == "__main__":
    main()
