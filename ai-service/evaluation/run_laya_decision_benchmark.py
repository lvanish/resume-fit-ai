"""Run the noul versus neutral-choice benchmark. Does not change production scoring.

    python -m evaluation.run_laya_decision_benchmark
"""

from __future__ import annotations

import json
from pathlib import Path

from app.config import get_settings
from app.services.laya_decision_benchmark import (
    LayaDecisionBenchmark,
    controlled_cases,
    format_confusion,
    relationship_manager_cases,
    strong_backend_cases,
    summarize,
)

RESULTS_PATH = Path(__file__).resolve().parent / "laya_decision_benchmark.json"


def main() -> None:
    settings = get_settings()
    if settings.requirement_matching_enabled:
        print("REQUIREMENT_MATCHING_ENABLED is true. This benchmark still does not change the scorer.", flush=True)
    cases = [*controlled_cases(), *relationship_manager_cases(), *strong_backend_cases()]
    rows = LayaDecisionBenchmark(settings).run(cases)
    payload = {
        "requirement_matching_enabled": settings.requirement_matching_enabled,
        "controlled": summarize([row for row in rows if row["group"] == "controlled"]),
        "relationship_manager": summarize([row for row in rows if row["group"] == "relationship-manager"]),
        "strong_backend": summarize([row for row in rows if row["group"] == "strong-backend"]),
        "rows": rows,
    }
    RESULTS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    for name in ("controlled", "relationship_manager", "strong_backend"):
        summary = payload[name]
        print(
            f"{name}: noul_accuracy={summary['noul_accuracy']:.3f} "
            f"choice_accuracy={summary['choice_accuracy']:.3f} "
            f"noul_fp={summary['noul_false_positives']} choice_fp={summary['choice_false_positives']} "
            f"swap_changed={summary['label_swap_changed']}/{summary['count']}",
            flush=True,
        )
        print(format_confusion(f"{name} noul", summary["noul_confusion"]), flush=True)
        print(format_confusion(f"{name} choice", summary["choice_confusion"]), flush=True)
    for row in rows:
        print(
            f"{row['test_id']}: expected={row['expected']} noul={row['noul_result']} "
            f"p={row['noul_probability']} choice={row['choice_result']} "
            f"swapped={row['choice_swapped_result']} elapsed_ms={row['elapsed_ms']}",
            flush=True,
        )


if __name__ == "__main__":
    main()
