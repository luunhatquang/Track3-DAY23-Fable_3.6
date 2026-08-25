import importlib.util
from pathlib import Path
from typing import TypedDict

import pytest

from langgraph_agent_lab.persistence import _sqlite_path, build_checkpointer


class CounterState(TypedDict):
    value: int


def _increment(state: CounterState) -> CounterState:
    return {"value": state["value"] + 1}


def _counter_graph(checkpointer: object) -> object:
    from langgraph.graph import END, START, StateGraph

    builder = StateGraph(CounterState)
    builder.add_node("increment", _increment)
    builder.add_edge(START, "increment")
    builder.add_edge("increment", END)
    return builder.compile(checkpointer=checkpointer)


def test_none_checkpointer() -> None:
    assert build_checkpointer("none") is None


def test_unknown_checkpointer() -> None:
    with pytest.raises(ValueError, match="Unknown checkpointer kind"):
        build_checkpointer("redis")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, "checkpoints.db"),
        (":memory:", ":memory:"),
        ("state/checkpoints.sqlite", "state/checkpoints.sqlite"),
        ("sqlite:///state/checkpoints.sqlite", "state/checkpoints.sqlite"),
    ],
)
def test_sqlite_path_normalization(value: str | None, expected: str) -> None:
    assert _sqlite_path(value) == expected


def test_sqlite_path_rejects_other_url_schemes() -> None:
    with pytest.raises(ValueError, match="file path or sqlite"):
        _sqlite_path("postgresql://localhost/checkpoints")


@pytest.mark.skipif(
    importlib.util.find_spec("langgraph") is None,
    reason="langgraph is not installed",
)
def test_memory_checkpointer_builds() -> None:
    assert build_checkpointer("memory") is not None


@pytest.mark.skipif(
    importlib.util.find_spec("langgraph") is None,
    reason="langgraph is not installed",
)
def test_sqlite_checkpointer_creates_database(tmp_path: Path) -> None:
    pytest.importorskip("langgraph.checkpoint.sqlite")
    database_path = tmp_path / "nested" / "checkpoints.sqlite"

    saver = build_checkpointer("sqlite", str(database_path))

    assert saver is not None
    assert database_path.exists()
    connection = saver.conn
    mode = connection.execute("PRAGMA journal_mode").fetchone()
    assert mode is not None and mode[0].lower() == "wal"
    connection.close()


@pytest.mark.skipif(
    importlib.util.find_spec("langgraph") is None,
    reason="langgraph is not installed",
)
def test_sqlite_keeps_threads_separate_and_survives_reopen(tmp_path: Path) -> None:
    pytest.importorskip("langgraph.checkpoint.sqlite")
    database_path = tmp_path / "checkpoints.sqlite"
    first_saver = build_checkpointer("sqlite", str(database_path))
    first_graph = _counter_graph(first_saver)
    first_config = {"configurable": {"thread_id": "thread-one"}}
    second_config = {"configurable": {"thread_id": "thread-two"}}

    assert first_graph.invoke({"value": 1}, config=first_config)["value"] == 2
    assert first_graph.invoke({"value": 10}, config=second_config)["value"] == 11
    assert first_graph.get_state(first_config).values["value"] == 2
    assert first_graph.get_state(second_config).values["value"] == 11
    assert len(list(first_graph.get_state_history(first_config))) >= 2
    first_saver.conn.close()

    reopened_saver = build_checkpointer("sqlite", str(database_path))
    reopened_graph = _counter_graph(reopened_saver)

    assert reopened_graph.get_state(first_config).values["value"] == 2
    assert reopened_graph.get_state(second_config).values["value"] == 11
    reopened_saver.conn.close()
