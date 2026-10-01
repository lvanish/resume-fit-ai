"""Compare broad Laya scoring with requirement-level scoring.

Prints scores and internal probabilities. Does not save resume or job-description text.

    python -m evaluation.compare_scoring
"""

from __future__ import annotations

import json
from pathlib import Path

from app.config import get_settings
from app.models.candidate_profile import CandidateProfile
from app.models.job_profile import JobProfile
from app.models.requirement import Requirement, RequirementCategory
from app.services.laya_service import BroadLayaScoringService
from app.services.requirement_builder import build_requirements
from app.services.requirement_matching_service import RequirementMatchingService
from evaluation.test_real_extraction import JOB_DESCRIPTION, RESUME

RESULTS_PATH = Path(__file__).resolve().parent / "scoring_comparison.json"

BACKEND_JOB = JobProfile(
    role="Backend Engineer",
    minimum_years_experience=4,
    required_skills=["Java", "Spring Boot", "PostgreSQL", "REST"],
    preferred_skills=["Kafka", "Docker"],
    responsibilities=["Build and support backend services."],
)
STRONG_BACKEND = CandidateProfile(
    role="Backend Engineer",
    years_of_experience=6,
    skills=["Java", "Spring Boot", "PostgreSQL", "REST", "Kafka", "Docker"],
    responsibilities=[
        "Designed Spring Boot APIs and PostgreSQL schemas.",
        "Operated Kafka consumers for payment events.",
    ],
)
FRONTEND = CandidateProfile(
    role="Frontend Engineer",
    years_of_experience=4,
    skills=["React", "TypeScript", "CSS"],
    responsibilities=[
        "Built React screens and CSS layouts.",
        "Wrote TypeScript component tests.",
    ],
)
MIXED = CandidateProfile(
    role="Software Engineer",
    years_of_experience=7,
    skills=["Java", "SQL", "Git"],
    responsibilities=[
        "Built internal tools for operations teams.",
        "Wrote SQL reports and supported releases.",
    ],
)
SALES_CANDIDATE = CandidateProfile(
    role="Full-stack engineer",
    years_of_experience=3,
    skills=[
        "React",
        "TypeScript",
        "Spring Boot",
        "Java",
        "MySQL",
        "Kafka",
        "RabbitMQ",
        "Redis",
        "Docker",
        "Azure",
        "AWS",
        "Kubernetes",
        "LangChain",
        "LangGraph",
        "RAG retrieval",
        "PostgreSQL",
    ],
    responsibilities=[
        "Built an agentic assistant using LangChain, LangGraph and LLMs over fintech policy and product documents, with RAG retrieval and multi-step tool calling.",
        "Worked with React, Spring Boot, MySQL, Kafka, RabbitMQ, GraphQL, Redis, Docker, Azure, AWS, Kubernetes, CI/CD, JUnit, Mockito, Prometheus and Grafana.",
        "Built the TDM Admin Tool using React, Spring Boot, PostgreSQL and SQLite.",
    ],
)
SALES_JOB = JobProfile(
    role="Relationship Manager",
    required_skills=[
        "Compliance",
        "Customer Relationships",
        "Loans",
        "LOS",
        "Relationship Manager",
        "Data Entry",
        "Customer Queries",
    ],
    responsibilities=[
        "Conduct village surveys and prospecting in selected villages.",
        "Source new customers and form JLG groups.",
        "Promote financial literacy amongst potential borrowers.",
        "Collect information needed for sourcing and validate documents.",
        "Coordinate with branch management for approvals and disbursements.",
        "Plan customer center meetings.",
        "Resolve customer queries and promote cross-sell opportunities.",
        "Manage customer portfolio.",
        "Ensure collections and recoveries are completed on schedule.",
        "Carry out end-use monitoring of loans.",
        "Maintain customer relationships and compliance.",
        "Prepare daily reports.",
        "Perform reconciliation with Credit and Operations.",
    ],
)

BROAD_TEXT = {
    "strong-backend": (
        "Backend engineer with 6 years of experience. Skills: Java, Spring Boot, PostgreSQL, REST, Kafka, Docker. "
        "Designed Spring Boot APIs and PostgreSQL schemas. Operated Kafka consumers for payment events.",
        "Backend Engineer. Requires 4 years, Java, Spring Boot, PostgreSQL, and REST. "
        "Kafka and Docker are preferred. Build and support backend services.",
    ),
    "frontend-vs-backend": (
        "Frontend engineer with 4 years of experience. Skills: React, TypeScript, CSS. "
        "Built React screens and CSS layouts. Wrote TypeScript component tests.",
        "Backend Engineer. Requires 4 years, Java, Spring Boot, PostgreSQL, and REST. "
        "Kafka and Docker are preferred. Build and support backend services.",
    ),
    "sales-mismatch": (RESUME, JOB_DESCRIPTION),
    "mixed-software": (
        "Software engineer with 7 years of experience. Skills: Java, SQL, Git. "
        "Built internal tools for operations teams. Wrote SQL reports and supported releases.",
        "Backend Engineer. Requires 4 years, Java, Spring Boot, PostgreSQL, and REST. "
        "Kafka and Docker are preferred. Build and support backend services.",
    ),
}


