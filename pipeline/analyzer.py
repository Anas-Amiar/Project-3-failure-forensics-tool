"""
The backward trace analyzer: given a failed/degraded trace, walks the
spans in order and finds the first one that actually went wrong -- the
root cause. Everything after it is just downstream damage from that one
broken step.
"""

from pydantic import BaseModel
from pipeline.models import Trace, Span

FailureCategory = str  # kept loose so new categories can be added without a schema change

FAILURE_CATEGORIES = {
    "extraction": "Extraction Failure",
    "classification": "Misclassification",
    "summarization": "Propagation Error",
    "intake": "Intake Failure",
}


class RootCauseDiagnosis(BaseModel):
    trace_id: str
    doc_id: str
    root_cause_step: str
    failure_category: FailureCategory
    evidence: str
    confidence_at_root: float


def diagnose(trace: Trace) -> RootCauseDiagnosis | None:
    """Returns the root cause diagnosis, or None if the trace had no failures."""
    failed_spans = [s for s in trace.spans if s.status == "failed"]
    if not failed_spans:
        return None

    # the root cause is the FIRST step (in pipeline order) that failed --
    # not necessarily the lowest-confidence one, since later steps often
    # inherit and compound an earlier step's problem
    root_span = failed_spans[0]

    category = FAILURE_CATEGORIES.get(root_span.step_name, "Unknown Failure")

    # build a plain-English evidence chain: what the root step produced,
    # and how that propagated to every step after it
    downstream_steps = [s.step_name for s in trace.spans
                         if trace.spans.index(s) > trace.spans.index(root_span)
                         and s.status == "failed"]

    evidence = (
        f"Step '{root_span.step_name}' produced low-confidence output "
        f"(confidence={root_span.confidence}): {root_span.output_summary}. "
    )
    if root_span.error:
        evidence += f"Reason: {root_span.error}. "
    if downstream_steps:
        evidence += f"This propagated forward and caused failures in: {', '.join(downstream_steps)}."
    else:
        evidence += "No downstream steps were affected."

    return RootCauseDiagnosis(
        trace_id=trace.trace_id,
        doc_id=trace.doc_id,
        root_cause_step=root_span.step_name,
        failure_category=category,
        evidence=evidence,
        confidence_at_root=root_span.confidence,
    )


if __name__ == "__main__":
    from data.documents import SAMPLE_DOCUMENTS
    from pipeline.orchestrator import run_pipeline_with_trace

    print("=== Backward trace analysis ===\n")
    for d in SAMPLE_DOCUMENTS:
        trace = run_pipeline_with_trace(d["doc_id"], d["text"])
        diagnosis = diagnose(trace)
        if diagnosis is None:
            print(f"{d['doc_id']}: no failures detected\n")
            continue
        print(f"{d['doc_id']}: ROOT CAUSE = {diagnosis.root_cause_step} ({diagnosis.failure_category})")
        print(f"  {diagnosis.evidence}\n")
