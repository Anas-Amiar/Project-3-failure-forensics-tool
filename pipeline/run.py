"""
Quick sanity check: run every sample document through the 4 raw pipeline
steps (no tracing yet -- that's Phase 2) and print what each step produced.
This is just to confirm the steps themselves work and that our "broken"
documents actually produce visibly low-confidence output.
"""

from data.documents import SAMPLE_DOCUMENTS
from pipeline.steps import intake, extract_entities, classify_document, summarize_document


def run_one(doc_id: str, text: str) -> None:
    doc = intake(doc_id, text)
    entities = extract_entities(doc)
    classification = classify_document(doc, entities)
    summary = summarize_document(doc, entities, classification)

    print(f"--- {doc_id} ---")
    print(f"  Extraction:     confidence={entities.confidence}  dates={entities.dates}  amounts={entities.amounts}")
    print(f"  Classification: confidence={classification.confidence}  type={classification.doc_type}")
    print(f"  Summary:        confidence={summary.confidence}  text=\"{summary.summary}\"")
    print()


if __name__ == "__main__":
    for d in SAMPLE_DOCUMENTS:
        run_one(d["doc_id"], d["text"])
