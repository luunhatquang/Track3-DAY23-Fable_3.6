"""Markdown report generation from observed scenario metrics."""

from __future__ import annotations

from pathlib import Path

from .metrics import MetricsReport


def render_report(metrics: MetricsReport) -> str:
    """Render a complete lab report from metrics data.

    Values in the scenario table are generated from the run; architecture and
    analysis sections document the frozen team contract without claiming untested
    extension work.
    """
    rows = []
    for item in metrics.scenario_metrics:
        errors = "; ".join(item.errors) if item.errors else "—"
        values = (
            item.scenario_id,
            item.expected_route,
            item.actual_route or "—",
            "yes" if item.success else "no",
            str(item.nodes_visited),
            str(item.retry_count),
            str(item.interrupt_count),
            str(item.latency_ms),
            errors,
        )
        rows.append("| " + " | ".join(_table_cell(value) for value in values) + " |")

    scenario_rows = "\n".join(rows) or "| — | — | — | no | 0 | 0 | 0 | 0 | — |"
    state_rows = "\n".join(
        (
            "| `messages`, `tool_results`, `errors`, `events` | append | Preserve audit history |",
            "| `route`, `risk_level`, `attempt`, `evaluation_result` | overwrite "
            "| Control routing |",
            "| `pending_question`, `proposed_action`, `approval`, `final_answer` | overwrite "
            "| Hold the current outcome |",
            "| `thread_id`, `scenario_id`, `query`, `max_attempts` | initialized/overwrite "
            "| Identify one execution |",
        )
    )
    return f"""# Day 08 Lab Report

## 1. Team / student

- Name: TODO
- Repo/commit: TODO
- Date: TODO

## 2. Architecture

The workflow uses a typed LangGraph state and eleven bounded nodes. Requests pass through
`intake` and `classify`, then follow the `simple`, `tool`, `missing_info`, `risky`, or `error`
route. Every terminal route passes through `finalize` before `END`. Tool failures use a bounded
retry loop, while risky actions require an approval decision before the tool can run.

```mermaid
flowchart LR
    START --> intake --> classify
    classify --> answer
    classify --> tool --> evaluate
    classify --> clarify
    classify --> risky_action --> approval
    classify --> retry
    evaluate --> answer
    evaluate --> retry
    approval --> tool
    approval --> clarify
    retry --> tool
    retry --> dead_letter
    answer --> finalize --> END
    clarify --> finalize
    dead_letter --> finalize
```

## 3. State schema and reducers

| Field group | Reducer | Purpose |
|---|---|---|
{state_rows}

## 4. Metrics summary

| Metric | Value |
|---|---:|
| Total scenarios | {metrics.total_scenarios} |
| Success rate | {metrics.success_rate:.2%} |
| Average nodes visited | {metrics.avg_nodes_visited:.2f} |
| Total retries | {metrics.total_retries} |
| Total approvals/interrupts | {metrics.total_interrupts} |
| Persistence resume demonstrated | {"yes" if metrics.resume_success else "no"} |

## 5. Scenario results

| Scenario | Expected | Actual | Success | Nodes | Retries | Approvals | Latency (ms) | Errors |
|---|---|---|---:|---:|---:|---:|---:|---|
{scenario_rows}

## 6. Failure analysis

1. **Transient or malformed tool output:** `evaluate` marks missing or error output for retry.
   `retry` increments the attempt counter and routing sends exhausted work to `dead_letter`,
   preventing an infinite loop or a false successful answer.
2. **Risky action without valid approval:** risky work is prepared but not executed before the
   approval node. A rejected, missing, or malformed decision routes to clarification instead of
   performing a side effect.

## 7. Persistence / recovery evidence

Resume/history evidence must be captured from an actual MemorySaver or SQLite run. Current run
status: **{"demonstrated" if metrics.resume_success else "not yet demonstrated"}**. Record the
thread ID, checkpoint count, test command, and restart/reopen result here before submission.

## 8. Extension work

SQLite persistence, real HITL resume, the Streamlit operations console, and graph evidence should
only be marked complete after their integration tests or demo evidence pass.

## 9. Improvement plan

Prioritize provider timeout handling, durable connection lifecycle management, richer tracing,
and automated clean-environment/Docker smoke tests. Production side effects should also use
idempotency keys so replay after an interrupt cannot duplicate an action.
"""


def _table_cell(value: str) -> str:
    """Escape dynamic text for a single-line Markdown table cell."""
    return value.replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def write_report(metrics: MetricsReport, output_path: str | Path) -> None:
    """Write the rendered report to a file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_report(metrics), encoding="utf-8")
