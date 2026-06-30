"""
Runs a document through all 4 steps while recording a full Trace: one
Span per step, capturing what went in, what came out, and the step's
self-reported confidence. This is what makes the pipeline "observable" --
every run leaves behind a complete, inspectable record.
"""

import json
import os
import sqlite3
import uuid

from pipeline.models import Span, Trace
from pipeline.steps import intake, extract_entities, classify_document, summarize_document

TRACES_DIR = os.path.join(os.path.dirname(__file__), "..", "reports", "traces")
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "reports", "traces.db")

LOW_CONFIDENCE_THRESHOLD = 2.5  # below this, a span is considered "degraded"


def _init_db() -> None:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS traces (
            trace_id TEXT PRIMARY KEY,
            doc_id TEXT,
            final_status TEXT,
            final_output TEXT
        )
    """)
    conn.commit()
    conn.close()


def run_pipeline_with_trace(doc_id: str, text: str) -> Trace:
    """Runs all 4 steps on one document and returns a full Trace."""
    trace_id = str(uuid.uuid4())[:8]
    spans: list[Span] = []

    # Step 1: intake
    doc = intake(doc_id, text)
    spans.append(Span(
        step_name="intake",
        input_summary=f"{len(text)} raw characters",
        output_summary=f"doc_id={doc.doc_id}",
        confidence=5.0,  # intake can't really fail in this mock pipeline
        status="success",
    ))

    # Step 2: extraction
    entities = extract_entities(doc)
    spans.append(Span(
        step_name="extraction",
        input_summary=f"raw text ({len(doc.text)} chars)",
        output_summary=f"names={entities.names}, dates={entities.dates}, amounts={entities.amounts}",
        confidence=entities.confidence,
        status="success" if entities.confidence >= LOW_CONFIDENCE_THRESHOLD else "failed",
        error=None if entities.confidence >= LOW_CONFIDENCE_THRESHOLD
              else "Low-confidence extraction: missing or inconsistent entities",
    ))

    # Step 3: classification
    classification = classify_document(doc, entities)
    spans.append(Span(
        step_name="classification",
        input_summary=f"names={entities.names}, dates={entities.dates}, key_terms={entities.key_terms}",
        output_summary=f"doc_type={classification.doc_type}",
        confidence=classification.confidence,
        status="success" if classification.confidence >= LOW_CONFIDENCE_THRESHOLD else "failed",
        error=None if classification.confidence >= LOW_CONFIDENCE_THRESHOLD
              else "Low-confidence classification: document type is ambiguous",
    ))

    # Step 4: summarization
    summary = summarize_document(doc, entities, classification)
    spans.append(Span(
        step_name="summarization",
        input_summary=f"doc_type={classification.doc_type}, entities confidence={entities.confidence}",
        output_summary=summary.summary,
        confidence=summary.confidence,
        status="success" if summary.confidence >= LOW_CONFIDENCE_THRESHOLD else "failed",
        error=None if summary.confidence >= LOW_CONFIDENCE_THRESHOLD
              else "Low-confidence summary: likely built on incomplete upstream data",
    ))

    failed_count = sum(1 for s in spans if s.status == "failed")
    if failed_count == 0:
        final_status = "success"
    elif failed_count == len(spans):
        final_status = "failure"
    else:
        final_status = "degraded"

    trace = Trace(
        trace_id=trace_id,
        doc_id=doc_id,
        spans=spans,
        final_status=final_status,
        final_output=summary.summary,
    )
    _save_trace(trace)
    return trace


def _save_trace(trace: Trace) -> None:
    os.makedirs(TRACES_DIR, exist_ok=True)
    path = os.path.join(TRACES_DIR, f"{trace.trace_id}.json")
    with open(path, "w") as f:
        json.dump(trace.model_dump(), f, indent=2)

    _init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT OR REPLACE INTO traces (trace_id, doc_id, final_status, final_output) VALUES (?, ?, ?, ?)",
        (trace.trace_id, trace.doc_id, trace.final_status, trace.final_output),
    )
    conn.commit()
    conn.close()


def load_trace(trace_id: str) -> Trace:
    path = os.path.join(TRACES_DIR, f"{trace_id}.json")
    with open(path) as f:
        return Trace(**json.load(f))


if __name__ == "__main__":
    from data.documents import SAMPLE_DOCUMENTS

    print("=== Running pipeline with full tracing ===\n")
    for d in SAMPLE_DOCUMENTS:
        trace = run_pipeline_with_trace(d["doc_id"], d["text"])
        print(f"trace_id={trace.trace_id}  doc_id={trace.doc_id}  status={trace.final_status}")
        for span in trace.spans:
            marker = "OK " if span.status == "success" else "FAIL"
            print(f"    [{marker}] {span.step_name:15s} confidence={span.confidence}")
        print()