def main() -> None:
    settings = get_settings()
    broad = BroadLayaScoringService(settings)
    matching = RequirementMatchingService(settings)
    profiles = {
        "strong-backend": (STRONG_BACKEND, BACKEND_JOB),
        "frontend-vs-backend": (FRONTEND, BACKEND_JOB),
        "sales-mismatch": (SALES_CANDIDATE, SALES_JOB),
        "mixed-software": (MIXED, BACKEND_JOB),
    }
    rows = []
    for case_id, (candidate, job) in profiles.items():
        resume, description = BROAD_TEXT[case_id]
        old_score = broad.calculate_match_score(resume, description)
        analysis = matching.match(candidate, job, build_requirements(job))
        row = {
            "case": case_id,
            "old_score": old_score,
            "new_score": analysis.final_score,
            "required_skill_score": round(analysis.required_skill_score, 4),
            "preferred_skill_score": round(analysis.preferred_skill_score, 4),
            "responsibility_score": round(analysis.responsibility_score, 4),
            "experience_score": analysis.experience_score,
            "role_score": analysis.role_score,
            "batch_count": analysis.batch_count,
            "batch_latency_ms": analysis.batch_latency_ms,
            "total_latency_ms": analysis.total_latency_ms,
            "requirements": [item.model_dump() for item in analysis.requirements],
        }
        rows.append(row)
        print(
            f"{case_id}: old_score={old_score} new_score={analysis.final_score} "
            f"batches={analysis.batch_count} total_ms={analysis.total_latency_ms}",
            flush=True,
        )

    probes = _binary_probes(matching)
    payload = {
        "cases": rows,
        "binary_probes": probes,
        "comparison": {
            "strong_backend_required_skill_score_gt_frontend": _score(rows, "strong-backend", "required_skill_score")
            > _score(rows, "frontend-vs-backend", "required_skill_score"),
            "strong_backend_final_score_gt_frontend": _score(rows, "strong-backend", "new_score")
            > _score(rows, "frontend-vs-backend", "new_score"),
            "strong_backend_final_score_gt_sales": _score(rows, "strong-backend", "new_score")
            > _score(rows, "sales-mismatch", "new_score"),
        },
    }
    RESULTS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print("comparison=" + json.dumps(payload["comparison"]), flush=True)
    _print_sales(rows)
    _print_probes(probes)


def _binary_probes(matching: RequirementMatchingService) -> list[dict]:
    probes = [
        (
            "kafka-explicit",
            CandidateProfile(
                role="Software Engineer",
                skills=["Kafka"],
                responsibilities=["Built Kafka consumers and producers."],
            ),
            "Kafka",
        ),
        (
            "kafka-event-driven",
            CandidateProfile(
                role="Software Engineer",
                skills=[],
                responsibilities=["Worked on event-driven services."],
            ),
            "Kafka",
        ),
        (
            "react-explicit",
            CandidateProfile(
                role="Frontend Engineer",
                skills=["React"],
                responsibilities=["Developed React applications."],
            ),
            "React",
        ),
        (
            "spring-against-react",
            CandidateProfile(
                role="Frontend Engineer",
                skills=["React"],
                responsibilities=["Developed React applications."],
            ),
            "Spring Boot",
        ),
    ]
    reported = []
    for name, candidate, skill in probes:
        job = JobProfile(role="Engineer", required_skills=[skill])
        analysis = matching.match(
            candidate,
            job,
            [Requirement(name=skill, category=RequirementCategory.REQUIRED_SKILL)],
        )
        probability = next(item.probability_yes for item in analysis.requirements if item.requirement == skill)
        reported.append({"probe": name, "requirement": skill, "probability_yes": probability})
        print(f"probe {name}: {skill}={probability}", flush=True)
    return reported


def _score(rows: list[dict], case_id: str, field: str):
    return next(row[field] for row in rows if row["case"] == case_id)


def _print_sales(rows: list[dict]) -> None:
    sales = next(row for row in rows if row["case"] == "sales-mismatch")
    print(
        "sales "
        f"requirements={len(sales['requirements'])} batches={sales['batch_count']} "
        f"required_skill_score={sales['required_skill_score']} "
        f"responsibility_score={sales['responsibility_score']} "
        f"role_score={sales['role_score']} experience_score={sales['experience_score']} "
        f"preferred_skill_score={sales['preferred_skill_score']} final_score={sales['new_score']}",
        flush=True,
    )
    for item in sales["requirements"]:
        print(
            f"  {item['category']}: {item['requirement']} probability_yes={item['probability_yes']} decision={item['decision']}",
            flush=True,
        )


def _print_probes(probes: list[dict]) -> None:
    by_name = {item["probe"]: item["probability_yes"] for item in probes}
    print(
        "probe_relations "
        f"kafka_explicit_gt_event_driven={by_name['kafka-explicit'] > by_name['kafka-event-driven']} "
        f"react_gt_spring={by_name['react-explicit'] > by_name['spring-against-react']}",
        flush=True,
    )


if __name__ == "__main__":
    main()
