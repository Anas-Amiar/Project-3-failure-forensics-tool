"""
The 4 pipeline steps. Each one is a clean, isolated function: typed input
in, typed output out. Mock mode uses regex/keyword heuristics instead of
a real LLM call, so the whole pipeline runs with no API key -- and, just
as importantly, the mock logic has real, predictable blind spots that we
can deliberately trigger to produce failures for the tracing layer to find.
"""

import re
from pipeline.models import (
    RawDocument,
    ExtractedEntities,
    ClassificationResult,
    SummaryResult,
)


def intake(doc_id: str, text: str) -> RawDocument:
    """Step 1: wrap raw text as a document. In a real system this would
    parse a PDF/scan; here we just accept text directly."""
    return RawDocument(doc_id=doc_id, text=text.strip())


NAME_PATTERN = re.compile(r"\b([A-Z][a-z]+ [A-Z][a-z]+)\b")
DATE_PATTERN = re.compile(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|[A-Z][a-z]+ \d{1,2},? \d{4})\b")
AMOUNT_PATTERN = re.compile(r"(\$|€|£)\s?[\d,]+(\.\d{2})?")


def extract_entities(doc: RawDocument) -> ExtractedEntities:
    """Step 2: pull out names, dates, amounts, key terms using regex rules.
    This is the step most likely to fail silently -- e.g. a document with
    no dates at all, or amounts in mixed currencies."""
    text = doc.text

    names = NAME_PATTERN.findall(text)
    dates = DATE_PATTERN.findall(text)
    dates = [d if isinstance(d, str) else d[0] for d in dates]
    amount_strings = [text[m.start():m.end()] for m in re.finditer(AMOUNT_PATTERN, text)]
    currencies_found = {amt[0] for amt in AMOUNT_PATTERN.findall(text)}

    key_terms = [w for w in ["agreement", "invoice", "payment", "report", "findings",
                              "regards", "contract", "terms"] if w in text.lower()]

    # confidence drops when the extraction looks shaky -- this is what
    # the backward trace analyzer will key off of later
    confidence = 5.0
    if not dates:
        confidence -= 2.0  # no dates extracted is a red flag for contracts/invoices
    if len(currencies_found) > 1:
        confidence -= 1.5  # mixed currency symbols suggest extraction confusion
    if not names and not amount_strings:
        confidence -= 1.0
    confidence = max(1.0, confidence)

    return ExtractedEntities(
        doc_id=doc.doc_id,
        names=names,
        dates=dates,
        amounts=amount_strings,
        key_terms=key_terms,
        confidence=round(confidence, 1),
    )


CLASSIFICATION_KEYWORDS = {
    "contract": ["agreement", "terms and conditions", "party", "parties", "hereby"],
    "invoice": ["invoice", "amount due", "payment", "bill to"],
    "report": ["findings", "summary of results", "analysis", "report"],
    "correspondence": ["regards", "dear", "sincerely", "following up"],
}


def classify_document(doc: RawDocument, entities: ExtractedEntities):
    """Step 3: decide what kind of document this is, using keyword scoring.
    Ambiguous documents (matching two categories about equally) are a known
    failure mode here -- the classifier picks one but with low confidence."""
    text = doc.text.lower()
    scores = {}
    for doc_type, keywords in CLASSIFICATION_KEYWORDS.items():
        scores[doc_type] = sum(1 for kw in keywords if kw in text)

    best_type = max(scores, key=scores.get)
    best_score = scores[best_type]

    if best_score == 0:
        best_type = "unknown"
        confidence = 1.5
    else:
        # confidence reflects how dominant the winning category was
        sorted_scores = sorted(scores.values(), reverse=True)
        margin = sorted_scores[0] - (sorted_scores[1] if len(sorted_scores) > 1 else 0)
        confidence = min(5.0, 2.5 + margin)

    return ClassificationResult(doc_id=doc.doc_id, doc_type=best_type, confidence=round(confidence, 1))


def summarize_document(doc: RawDocument, entities: ExtractedEntities, classification) -> SummaryResult:
    """Step 4: produce a short summary tailored to the document type.
    This step inherits any upstream confusion -- if extraction missed the
    dates or classification guessed wrong, the summary will reflect that."""
    doc_type = classification.doc_type

    if doc_type == "contract":
        date_part = entities.dates[0] if entities.dates else "an unspecified date"
        parties = ", ".join(entities.names[:2]) if entities.names else "unspecified parties"
        summary = f"Contract between {parties}, dated {date_part}."
    elif doc_type == "invoice":
        amount_part = entities.amounts[0] if entities.amounts else "an unspecified amount"
        summary = f"Invoice for {amount_part}."
    elif doc_type == "report":
        summary = f"Report covering: {', '.join(entities.key_terms) or 'general findings'}."
    elif doc_type == "correspondence":
        names_part = entities.names[0] if entities.names else "an unspecified sender"
        summary = f"Correspondence from {names_part}."
    else:
        summary = "Unable to determine document type or summary."

    # if entities were missing key info, the summary itself flags low confidence
    confidence = min(entities.confidence, classification.confidence)
    if "unspecified" in summary:
        confidence = min(confidence, 2.0)

    return SummaryResult(doc_id=doc.doc_id, summary=summary, confidence=round(confidence, 1))
