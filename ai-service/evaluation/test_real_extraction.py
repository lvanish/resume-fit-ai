"""Extract profiles from the fintech resume and Bajaj Finance job description.

Prints the validated profiles, model name, and extraction times.
Does not print the source text and does not score the pair.
"""

from __future__ import annotations

import time

from app.config import get_settings
from app.models.candidate_profile import CandidateProfile
from app.models.job_profile import JobProfile
from app.services.llm_service import LLMService
from app.services.profile_extraction_service import ProfileExtractionService
from app.services.requirement_builder import build_matching_context

RESUME = (
    "Full-stack engineer with 3+ years shipping production features for a fintech platform "
    "and Airbus aircraft-data administration, from the React/TypeScript UI through Java Spring "
    "Boot services to the data store.\n\n"
    "Improves systems after release with faster data access, event-driven flows, CI/CD, "
    "containers, production monitoring and caching.\n\n"
    "Built an agentic assistant using LangChain, LangGraph and LLMs over fintech policy and "
    "product documents, with RAG retrieval and multi-step tool calling.\n\n"
    "Software Engineer at Abans Finserv from Jun 2025 to Aug 2026. Worked with React, Spring "
    "Boot, MySQL, Kafka, RabbitMQ, GraphQL, Redis, Docker, Azure, AWS, Kubernetes, CI/CD, "
    "JUnit, Mockito, Prometheus and Grafana.\n\n"
    "Associate System Engineer at Airbus from Aug 2022 to Apr 2024. Built the TDM Admin Tool "
    "using React, Spring Boot, PostgreSQL and SQLite. Improved API latency by 20% and retrieval "
    "time by 30% through query optimization, indexes and Redis caching.\n\n"
    "Technical Intern at DRDO from Jun 2021 to Aug 2021. Worked with React, TypeScript, REST "
    "APIs, MongoDB, Node.js, Docker and CI/CD."
)

JOB_DESCRIPTION = (
    "Senior Relationship Manager - GL North\n\n"
    "Bajaj Finance\n\n"
    "Job Summary:\n"
    "Responsible for doing village surveys, getting new customers, doing CGT, house "
    "verification and income assessment, quality sourcing, collections and recoveries, and "
    "maintaining healthy customer relationships on the ground.\n\n"
    "Responsibilities:\n"
    "Conduct village surveys and prospecting in selected villages.\n"
    "Source new customers and form JLG groups.\n"
    "Promote financial literacy amongst potential borrowers.\n"
    "Collect information needed for sourcing and validate documents.\n"
    "Coordinate with branch management for approvals and disbursements.\n"
    "Plan customer center meetings.\n"
    "Resolve customer queries and promote cross-sell opportunities.\n"
    "Manage customer portfolio.\n"
    "Ensure collections and recoveries are completed on schedule.\n"
    "Carry out end-use monitoring of loans.\n"
    "Maintain customer relationships and compliance.\n"
    "Prepare daily reports.\n"
    "Perform reconciliation with Credit and Operations.\n\n"
    "Role: Relationship Manager\n"
    "Industry: Banking / BFSI\n"
    "Employment Type: Full Time, Permanent\n\n"
    "Key Skills:\n"
    "Compliance\n"
    "Customer Relationships\n"
    "Loans\n"
    "LOS\n"
    "Relationship Manager\n"
    "Data Entry\n"
    "Customer Queries"
)


def main() -> None:
    settings = get_settings()
    service = ProfileExtractionService(LLMService(settings))
    print(f"model={settings.llm_model}", flush=True)

    started = time.perf_counter()
    candidate = service.extract_candidate_profile(RESUME)
    resume_ms = (time.perf_counter() - started) * 1000.0
    print(f"resume_extraction_ms={resume_ms:.0f}", flush=True)
    print(f"candidate_validation={'succeeded' if isinstance(candidate, CandidateProfile) else 'failed'}")
    print("CandidateProfile:")
    print(candidate.model_dump_json(indent=2))

    started = time.perf_counter()
    job = service.extract_job_profile(JOB_DESCRIPTION)
    job_ms = (time.perf_counter() - started) * 1000.0
    print(f"job_extraction_ms={job_ms:.0f}", flush=True)
    print(f"job_validation={'succeeded' if isinstance(job, JobProfile) else 'failed'}")
    print("JobProfile:")
    print(job.model_dump_json(indent=2))

    context = build_matching_context(candidate, job)
    print(f"requirement_count={len(context.requirements)}", flush=True)
    print("Requirements:")
    for requirement in context.requirements:
        print(f"- {requirement.category.value}: {requirement.name}")


if __name__ == "__main__":
    main()
