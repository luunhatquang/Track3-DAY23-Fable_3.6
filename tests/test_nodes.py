"""Offline unit tests for node behavior and LLM integration contracts."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from types import ModuleType

import pytest

from langgraph_agent_lab import nodes


@dataclass
class FakeTextResponse:
    """Minimal LangChain-like response for answer-node tests."""

    content: str


class FakeStructuredModel:
    """Fake structured model that records the prompt supplied by classify_node."""

    def __init__(self, response: object) -> None:
        self.response = response
        self.prompt = ""

    def invoke(self, input_value: object) -> object:
        self.prompt = str(input_value)
        return self.response


class FakeChatModel:
    """Fake chat model supporting both structured and plain invocations."""

    def __init__(
        self,
        structured_response: object,
        text_response: str = "Grounded answer.",
    ) -> None:
        self.structured = FakeStructuredModel(structured_response)
        self.text_response = text_response
        self.answer_prompt = ""

    def with_structured_output(self, schema: object) -> FakeStructuredModel:
        del schema
        return self.structured

    def invoke(self, input_value: object) -> FakeTextResponse:
        self.answer_prompt = str(input_value)
        return FakeTextResponse(content=self.text_response)


@pytest.mark.parametrize(
    ("query", "route"),
    [
        ("How do I reset my password?", "simple"),
        ("Where is order 123?", "tool"),
        ("Can you fix it?", "missing_info"),
        ("Refund the order and email me", "risky"),
        ("The service timed out", "error"),
    ],
)
def test_classify_node_uses_structured_llm(
    monkeypatch: pytest.MonkeyPatch,
    query: str,
    route: str,
) -> None:
    fake_llm = FakeChatModel({"route": route, "rationale": "fake classification"})
    monkeypatch.setattr(nodes, "get_llm", lambda: fake_llm)

    result = nodes.classify_node({"query": query})

    assert result["route"] == route
    assert result["risk_level"] == ("high" if route == "risky" else "low")
    assert fake_llm.structured.prompt
    assert "risky > tool > missing_info > error > simple" in fake_llm.structured.prompt


def test_answer_node_grounds_prompt_in_state(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_llm = FakeChatModel({"route": "simple", "rationale": "unused"}, "Your order is shipped.")
    monkeypatch.setattr(nodes, "get_llm", lambda temperature=0.0: fake_llm)

    result = nodes.answer_node(
        {
            "query": "Where is order 123?",
            "tool_results": ["SUCCESS: order 123 shipped"],
            "approval": {"approved": True, "reviewer": "Lee", "comment": "ok"},
            "proposed_action": "None",
        }
    )

    assert result["final_answer"] == "Your order is shipped."
    assert "Where is order 123?" in fake_llm.answer_prompt
    assert "SUCCESS: order 123 shipped" in fake_llm.answer_prompt
    assert "Lee" in fake_llm.answer_prompt


@pytest.mark.parametrize(
    ("state", "expected_fragment"),
    [
        ({"route": "error", "attempt": 0, "query": "timeout"}, "ERROR"),
        ({"route": "error", "attempt": 1, "query": "timeout"}, "ERROR"),
        ({"route": "error", "attempt": 2, "query": "timeout"}, "SUCCESS"),
        ({"route": "tool", "attempt": 0, "query": "lookup order"}, "SUCCESS"),
    ],
)
def test_tool_node_simulates_transient_errors(
    state: dict[str, object],
    expected_fragment: str,
) -> None:
    result = nodes.tool_node(state)

    assert expected_fragment in str(result["tool_results"][0])


@pytest.mark.parametrize(
    ("tool_results", "expected"),
    [
        ([], "needs_retry"),
        (["ERROR: network"], "needs_retry"),
        (["SUCCESS: lookup complete"], "success"),
    ],
)
def test_evaluate_node_gates_retry(tool_results: list[str], expected: str) -> None:
    result = nodes.evaluate_node({"tool_results": tool_results})

    assert result["evaluation_result"] == expected


def test_clarification_and_risky_action_are_auditable() -> None:
    clarification = nodes.ask_clarification_node({"query": "Please fix it"})
    risky = nodes.risky_action_node({"query": "Delete the customer account"})

    assert clarification["pending_question"] == clarification["final_answer"]
    assert "Delete the customer account" in str(risky["proposed_action"])
    assert risky["events"][0]["node"] == "risky_action"


def test_retry_dead_letter_and_finalize_emit_expected_updates() -> None:
    retry = nodes.retry_or_fallback_node({"attempt": 1, "max_attempts": 3})
    dead_letter = nodes.dead_letter_node({"attempt": 3, "max_attempts": 3})
    final = nodes.finalize_node({"route": "error", "attempt": 3})

    assert retry["attempt"] == 2
    assert retry["errors"]
    assert "could not complete" in str(dead_letter["final_answer"]).lower()
    assert final["events"][0]["node"] == "finalize"


def test_approval_node_auto_approves_when_interrupts_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LANGGRAPH_INTERRUPT", raising=False)

    result = nodes.approval_node({"query": "Refund order", "proposed_action": "Refund order"})

    assert result["approval"]["approved"] is True
    assert result["events"][0]["event_type"] == "auto_approved"


def test_approval_node_uses_resumed_interrupt_decision(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_payload: dict[str, object] = {}
    fake_types = ModuleType("langgraph.types")

    def fake_interrupt(payload: object) -> dict[str, object]:
        captured_payload.update(payload if isinstance(payload, dict) else {})
        return {"approved": False, "reviewer": "Dana", "comment": "Need more evidence."}

    fake_types.interrupt = fake_interrupt
    monkeypatch.setitem(sys.modules, "langgraph.types", fake_types)
    monkeypatch.setenv("LANGGRAPH_INTERRUPT", "true")

    result = nodes.approval_node(
        {
            "thread_id": "thread-approval",
            "scenario_id": "approval-test",
            "query": "Refund order 123",
            "proposed_action": "Refund order 123",
            "risk_level": "high",
        }
    )

    assert captured_payload["thread_id"] == "thread-approval"
    assert result["approval"]["approved"] is False
    assert result["approval"]["reviewer"] == "Dana"
    assert result["events"][0]["event_type"] == "resumed"


def test_malformed_approval_decision_is_rejected() -> None:
    decision = nodes._approval_from({"approved": "yes", "reviewer": 7, "comment": None})

    assert decision["approved"] is False
    assert decision["reviewer"] == "unknown"
