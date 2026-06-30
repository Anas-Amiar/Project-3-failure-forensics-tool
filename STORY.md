# Failure Forensics Tool for AI Pipelines — the pitch

*A 2-minute walkthrough for presenting this project in an interview.*

## The 30-second version

"When a multi-step AI pipeline produces a bad final output, most teams have no idea
which step actually broke — they just see garbage at the end. I built an observability
layer that traces every intermediate step of a pipeline, walks backward through the
trace when something fails, and pinpoints the exact step where the problem
originated, with evidence. It's essentially a scoped-down LangSmith — and every
diagnosed failure automatically becomes a permanent regression test, so the system
gets smarter about its own weak points over time."

## The problem, in plain terms

Imagine a document-processing pipeline: extract entities, classify the document type,
write a summary. If the final summary is wrong, *why*? Was extraction confused? Did
classification guess the wrong document type? Did summarization just write a bad
sentence from otherwise-fine data? Without tracing, you're debugging blind — re-reading
logs, guessing, re-running the whole thing with print statements.

## The idea

Treat the pipeline like a stack trace, not a black box. Record what every step
received and produced. When the output is bad, walk the steps *in order* and find the
first one that actually degraded — that's the root cause. Everything after it is just
the symptom propagating forward.

## How I built it (in order, and why that order)

1. **The 4-step pipeline** (`pipeline/steps.py`) — intake, extraction, classification,
   summarization, each a clean, isolated function with a strict Pydantic input/output
   contract. This had to come first and be strictly typed — if the steps are
   spaghetti, tracing is meaningless.

2. **Realistic failure modes, built deliberately** (`data/documents.py`) — a document
   with no dates anywhere, an invoice with mixed currency symbols, a document
   ambiguous between two categories, a near-empty document. Without real failures,
   there's nothing for a forensics tool to actually demonstrate.

3. **The tracing layer** (`pipeline/orchestrator.py`) — every pipeline run produces a
   `Trace`: one `Span` per step, recording exactly what went in, what came out, and a
   self-reported confidence score. Saved as both human-readable JSON and indexed in
   SQLite for queryability.

4. **The backward trace analyzer** (`pipeline/analyzer.py`) — the actual diagnostic
   engine. Walks the spans in pipeline order and returns the *first* failed step, not
   the worst-looking one — because a late step often just inherited an earlier step's
   problem and shouldn't take the blame for it.

5. **The visual trace explorer** (`pipeline/explorer.py`) — a static HTML report per
   document: each step shown as a colored block (green/yellow/red), the root-cause
   step called out explicitly, with the evidence chain underneath.

6. **The feedback-to-eval loop** (`pipeline/feedback.py`) — every diagnosed failure
   becomes a permanent test case in a growing dataset, plus analytics on which step
   fails most often across all documents processed so far.

## The result

Running 8 documents (4 clean, 4 deliberately broken) through the pipeline:

| Document | Root cause found | Category |
|---|---|---|
| Missing-date contract | summarization | Propagation Error (inherited missing date) |
| Mixed-currency invoice | extraction | Extraction Failure (confused by two currencies) |
| Near-empty document | extraction | Extraction Failure (cascaded through 2 more steps) |

The analyzer correctly distinguished "the problem started here" (extraction, in the
currency case) from "the problem only became visible here" (summarization, in the
missing-date case) — which is the actual hard part of root-causing a pipeline failure.

The failure analytics also produced a genuinely useful signal: across all flagged
failures, **extraction was the most common root cause** — exactly the kind of
"where should we invest engineering effort" answer a product team would want.

## What I'd highlight if asked "what was the hardest design decision?"

Deciding the root cause is the *first* failed step, not the *lowest-confidence* one.
My first instinct was to just report whichever span had the worst score — but that
often pointed at a downstream step that was simply inheriting bad input from
upstream, which would send an engineer chasing the wrong code. Walking forward and
stopping at the first failure finds the true origin, not just the loudest symptom.

I also caught a real bug while building the demo data: my regex-based name extractor
flagged "This Agreement" as a person's name, because it just matches two consecutive
capitalized words. That's a textbook Extraction Hallucination — and a good reminder
that even "obviously correct" heuristics need to be run against real input before you
trust them.

## What I'd build next

- Swap the mock regex steps for real LLM calls, and add LLM-as-judge confidence
  scoring instead of rule-based confidence
- A live, clickable React trace explorer instead of static HTML
- Automatic regression re-runs: periodically re-process the accumulated eval dataset
  against the current pipeline and track whether known failures have been fixed

## Companion projects

This project pairs with [Model Regression Detection System](
https://github.com/Anas-Amiar/Project-1-model-regression-detector) (catches quality
regressions on prompt/model changes) and [LLM Cost Autopilot](
https://github.com/Anas-Amiar/Project-2-llm-cost-autopilot) (optimizes cost per
request). Together the three represent the core levers an AI engineering team
manages in production: correctness, cost, and observability.
