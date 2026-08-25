"""Construction of the complete terminating LangGraph workflow."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .state import AgentState

if TYPE_CHECKING:
    from langgraph.graph.state import Checkpointer, CompiledStateGraph


def build_graph(
    checkpointer: Checkpointer = None,
) -> CompiledStateGraph[AgentState, None, AgentState, AgentState]:
    from langgraph.graph import END, START, StateGraph

    from .nodes import (
        answer_node,
        approval_node,
        ask_clarification_node,
        classify_node,
        dead_letter_node,
        evaluate_node,
        finalize_node,
        intake_node,
        retry_or_fallback_node,
        risky_action_node,
        tool_node,
    )
    from .routing import (
        route_after_approval,
        route_after_classify,
        route_after_evaluate,
        route_after_retry,
    )

    builder = StateGraph(AgentState)
    for name, node in {
        "intake": intake_node,
        "classify": classify_node,
        "tool": tool_node,
        "evaluate": evaluate_node,
        "answer": answer_node,
        "clarify": ask_clarification_node,
        "risky_action": risky_action_node,
        "approval": approval_node,
        "retry": retry_or_fallback_node,
        "dead_letter": dead_letter_node,
        "finalize": finalize_node,
    }.items():
        builder.add_node(name, node)
    for source, target in (
        (START, "intake"),
        ("intake", "classify"),
        ("tool", "evaluate"),
        ("answer", "finalize"),
        ("clarify", "finalize"),
        ("risky_action", "approval"),
        ("dead_letter", "finalize"),
        ("finalize", END),
    ):
        builder.add_edge(source, target)
    builder.add_conditional_edges(
        "classify",
        route_after_classify,
        {
            "answer": "answer",
            "tool": "tool",
            "clarify": "clarify",
            "risky_action": "risky_action",
            "retry": "retry",
        },
    )
    builder.add_conditional_edges(
        "evaluate", route_after_evaluate, {"retry": "retry", "answer": "answer"}
    )
    builder.add_conditional_edges(
        "retry", route_after_retry, {"tool": "tool", "dead_letter": "dead_letter"}
    )
    builder.add_conditional_edges(
        "approval", route_after_approval, {"tool": "tool", "clarify": "clarify"}
    )
    return builder.compile(checkpointer=checkpointer)
