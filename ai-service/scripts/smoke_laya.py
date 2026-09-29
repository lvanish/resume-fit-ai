"""Run one real typed-decisions scoring pass and print the internal answers.

This is a developer check. The HTTP API still returns only {"score": <int>}.
"""

from app.config import get_settings
from app.services.laya_service import QUESTION_IDS, LayaService

RESUME = (
    "Software Engineer with 4 years of experience building backend services using "
    "Java, Spring Boot, REST APIs, PostgreSQL and Docker. Developed and maintained "
    "production APIs and worked on database optimization."
)
JOB_DESCRIPTION = (
    "Backend Engineer. Requires 4+ years of experience, Java, Spring Boot, REST APIs "
    "and PostgreSQL. Experience with Docker is preferred. Kafka and AWS are also preferred."
)


def main() -> None:
    details = LayaService(get_settings()).score(RESUME, JOB_DESCRIPTION)
    print(f"model: {details.model}")
    print(
        "checkpoint limits: "
        f"max_len={details.max_len} head_max_len={details.head_max_len} "
        f"state_tokens={details.state_tokens} budget={details.state_token_budget}"
    )
    for question_id in QUESTION_IDS:
        print(f"{question_id}: {details.answers[question_id]}")
    print(f"match_score: {details.score}")
    print(f"elapsed_ms: {details.elapsed_ms:.0f}")
    print(
        "tokens: "
        f"resume {details.original_resume_tokens}->{details.final_resume_tokens}, "
        f"job {details.original_job_description_tokens}->{details.final_job_description_tokens}, "
        f"compacted={details.compacted}"
    )


if __name__ == "__main__":
    main()
