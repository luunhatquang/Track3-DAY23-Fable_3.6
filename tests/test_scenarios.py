import json
from pathlib import Path

import pytest

from langgraph_agent_lab.scenarios import load_scenarios


def _scenario(identifier: str) -> str:
    return json.dumps(
        {
            "id": identifier,
            "query": f"Question {identifier}",
            "expected_route": "simple",
        }
    )


def test_load_scenarios_accepts_blank_lines(tmp_path: Path) -> None:
    path = tmp_path / "scenarios.jsonl"
    path.write_text("\n".join([_scenario(str(index)) for index in range(6)]) + "\n\n")

    scenarios = load_scenarios(path)

    assert [scenario.id for scenario in scenarios] == [str(index) for index in range(6)]


def test_load_scenarios_reports_source_line(tmp_path: Path) -> None:
    path = tmp_path / "scenarios.jsonl"
    path.write_text("\n".join([_scenario(str(index)) for index in range(5)] + ["not-json"]))

    with pytest.raises(ValueError, match="Invalid scenario at line 6"):
        load_scenarios(path)


def test_load_scenarios_rejects_duplicate_ids(tmp_path: Path) -> None:
    path = tmp_path / "scenarios.jsonl"
    path.write_text("\n".join([_scenario(str(index)) for index in range(5)] + [_scenario("0")]))

    with pytest.raises(ValueError, match="Duplicate scenario id at line 6: 0"):
        load_scenarios(path)


def test_load_scenarios_requires_minimum_count(tmp_path: Path) -> None:
    path = tmp_path / "scenarios.jsonl"
    path.write_text("\n".join(_scenario(str(index)) for index in range(5)))

    with pytest.raises(ValueError, match="At least 6 scenarios"):
        load_scenarios(path)
