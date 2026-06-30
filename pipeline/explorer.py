"""
Generates a static HTML "trace explorer": one page per document showing
its pipeline as color-coded steps, plus an index page linking all traces.
No server needed -- just open the HTML files in a browser.
"""

import os
from pipeline.models import Trace
from pipeline.analyzer import diagnose

REPORTS_DIR = os.path.join(os.path.dirname(__file__), "..", "reports", "html")

STATUS_COLOR = {
    "success": "#1a7f37",   # green
    "degraded": "#bf8700",  # yellow
    "failure": "#cf222e",   # red
}


def _span_color(span, is_root_cause: bool) -> str:
    if is_root_cause:
        return "#cf222e"  # red: this is where it actually broke
    if span.status == "failed":
        return "#bf8700"  # yellow: affected, but not the origin
    return "#1a7f37"  # green: healthy


def render_trace_page(trace: Trace) -> str:
    diagnosis = diagnose(trace)
    root_step = diagnosis.root_cause_step if diagnosis else None

    rows = []
    for span in trace.spans:
        color = _span_color(span, span.step_name == root_step)
        marker = " ← ROOT CAUSE" if span.step_name == root_step else ""
        rows.append(f"""
        <div style="border-left: 6px solid {color}; padding: 10px 16px; margin-bottom: 10px; background: #f6f8fa;">
            <strong>{span.step_name}{marker}</strong> — confidence {span.confidence}/5
            <div style="font-size: 13px; color: #555; margin-top: 4px;">In: {span.input_summary}</div>
            <div style="font-size: 13px; color: #555;">Out: {span.output_summary}</div>
            {f'<div style="font-size: 13px; color: #cf222e; margin-top: 4px;">{span.error}</div>' if span.error else ''}
        </div>
        """)

    evidence_block = ""
    if diagnosis:
        evidence_block = f"""
        <div style="background: #fff8c5; border: 1px solid #d4a72c; padding: 12px 16px; margin-top: 16px;">
            <strong>Root cause diagnosis:</strong> {diagnosis.failure_category} in '{diagnosis.root_cause_step}'<br>
            {diagnosis.evidence}
        </div>
        """

    return f"""
    <html><head><title>Trace {trace.trace_id}</title></head>
    <body style="font-family: -apple-system, sans-serif; max-width: 700px; margin: 40px auto;">
        <a href="index.html">&larr; back to all traces</a>
        <h2>Trace {trace.trace_id} — {trace.doc_id}</h2>
        <p>Status: <strong style="color: {STATUS_COLOR[trace.final_status]}">{trace.final_status.upper()}</strong></p>
        {''.join(rows)}
        {evidence_block}
        <p style="margin-top: 16px;"><strong>Final output:</strong> {trace.final_output}</p>
    </body></html>
    """


def render_index_page(traces: list[Trace]) -> str:
    rows = []
    for t in traces:
        color = STATUS_COLOR[t.final_status]
        rows.append(f"""
        <tr>
            <td><a href="trace_{t.trace_id}.html">{t.doc_id}</a></td>
            <td style="color: {color}; font-weight: bold;">{t.final_status}</td>
        </tr>
        """)
    return f"""
    <html><head><title>Trace Explorer</title></head>
    <body style="font-family: -apple-system, sans-serif; max-width: 700px; margin: 40px auto;">
        <h2>Failure Forensics — Trace Explorer</h2>
        <table style="width: 100%; border-collapse: collapse;">
            <tr><th style="text-align:left;">Document</th><th style="text-align:left;">Status</th></tr>
            {''.join(rows)}
        </table>
    </body></html>
    """


def build_explorer(traces: list[Trace]) -> str:
    os.makedirs(REPORTS_DIR, exist_ok=True)
    for t in traces:
        path = os.path.join(REPORTS_DIR, f"trace_{t.trace_id}.html")
        with open(path, "w") as f:
            f.write(render_trace_page(t))

    index_path = os.path.join(REPORTS_DIR, "index.html")
    with open(index_path, "w") as f:
        f.write(render_index_page(traces))
    return index_path


if __name__ == "__main__":
    from data.documents import SAMPLE_DOCUMENTS
    from pipeline.orchestrator import run_pipeline_with_trace

    traces = [run_pipeline_with_trace(d["doc_id"], d["text"]) for d in SAMPLE_DOCUMENTS]
    index_path = build_explorer(traces)
    print(f"Trace explorer built: {index_path}")
    print("Open it in a browser to view.")
