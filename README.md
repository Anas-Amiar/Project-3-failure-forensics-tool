# Failure Forensics Tool for AI Pipelines

An observability layer for multi-step AI pipelines. When a pipeline's final output is
bad, this tool traces every intermediate step, identifies exactly *where* the failure
originated, categorizes why, and feeds confirmed failures back into a growing eval
dataset — a mini LangSmith/Braintrust, scoped to be buildable end to end.

## Why this exists

When a multi-step AI pipeline produces garbage, most teams have no idea which step
broke. This tool answers "where did this go wrong?" with evidence, not guessing.

## How it works

```
pipeline/
  models.py        Typed input/output for every step, plus Span/Trace shapes
  steps.py          The 4 pipeline steps: intake, extraction, classification, summarization
  orchestrator.py   Runs all 4 steps, records a full Trace, saves to JSON + SQLite
  analyzer.py       Backward trace analysis: finds the first failed step (the root cause)
  explorer.py       Generates a static HTML trace explorer (color-coded steps)
  feedback.py       Turns confirmed failures into permanent eval cases + analytics
  run.py            Quick sanity check: runs the raw steps with no tracing
data/
  documents.py      8 sample documents -- 4 clean, 4 deliberately built to break a step
reports/            Generated output (traces, HTML, eval dataset) -- gitignored
```

### The pipeline

```
Step 1: Intake          -- accept raw document text
Step 2: Extraction       -- pull out names, dates, amounts, key terms
Step 3: Classification   -- decide document type (contract/invoice/report/correspondence)
Step 4: Summarization    -- write a type-tailored one-line summary
```

Each step is a clean, isolated function with a strict Pydantic input/output contract.
That matters: if step 3's output doesn't match its contract, that's a clean,
attributable failure pinned to step 3 — not a vague "something broke somewhere."

### The flow for one document

```
run_pipeline_with_trace(doc_id, text)
  1. Run all 4 steps, recording a Span per step (input, output, confidence, status)
  2. Save the full Trace to reports/traces/<trace_id>.json + index it in SQLite
  3. diagnose(trace) walks the spans IN ORDER and returns the first failed step
     -- that's the root cause, everything after it is downstream damage
  4. build_explorer() renders an HTML page per trace, root cause highlighted in red
  5. flag_failure() turns a diagnosed failure into a permanent eval case
```

## Setup

```bash
git clone https://github.com/Anas-Amiar/Project-3-failure-forensics-tool.git
cd "Project 3 - failure-forensics-tool"
pip install -r requirements.txt

python3 -m pipeline.run            # sanity check: raw steps, no tracing
python3 -m pipeline.orchestrator   # full pipeline with tracing
python3 -m pipeline.analyzer       # root cause diagnosis for every document
python3 -m pipeline.explorer       # builds reports/html/index.html -- open it in a browser
python3 -m pipeline.feedback       # builds the eval dataset + failure analytics
```

Everything runs in **mock mode** by default — regex/keyword-based steps instead of
real LLM calls, so the whole pipeline runs with no API key. The mock logic has real,
predictable blind spots (no dates, mixed currencies, ambiguous categories, empty
documents) so there's always something genuine for the forensics tool to find.

## The sample documents

`data/documents.py` has 8 documents: 4 clean, 4 deliberately built to break one
specific step:

| doc | Designed failure | Where it's caught |
|---|---|---|
| doc_005 | contract with no dates anywhere | summarization (falls back to "unspecified date") |
| doc_006 | invoice with mixed $/€ amounts | extraction itself (confused by two currencies) |
| doc_007 | ambiguous contract-vs-correspondence wording | classification (low confidence, not a hard failure) |
| doc_008 | near-empty document ("ok.") | full cascade: extraction → classification → summarization |

## Failure taxonomy

| Category | What it means |
|---|---|
| Extraction Failure | the extraction step itself produced low-confidence or inconsistent entities |
| Misclassification | the document type was guessed with low confidence |
| Propagation Error | an earlier step's gap (e.g. missing date) only became visible once a later step tried to use it |

## Architecture decisions

**Why find the *first* failed step, not the lowest-confidence one?**
A later step can look worse than the step that actually caused the problem, simply
because it inherited bad input. Walking forward through the trace and stopping at the
first failure finds the true origin, not just the most visibly broken symptom.

**Why a static HTML explorer instead of a live server?**
Zero setup to view — open one file in a browser. A live React/Streamlit explorer is a
natural v2, but the static version demonstrates the same diagnostic value without the
extra infrastructure.

**Why mock mode by default?**
So the entire pipeline — steps, tracing, root cause analysis, the HTML explorer, the
feedback loop — can be built, run, and demoed with zero API keys and zero cost, while
still producing organic, realistic failures to diagnose.

## What's deliberately out of scope for v1

- Real LLM calls for extraction/classification/summarization (mock-only for now)
- A live, clickable trace UI (currently static HTML)
- Automatic regression re-runs of the growing eval dataset against pipeline changes
- LLM-as-judge confidence scoring (current confidence is rule-based, not model-based)
