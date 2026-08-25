"""CLI for the lab."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from time import perf_counter
from typing import Annotated

import typer
import yaml
from dotenv import load_dotenv
from langchain_core.runnables import RunnableConfig

from .graph import build_graph
from .metrics import MetricsReport, metric_from_state, summarize_metrics, write_metrics
from .persistence import build_checkpointer
from .report import write_report
from .scenarios import load_scenarios
from .state import initial_state

app = typer.Typer(no_args_is_help=True)


@app.command("run-scenarios")
def run_scenarios(
    config: Annotated[Path, typer.Option("--config")],
    output: Annotated[Path, typer.Option("--output")],
) -> None:
    """Run all grading scenarios and write metrics JSON."""
    load_dotenv()
    cfg = _load_config(config)
    scenarios = load_scenarios(_required_string(cfg, "scenarios_path"))
    checkpointer_kind = _optional_string(cfg, "checkpointer") or "memory"
    database_url = _optional_string(cfg, "database_url")
    checkpointer = build_checkpointer(checkpointer_kind, database_url)
    try:
        graph = build_graph(checkpointer=checkpointer)
    except Exception as exc:
        raise typer.BadParameter(f"Unable to build graph: {exc}") from exc

    metrics = []
    run_configs: list[RunnableConfig] = []
    for scenario in scenarios:
        state = initial_state(scenario)
        run_config: RunnableConfig = {"configurable": {"thread_id": state["thread_id"]}}
        run_configs.append(run_config)
        started = perf_counter()
        try:
            final_state = graph.invoke(state, config=run_config)
        except Exception as exc:
            final_state = dict(state)
            final_state["errors"] = [*state.get("errors", []), f"{type(exc).__name__}: {exc}"]
            typer.echo(f"Scenario {scenario.id} failed: {exc}", err=True)
        latency_ms = max(1, round((perf_counter() - started) * 1000))
        metrics.append(
            metric_from_state(
                final_state,
                scenario.expected_route.value,
                scenario.requires_approval,
                latency_ms=latency_ms,
            )
        )

    resume_success = checkpointer_kind == "sqlite" and _has_checkpoint_history(graph, run_configs)
    report = summarize_metrics(metrics, resume_success=resume_success)
    write_metrics(report, output)
    report_path = _optional_string(cfg, "report_path")
    if report_path:
        write_report(report, report_path)
    typer.echo(f"Wrote metrics to {output}")


@app.command("validate-metrics")
def validate_metrics(metrics: Annotated[Path, typer.Option("--metrics")]) -> None:
    """Validate metrics JSON schema for grading."""
    payload = json.loads(metrics.read_text(encoding="utf-8"))
    report = MetricsReport.model_validate(payload)
    if report.total_scenarios < 6:
        raise typer.BadParameter("Expected at least 6 scenarios")
    typer.echo(f"Metrics valid. success_rate={report.success_rate:.2%}")


def _load_config(path: Path) -> Mapping[str, object]:
    """Load and validate the top-level YAML mapping."""
    if not path.is_file():
        raise typer.BadParameter(f"Config file does not exist: {path}")
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise typer.BadParameter(f"Invalid YAML config: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise typer.BadParameter("Config must be a YAML mapping")
    return payload


def _required_string(config: Mapping[str, object], key: str) -> str:
    value = _optional_string(config, key)
    if value is None:
        raise typer.BadParameter(f"Config field '{key}' is required")
    return value


def _optional_string(config: Mapping[str, object], key: str) -> str | None:
    value = config.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise typer.BadParameter(f"Config field '{key}' must be a non-empty string")
    return value.strip()


def _has_checkpoint_history(graph: object, configs: list[RunnableConfig]) -> bool:
    """Return true only when SQLite history was actually readable after execution."""
    history_reader = getattr(graph, "get_state_history", None)
    if not callable(history_reader):
        return False
    try:
        return any(any(history_reader(config)) for config in configs)
    except Exception:
        return False


if __name__ == "__main__":
    app()
