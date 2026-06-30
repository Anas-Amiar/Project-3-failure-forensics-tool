"""
Typed input/output shapes for every step of the pipeline. Each step takes
one of these in and returns one of these out -- never raw dicts. This is
what makes tracing meaningful later: if a step's output doesn't match its
contract, that's a clean, attributable failure, not vague "something broke."
"""

from typing import Literal
from pydantic import BaseModel

DocumentType = Literal["contract", "invoice", "report", "correspondence", "unknown"]


class RawDocument(BaseModel):
    doc_id: str
    text: str


class ExtractedEntities(BaseModel):
    doc_id: str
    names: list[str]
    dates: list[str]
    amounts: list[str]
    key_terms: list[str]
    confidence: float  # 1-5 self-reported confidence, set by the (mock) extraction step


class ClassificationResult(BaseModel):
    doc_id: str
    doc_type: DocumentType
    confidence: float


class SummaryResult(BaseModel):
    doc_id: str
    summary: str
    confidence: float


class StepOutcome(BaseModel):
    """Generic wrapper so the orchestrator can treat every step the same way."""
    step_name: str
    success: bool
    output: dict | None = None
    error: str | None = None
    confidence: float | None = None


class Span(BaseModel):
    """One step's execution record inside a trace -- the unit tracing is built from."""
    step_name: str
    input_summary: str   # short human-readable description of what went in
    output_summary: str  # short human-readable description of what came out
    confidence: float    # 1-5, self-reported by the step
    status: Literal["success", "failed"]
    error: str | None = None


class Trace(BaseModel):
    """The full record of one document's run through the pipeline."""
    trace_id: str
    doc_id: str
    spans: list[Span] = []
    final_status: Literal["success", "failure", "degraded"] = "success"
    final_output: str | None = None
