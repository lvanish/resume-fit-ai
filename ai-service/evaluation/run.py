"""Run the synthetic evaluation set through the real Laya pipeline.

Usage, from ai-service:

    python -m evaluation.run

Writes evaluation/results.json. Resume and job-description text are not stored.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from app.config import get_settings
from app.services.laya_service import LayaService
from evaluation.probes import (
    BACKEND_JD,
    EXPERIENCE_VERSIONS,
    FRONTEND_MISMATCH_RESUME,
    LONG_JD,
    LONG_RESUME,
    MARKETING_JD,
    NORMAL_JD,
    NORMAL_RESUME,
    ORDER_A,
    ORDER_B,
    ORDER_JD,
    PARAPHRASE_A,
    PARAPHRASE_B,
    PARAPHRASE_JD,
    REQUIREMENTS_JD,
    RESPONSIBILITY_JD,
    RESPONSIBILITY_VERSIONS,
    SHORT_JD,
    SHORT_RESUME,
    SKILL_VERSIONS,
    STRONG_BACKEND_JD,
    STRONG_BACKEND_RESUME,
)
from evaluation.stats import (
    CATEGORIES,
    CLOSE_SCORE_GAP,
    LONG_DOCUMENT_GAP,
    MATERIAL_MISMATCH_GAP,
    assert_no_document_text,
    category_summary,
    dimension_averages,
    monotonicity_flags,
    pair_flag,
    repeatability_summary,
    score_distribution,
    separation_flags,
)

ROOT = Path(__file__).resolve().parent
DATASET_PATH = ROOT / "dataset.json"
SMOKE_PATH = ROOT / "smoke_case.json"
RESULTS_PATH = ROOT / "results.json"


def main() -> None:
    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    smoke = json.loads(SMOKE_PATH.read_text(encoding="utf-8"))
    _validate_dataset(dataset)
    service = LayaService(get_settings())

    dataset_records = [
        _score(
            service,
            case["id"],
            case["resume"],
            case["jobDescription"],
            expectedCategory=case["expectedCategory"],
        )
        for case in dataset
    ]
    monotonicity = _monotonicity(service)
    negative = _negative(service)
    irrelevant = _pair(
        service,
        "requirements-only",
        STRONG_BACKEND_RESUME,
        REQUIREMENTS_JD,
        "requirements-plus-marketing",
        STRONG_BACKEND_RESUME,
        MARKETING_JD,
    )
    order = _pair(
        service,
        "summary-skills-experience-education",
        ORDER_A,
        ORDER_JD,
        "education-experience-skills-summary",
        ORDER_B,
        ORDER_JD,
    )
    paraphrase = _pair(
        service,
        "developed-rest-apis",
        PARAPHRASE_A,
        PARAPHRASE_JD,
        "built-backend-http-services",
        PARAPHRASE_B,
        PARAPHRASE_JD,
    )
    repeatability = [
        _score(service, f"repeat-{index}", smoke["resume"], smoke["jobDescription"])
        for index in range(1, 6)
    ]
    long_input = _long_input(service)
    regression = _score(service, smoke["id"], smoke["resume"], smoke["jobDescription"])

    flags = _flags(dataset_records, monotonicity, negative, irrelevant, order, paraphrase, long_input)
    payload = {
        "dataset": dataset_records,
        "monotonicity": monotonicity,
        "negative": negative,
        "irrelevant_text": irrelevant,
        "order_invariance": order,
        "paraphrase": paraphrase,
        "repeatability": repeatability,
        "long_input": long_input,
        "regression": regression,
        "summary": _summary(dataset_records, repeatability, flags),
    }
    assert_no_document_text(payload)
    RESULTS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _print_summary(payload)
    if any(not item["within_budget"] for item in long_input):
        raise SystemExit("A long-input case exceeded the Laya state budget.")


def _validate_dataset(dataset: list[dict]) -> None:
    if len(dataset) < 15:
        raise SystemExit(f"Evaluation dataset has {len(dataset)} cases; at least 15 are required.")
    seen = set()
    for case in dataset:
        if case["id"] in seen:
            raise SystemExit(f"Duplicate case id {case['id']}")
        seen.add(case["id"])
        if case["expectedCategory"] not in CATEGORIES:
            raise SystemExit(f"{case['id']} has unknown category {case['expectedCategory']}")
        if not str(case["resume"]).strip() or not str(case["jobDescription"]).strip():
            raise SystemExit(f"{case['id']} has blank text")


def _score(service: LayaService, case_id: str, resume: str, job_description: str, **extra) -> dict:
    details = service.score(resume, job_description)
    if details.state_tokens > details.state_token_budget:
        raise SystemExit(f"{case_id} state tokens exceeded the checkpoint budget")
    record = {
        "id": case_id,
        **details.analysis.as_dict(),
        "elapsed_ms": round(details.elapsed_ms, 1),
        "compacted": details.compacted,
        "state_tokens": details.state_tokens,
        "state_token_budget": details.state_token_budget,
        "original_resume_tokens": details.original_resume_tokens,
        "final_resume_tokens": details.final_resume_tokens,
        "original_job_description_tokens": details.original_job_description_tokens,
        "final_job_description_tokens": details.final_job_description_tokens,
        "within_budget": details.state_tokens <= details.state_token_budget,
    }
    record.update(extra)
    print(
        f"{case_id}: score={record['final_score']} "
        f"skills={record['required_skills']:.2f} experience={record['experience']:.2f} "
        f"responsibilities={record['responsibilities']:.2f} "
        f"preferred={record['preferred_skills']:.2f} alignment={record['overall_alignment']:.2f} "
        f"elapsed_ms={record['elapsed_ms']:.0f} compacted={record['compacted']} "
        f"state={record['state_tokens']}/{record['state_token_budget']}",
        flush=True,
    )
    return record


def _monotonicity(service: LayaService) -> list[dict]:
    records = []
    for step, resume in SKILL_VERSIONS.items():
        records.append(
            _score(service, f"skills-{step}", resume, BACKEND_JD, series="required_skills", step=step)
        )
    for step, resume in EXPERIENCE_VERSIONS.items():
        records.append(
            _score(service, f"experience-{step}", resume, BACKEND_JD, series="experience", step=step)
        )
    for step, resume in RESPONSIBILITY_VERSIONS.items():
        records.append(
            _score(
                service,
                f"responsibilities-{step}",
                resume,
                RESPONSIBILITY_JD,
                series="responsibilities",
                step=step,
            )
        )
    return records


def _negative(service: LayaService) -> dict:
    strong = _score(service, "negative-strong-backend", STRONG_BACKEND_RESUME, STRONG_BACKEND_JD)
    mismatch = _score(service, "negative-frontend-mismatch", FRONTEND_MISMATCH_RESUME, STRONG_BACKEND_JD)
    return {"strong_backend": strong, "frontend_mismatch": mismatch}


def _pair(
    service: LayaService,
    left_id: str,
    left_resume: str,
    left_job: str,
    right_id: str,
    right_resume: str,
    right_job: str,
) -> dict:
    return {
        "left": _score(service, left_id, left_resume, left_job),
        "right": _score(service, right_id, right_resume, right_job),
    }


def _long_input(service: LayaService) -> list[dict]:
    short = _score(service, "long-short", SHORT_RESUME, SHORT_JD, variant="short")
    shortened = _score(
        service,
        "long-shortened-equivalent",
        NORMAL_RESUME,
        NORMAL_JD,
        variant="shortened_equivalent",
    )
    expanded = _score(service, "long-expanded", LONG_RESUME, LONG_JD, variant="long")
    return [short, shortened, expanded]


def _flags(dataset, monotonicity, negative, irrelevant, order, paraphrase, long_input) -> list[str]:
    flags = list(separation_flags(category_summary(dataset)))
    for series_name in ("required_skills", "experience", "responsibilities"):
        series = [item for item in monotonicity if item["series"] == series_name]
        flags.extend(monotonicity_flags(series))
    strong_score = negative["strong_backend"]["final_score"]
    mismatch_score = negative["frontend_mismatch"]["final_score"]
    if mismatch_score > strong_score - MATERIAL_MISMATCH_GAP:
        flags.append(
            "frontend mismatch "
            f"{mismatch_score} is not at least {MATERIAL_MISMATCH_GAP} below "
            f"the strong backend score {strong_score}"
        )
    for label, pair in (
        ("irrelevant marketing text", irrelevant),
        ("section order", order),
        ("paraphrase", paraphrase),
    ):
        note = pair_flag(
            label,
            pair["left"]["final_score"],
            pair["right"]["final_score"],
            CLOSE_SCORE_GAP,
        )
        if note:
            flags.append(note)
    by_variant = {item["variant"]: item for item in long_input}
    note = pair_flag(
        "long document versus shortened equivalent",
        by_variant["long"]["final_score"],
        by_variant["shortened_equivalent"]["final_score"],
        LONG_DOCUMENT_GAP,
    )
    if note:
        flags.append(note)
    for item in long_input:
        if not item["within_budget"]:
            flags.append(f"{item['id']} exceeded the state budget")
    return flags


def _summary(dataset_records, repeatability, flags) -> dict:
    scores = [int(record["final_score"]) for record in dataset_records]
    return {
        "category_summary": category_summary(dataset_records),
        "dataset_distribution": score_distribution(scores),
        "dimension_averages": dimension_averages(dataset_records),
        "repeatability": repeatability_summary([int(item["final_score"]) for item in repeatability]),
        "flags": flags,
        "weights_changed": False,
    }


def _print_summary(payload: dict) -> None:
    summary = payload["summary"]
    print("\n== category ranges ==")
    for row in summary["category_summary"]:
        print(
            f"{row['category']}: count={row['count']} min={row['min']} "
            f"max={row['max']} average={row['average']}"
        )
    distribution = summary["dataset_distribution"]
    print("\n== dataset distribution ==")
    print(
        f"lowest={distribution['lowest']} highest={distribution['highest']} "
        f"average={distribution['average']} median={distribution['median']} "
        f"std={distribution['standard_deviation']}"
    )
    print(f"bands={distribution['bands']}")
    print("\n== dimension averages (0-4) ==")
    for name, value in summary["dimension_averages"].items():
        print(f"{name}: {value}")
    repeatability = summary["repeatability"]
    print("\n== repeatability ==")
    print(
        f"runs={repeatability['runs']} min={repeatability['min']} max={repeatability['max']} "
        f"average={repeatability['average']} range={repeatability['range']}"
    )
    print("\n== flags ==")
    if summary["flags"]:
        for flag in summary["flags"]:
            print(f"- {flag}")
    else:
        print("none")
    print(f"\nwrote {RESULTS_PATH}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
