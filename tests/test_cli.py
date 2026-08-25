import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from langgraph_agent_lab.cli import app


class FakeGraph:
    def invoke(self, state: dict[str, Any], config: object) -> dict[str, Any]:
        if state["scenario_id"] == "S3":
            raise RuntimeError("provider unavailable")
        return {
            **state,
            "route": "simple",
            "final_answer": "ok",
            "events": [{"node": "answer"}, {"node": "finalize"}],
        }

    def get_state_history(self, config: object) -> list[object]:
        return [object()]


def _write_scenarios(path: Path) -> None:
    rows = [
        {
            "id": f"S{index}",
            "query": f"Question {index}",
            "expected_route": "simple",
        }
        for index in range(6)
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")


def test_run_scenarios_writes_report_and_preserves_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scenarios = tmp_path / "scenarios.jsonl"
    metrics = tmp_path / "metrics.json"
    report = tmp_path / "report.md"
    config = tmp_path / "config.yaml"
    _write_scenarios(scenarios)
    config.write_text(
        f"scenarios_path: {scenarios}\n"
        "checkpointer: sqlite\n"
        f"database_url: {tmp_path / 'checkpoints.sqlite'}\n"
        f"report_path: {report}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("langgraph_agent_lab.cli.build_checkpointer", lambda *args: object())
    monkeypatch.setattr("langgraph_agent_lab.cli.build_graph", lambda checkpointer: FakeGraph())

    result = CliRunner().invoke(
        app,
        ["run-scenarios", "--config", str(config), "--output", str(metrics)],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(metrics.read_text(encoding="utf-8"))
    assert payload["total_scenarios"] == 6
    assert payload["resume_success"] is True
    assert payload["scenario_metrics"][3]["success"] is False
    assert "RuntimeError: provider unavailable" in payload["scenario_metrics"][3]["errors"]
    assert all(item["latency_ms"] >= 1 for item in payload["scenario_metrics"])
    assert report.is_file()


def test_run_scenarios_rejects_non_mapping_config(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text("- invalid\n- config\n", encoding="utf-8")

    result = CliRunner().invoke(
        app,
        ["run-scenarios", "--config", str(config), "--output", str(tmp_path / "out.json")],
    )

    assert result.exit_code != 0
    assert "Config must be a YAML mapping" in result.output


def test_validate_metrics_requires_six_scenarios(tmp_path: Path) -> None:
    metrics = tmp_path / "metrics.json"
    metrics.write_text(
        json.dumps(
            {
                "total_scenarios": 0,
                "success_rate": 0,
                "avg_nodes_visited": 0,
                "total_retries": 0,
                "total_interrupts": 0,
                "resume_success": False,
                "scenario_metrics": [],
            }
        ),
        encoding="utf-8",
    )

    result = CliRunner().invoke(app, ["validate-metrics", "--metrics", str(metrics)])

    assert result.exit_code != 0
    assert "Expected at least 6 scenarios" in result.output
