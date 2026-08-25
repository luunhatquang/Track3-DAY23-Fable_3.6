"""Scenario loading."""

from __future__ import annotations

from pathlib import Path

from .state import Scenario


def load_scenarios(path: str | Path) -> list[Scenario]:
    scenario_path = Path(path)
    scenarios: list[Scenario] = []
    seen_ids: set[str] = set()
    with scenario_path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                scenario = Scenario.model_validate_json(line)
            except Exception as exc:
                raise ValueError(f"Invalid scenario at line {line_no}: {exc}") from exc
            if scenario.id in seen_ids:
                raise ValueError(f"Duplicate scenario id at line {line_no}: {scenario.id}")
            seen_ids.add(scenario.id)
            scenarios.append(scenario)
    if len(scenarios) < 6:
        raise ValueError("At least 6 scenarios are required for grading")
    return scenarios
