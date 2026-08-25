from langgraph_agent_lab.metrics import ScenarioMetric, metric_from_state, summarize_metrics
from langgraph_agent_lab.report import render_report
from langgraph_agent_lab.state import make_event


def test_metric_from_state_success() -> None:
    state = {
        "scenario_id": "S",
        "route": "simple",
        "final_answer": "ok",
        "events": [
            make_event("intake", "completed", "ok"),
            make_event("answer", "completed", "ok"),
        ],
        "errors": [],
        "approval": None,
    }
    metric = metric_from_state(state, expected_route="simple", approval_required=False)
    assert metric.success is True
    assert metric.nodes_visited == 2


def test_metric_from_state_route_mismatch() -> None:
    state = {
        "scenario_id": "S",
        "route": "tool",
        "final_answer": "ok",
        "events": [],
        "errors": [],
        "approval": None,
    }
    metric = metric_from_state(state, expected_route="simple", approval_required=False)
    assert metric.success is False


def test_summarize_metrics() -> None:
    m1 = metric_from_state(
        {
            "scenario_id": "1",
            "route": "simple",
            "final_answer": "ok",
            "events": [],
            "errors": [],
            "approval": None,
        },
        "simple",
        False,
    )
    m2 = metric_from_state(
        {
            "scenario_id": "2",
            "route": "tool",
            "final_answer": None,
            "events": [],
            "errors": [],
            "approval": None,
        },
        "tool",
        False,
    )
    report = summarize_metrics([m1, m2])
    assert report.total_scenarios == 2
    assert 0 <= report.success_rate <= 1


def test_metric_captures_latency_retries_approval_and_string_errors() -> None:
    state = {
        "scenario_id": "risky",
        "route": "risky",
        "final_answer": "completed",
        "events": [
            {"node": "retry"},
            {"node": "approval"},
            "malformed-event",
        ],
        "errors": ["timeout", 503],
        "approval": None,
    }

    metric = metric_from_state(state, "risky", True, latency_ms=42)

    assert metric.success is True
    assert metric.retry_count == 1
    assert metric.interrupt_count == 1
    assert metric.approval_observed is True
    assert metric.latency_ms == 42
    assert metric.errors == ["timeout", "503"]


def test_summarize_metrics_records_real_resume_result() -> None:
    item = ScenarioMetric(scenario_id="S", success=True, expected_route="simple")

    report = summarize_metrics([item], resume_success=True)

    assert report.resume_success is True


def test_render_report_contains_metrics_and_escapes_dynamic_cells() -> None:
    item = ScenarioMetric(
        scenario_id="S|01",
        success=False,
        expected_route="tool",
        actual_route="error",
        latency_ms=12,
        errors=["line one\nline two"],
    )
    report = summarize_metrics([item])

    markdown = render_report(report)

    assert "# Day 08 Lab Report" in markdown
    assert "S\\|01" in markdown
    assert "line one line two" in markdown
    assert "Persistence / recovery evidence" in markdown
