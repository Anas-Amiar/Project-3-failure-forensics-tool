"""
The feedback-to-eval loop: every diagnosed failure becomes a permanent
test case in a growing eval dataset, plus analytics on which step fails
most often. This is what turns one-off debugging into a system that gets
more valuable (and the pipeline more battle-tested) over time.
"""

import json
import os
from collections import Counter

from pipeline.models import Trace
from pipeline.analyzer import diagnose, RootCauseDiagnosis

EVAL_DATASET_PATH = os.path.join(os.path.dirname(__file__), "..", "reports", "eval_dataset.json")


def _load_dataset() -> list[dict]:
    if not os.path.exists(EVAL_DATASET_PATH):
        return []
    with open(EVAL_DATASET_PATH) as f:
        return json.load(f)


def _save_dataset(cases: list[dict]) -> None:
    os.makedirs(os.path.dirname(EVAL_DATASET_PATH), exist_ok=True)
    with open(EVAL_DATASET_PATH, "w") as f:
        json.dump(cases, f, indent=2)


def flag_failure(trace: Trace, original_text: str) -> RootCauseDiagnosis | None:
    """
    Simulates a human flagging a bad output and confirming the root cause
    diagnosis. Appends a new eval case to the growing dataset.
    """
    diagnosis = diagnose(trace)
    if diagnosis is None:
        return None

    cases = _load_dataset()
    cases.append({
        "doc_id": trace.doc_id,
        "trace_id": trace.trace_id,
        "original_text": original_text,
        "failing_step": diagnosis.root_cause_step,
        "failure_category": diagnosis.failure_category,
        "evidence": diagnosis.evidence,
        "flagged_by": "human-confirmed",  # in a real system, a human clicks "confirm"
    })
    _save_dataset(cases)
    return diagnosis


def failure_analytics() -> dict:
    """Returns stats on the accumulated eval dataset: most common failure
    types, which step fails most often."""
    cases = _load_dataset()
    if not cases:
        return {"total_cases": 0}

    by_step = Counter(c["failing_step"] for c in cases)
    by_category = Counter(c["failure_category"] for c in cases)

    return {
        "total_cases": len(cases),
        "failures_by_step": dict(by_step.most_common()),
        "failures_by_category": dict(by_category.most_common()),
        "most_common_failure_point": by_step.most_common(1)[0][0],
    }


if __name__ == "__main__":
    from data.documents import SAMPLE_DOCUMENTS
    from pipeline.orchestrator import run_pipeline_with_trace

    # reset the dataset for a clean demo run
    _save_dataset([])

    print("=== Flagging failures and building the eval dataset ===\n")
    for d in SAMPLE_DOCUMENTS:
        trace = run_pipeline_with_trace(d["doc_id"], d["text"])
        diagnosis = flag_failure(trace, d["text"])
        if diagnosis:
            print(f"Flagged {d['doc_id']}: {diagnosis.failure_category} at '{diagnosis.root_cause_step}'")

    print("\n=== Failure analytics ===")
    stats = failure_analytics()
    print(f"Total flagged cases:     {stats['total_cases']}")
    print(f"Failures by step:        {stats['failures_by_step']}")
    print(f"Failures by category:    {stats['failures_by_category']}")
    print(f"Most common failure point: {stats['most_common_failure_point']}")
