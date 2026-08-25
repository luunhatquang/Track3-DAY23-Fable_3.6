"""Offline end-to-end smoke tests for the compiled graph."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from langgraph_agent_lab import nodes
from langgraph_agent_lab.graph import build_graph
from langgraph_agent_lab.persistence import build_checkpointer
from langgraph_agent_lab.state import Route, Scenario, initial_state


@dataclass
class FakeResponse:
    content: str


class FakeStructuredModel:
    def invoke(self, prompt: object) -> dict[str, str]:
        query = str(prompt).rsplit("Ticket:", maxsplit=1)[-1].lower()
        if any(word in query for word in ("refund", "delete", "cancel", "email")):
            route = "risky"
        elif any(word in query for word in ("lookup", "track", "order status")):
            route = "tool"
        elif any(word in query for word in ("fix it", "does not work")):
            route = "missing_info"
        elif any(word in query for word in ("timeout", "failure", "unavailable")):
            route = "error"
        else:
            route = "simple"
        return {"route": route, "rationale": "offline integration fixture"}


class FakeChatModel:
    def with_structured_output(self, schema: object) -> FakeStructuredModel:
        del schema
        return FakeStructuredModel()

    def invoke(self, prompt: object) -> FakeResponse:
        del prompt
        return FakeResponse("Grounded offline response.")


@pytest.fixture(autouse=True)
def fake_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    model = FakeChatModel()
    monkeypatch.setattr(nodes, "get_llm", lambda *args, **kwargs: model)
    monkeypatch.delenv("LANGGRAPH_INTERRUPT", raising=False)


@pytest.mark.parametrize(
    ("query", "expected_route"),
    [
        ("How do I reset my password?", Route.SIMPLE.value),
        ("Track my order", Route.TOOL.value),
        ("Cancel subscription and email me", Route.RISKY.value),
        ("It does not work", Route.MISSING_INFO.value),
        ("Service unavailable after deploy", Route.ERROR.value),
        ("Lookup the payment then refund it", Route.RISKY.value),
    ],
)
def test_graph_runs_hidden_style_routes(query: str, expected_route: str) -> None:
    graph = build_graph(checkpointer=build_checkpointer("memory"))
    scenario = Scenario(id="smoke", query=query, expected_route=Route(expected_route))
    state = initial_state(scenario)

    result = graph.invoke(
        state,
        config={"configurable": {"thread_id": state["thread_id"]}},
    )

    assert result["route"] == expected_route
    assert result.get("final_answer") or result.get("pending_question")
    assert result["events"][-1]["node"] == "finalize"


def test_max_attempts_one_reaches_dead_letter() -> None:
    graph = build_graph(checkpointer=build_checkpointer("memory"))
    scenario = Scenario(
        id="dead-letter",
        query="Service unavailable after deploy",
        expected_route=Route.ERROR,
        should_retry=True,
        max_attempts=1,
    )
    state = initial_state(scenario)

    result = graph.invoke(
        state,
        config={"configurable": {"thread_id": state["thread_id"]}},
    )

    visited = [event["node"] for event in result["events"]]
    assert "retry" in visited
    assert "dead_letter" in visited
    assert visited[-1] == "finalize"


def test_sqlite_graph_history_is_isolated_by_thread(tmp_path: Path) -> None:
    saver = build_checkpointer("sqlite", str(tmp_path / "graph.sqlite"))
    graph = build_graph(checkpointer=saver)
    first = initial_state(Scenario(id="one", query="General help", expected_route=Route.SIMPLE))
    second = initial_state(Scenario(id="two", query="Track my order", expected_route=Route.TOOL))

    for state in (first, second):
        graph.invoke(state, config={"configurable": {"thread_id": state["thread_id"]}})

    first_config = {"configurable": {"thread_id": first["thread_id"]}}
    second_config = {"configurable": {"thread_id": second["thread_id"]}}
    assert graph.get_state(first_config).values["scenario_id"] == "one"
    assert graph.get_state(second_config).values["scenario_id"] == "two"
    assert list(graph.get_state_history(first_config))
    saver.conn.close()
