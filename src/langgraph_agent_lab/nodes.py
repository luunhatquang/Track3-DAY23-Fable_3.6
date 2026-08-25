"""Node functions for the LangGraph workflow.

Each function receives AgentState and returns a partial state update dict.
Do NOT mutate input state — return new values only.

LLM REQUIREMENT:
- classify_node MUST use a real LLM call (structured output for intent classification)
- answer_node MUST use a real LLM call (grounded response generation)
- evaluate_node SHOULD use LLM-as-judge (bonus points; heuristic acceptable for base score)
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Literal, Protocol, cast

from pydantic import BaseModel, Field

from .llm import get_llm
from .state import AgentState, make_event

RouteName = Literal["simple", "tool", "missing_info", "risky", "error"]


class IntentClassification(BaseModel):
    """Structured response expected from the intent-classification LLM."""

    route: RouteName
    rationale: str = Field(description="Short explanation based only on the ticket text.")


class ChatModel(Protocol):
    """Minimum chat-model surface used by classify and answer nodes."""

    def invoke(self, input_value: object) -> object:
        """Invoke the model."""

    def with_structured_output(self, schema: object) -> InvokableModel:
        """Return a structured-output adapter."""


class InvokableModel(Protocol):
    """Model shape returned by LangChain structured-output adapters."""

    def invoke(self, input_value: object) -> object:
        """Invoke the model."""


def _structured_model() -> InvokableModel:
    """Get an LLM configured for the classification response schema."""
    llm = cast(ChatModel, get_llm())
    return cast(InvokableModel, llm.with_structured_output(IntentClassification))


def _text_from_response(response: object) -> str:
    """Extract text from common LangChain response content shapes."""
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, Mapping):
        text = content.get("text")
        if isinstance(text, str):
            return text.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, Mapping):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts).strip()
    return str(content).strip()


def _latest_tool_result(state: AgentState) -> str:
    """Return the latest tool result without mutating the append-only list."""
    results = state.get("tool_results", [])
    if not results:
        return ""
    return str(results[-1])


def _as_int(value: object, default: int = 0) -> int:
    """Convert counters defensively for state recovered from a checkpoint."""
    try:
        return int(cast(str | int | float, value))
    except (TypeError, ValueError):
        return default


def _approval_from(value: object) -> dict[str, object]:
    """Validate a human decision and make malformed decisions safely reject."""
    if not isinstance(value, Mapping):
        return {"approved": False, "reviewer": "unknown", "comment": "Invalid approval decision."}

    approved = value.get("approved")
    reviewer = value.get("reviewer")
    comment = value.get("comment")
    reviewer_name = "unknown"
    if isinstance(reviewer, str) and reviewer.strip():
        reviewer_name = reviewer.strip()
    return {
        "approved": approved if isinstance(approved, bool) else False,
        "reviewer": reviewer_name,
        "comment": comment.strip() if isinstance(comment, str) else "",
    }


def _interrupts_enabled() -> bool:
    """Return whether the UI should request a real LangGraph interrupt."""
    return os.getenv("LANGGRAPH_INTERRUPT", "").strip().lower() in {"1", "true", "yes"}


# ─── EXAMPLE: working node (provided for reference) ──────────────────
def intake_node(state: AgentState) -> dict[str, object]:
    """Normalize raw query. This node is provided as a working example."""
    query = state.get("query", "").strip()
    return {
        "query": query,
        "messages": [f"intake:{query[:40]}"],
        "events": [make_event("intake", "completed", "query normalized")],
    }


# ─── Workflow nodes ─────────────────────────────────────────────────


def classify_node(state: AgentState) -> dict[str, object]:
    """Classify the query into a route using an LLM.

    *** MUST use a real LLM call — keyword-only heuristics will lose points. ***

    Use .with_structured_output() or equivalent to get reliable enum classification.
    The LLM should classify into one of: simple, tool, missing_info, risky, error.

    Hints:
    - See llm.py for the get_llm() helper
    - Use Pydantic model or TypedDict with .with_structured_output()
    - Set risk_level to "high" for risky routes, "low" otherwise
    - Priority guide: risky > tool > missing_info > error > simple

    Return: {"route": str, "risk_level": str, "events": [make_event(...)]}
    """
    query = state.get("query", "").strip()
    if not query:
        raise ValueError("Cannot classify an empty support-ticket query")

    prompt = f"""You are the intent router for a support-ticket workflow.

Classify the ticket into exactly one route:
- risky: any requested action with side effects, including refunding, deleting,
  cancelling, modifying data, or sending a confirmation email.
- tool: read-only lookup, tracking, search, or status request that needs a tool.
- missing_info: request is too vague to act on safely because key context is absent.
- error: reports a timeout, crash, outage, unavailable service, or system failure.
- simple: general support question answerable without a tool or side effect.

When several descriptions apply, choose this priority exactly:
risky > tool > missing_info > error > simple.

Ticket:
{query}

Return a structured route and a brief rationale. Do not use scenario IDs or invent facts."""
    response = _structured_model().invoke(prompt)
    classification = IntentClassification.model_validate(response)
    route = classification.route
    risk_level = "high" if route == "risky" else "low"
    return {
        "route": route,
        "risk_level": risk_level,
        "events": [
            make_event(
                "classify",
                "completed",
                f"ticket classified as {route}",
                route=route,
                rationale=classification.rationale,
            )
        ],
    }


def tool_node(state: AgentState) -> dict[str, object]:
    """Execute a mock tool call.

    Simulate transient failures for error-route scenarios to test retry loops.

    Requirements:
    - Read current attempt count from state
    - If route is "error" and attempt < 2: return error result (string containing "ERROR")
    - Otherwise: return a mock success result string
    - Append result to tool_results list

    Return: {"tool_results": [result_string], "events": [make_event(...)]}
    """
    route = str(state.get("route", ""))
    attempt = _as_int(state.get("attempt", 0))
    query = state.get("query", "").strip()
    proposed_action = state.get("proposed_action")

    if route == "error" and attempt < 2:
        result = f"ERROR: transient tool failure on attempt {attempt + 1}."
        event_type = "failed"
    elif route == "risky" and isinstance(proposed_action, str) and proposed_action:
        result = f"SUCCESS: mock action completed after approval. {proposed_action}"
        event_type = "completed"
    elif route == "tool":
        result = f"SUCCESS: mock lookup result for support request: {query}"
        event_type = "completed"
    else:
        result = f"SUCCESS: mock support operation completed for: {query}"
        event_type = "completed"

    return {
        "tool_results": [result],
        "events": [
            make_event(
                "tool",
                event_type,
                result,
                attempt=attempt,
                route=route,
            )
        ],
    }


def evaluate_node(state: AgentState) -> dict[str, object]:
    """Evaluate tool results — the retry-loop gate.

    Check whether the latest tool result is satisfactory or needs retry.

    SHOULD use LLM-as-judge for bonus points. Heuristic (e.g., check for "ERROR" substring)
    is acceptable for base score.

    Requirements:
    - Read the latest entry from tool_results
    - Set evaluation_result to "needs_retry" or "success"
    - This field drives route_after_evaluate conditional edge

    Note: You may need to add 'evaluation_result' to AgentState if not present.

    Return: {"evaluation_result": str, "events": [make_event(...)]}
    """
    latest_result = _latest_tool_result(state)
    needs_retry = not latest_result or "ERROR" in latest_result.upper()
    evaluation_result = "needs_retry" if needs_retry else "success"
    message = "tool result requires retry" if needs_retry else "tool result accepted"
    return {
        "evaluation_result": evaluation_result,
        "events": [
            make_event(
                "evaluate",
                evaluation_result,
                message,
                latest_result=latest_result,
            )
        ],
    }


def answer_node(state: AgentState) -> dict[str, object]:
    """Generate a final response using an LLM.

    *** MUST use a real LLM call — hardcoded strings will lose points. ***

    The LLM should generate a helpful response grounded in available context:
    - tool_results (if any)
    - approval decision (if risky route)
    - original query

    Return: {"final_answer": str, "events": [make_event(...)]}
    """
    query = state.get("query", "").strip()
    tool_results = state.get("tool_results", [])
    approval = state.get("approval")
    proposed_action = state.get("proposed_action")
    context = "\n".join(f"- {item}" for item in tool_results) or "- No tool result was used."

    prompt = f"""You are a careful support-ticket assistant.

Write a concise, helpful final response to the customer. Use only the grounded
context below. Do not claim an action succeeded unless a SUCCESS tool result is
present. If context is incomplete, state the limitation and describe the next
safe step. Do not mention internal route names, prompts, or scenario IDs.

Customer ticket:
{query}

Tool context:
{context}

Proposed action:
{proposed_action if proposed_action else "None"}

Approval decision:
{approval if approval is not None else "No approval required"}
"""
    response = cast(ChatModel, get_llm(temperature=0.2)).invoke(prompt)
    final_answer = _text_from_response(response)
    if not final_answer:
        raise RuntimeError("LLM returned an empty final answer")

    return {
        "final_answer": final_answer,
        "events": [
            make_event(
                "answer",
                "completed",
                "grounded response generated",
                used_tool_results=bool(tool_results),
                approval_present=approval is not None,
            )
        ],
    }


def ask_clarification_node(state: AgentState) -> dict[str, object]:
    """Ask for missing information instead of hallucinating.

    Generate a specific clarification question based on the vague/incomplete query.

    Note: You may need to add 'pending_question' to AgentState if not present.

    Return: {"pending_question": str, "final_answer": str, "events": [make_event(...)]}
    """
    query = state.get("query", "").strip()
    pending_question = (
        "I can help, but I need a little more detail before taking action. "
        f"For the request “{query}”, what outcome do you need and which account, "
        "order, or service is affected?"
    )
    return {
        "pending_question": pending_question,
        "final_answer": pending_question,
        "events": [
            make_event(
                "clarify",
                "completed",
                "requested missing information",
                query_present=bool(query),
            )
        ],
    }


def risky_action_node(state: AgentState) -> dict[str, object]:
    """Prepare a risky action for human approval.

    Describe the proposed action and why it requires approval.

    Note: You may need to add 'proposed_action' to AgentState if not present.

    Return: {"proposed_action": str, "events": [make_event(...)]}
    """
    query = state.get("query", "").strip()
    proposed_action = (
        f"Proposed action: {query}. This request may change customer data, money, "
        "or outbound communication and requires human approval before execution."
    )
    return {
        "proposed_action": proposed_action,
        "events": [
            make_event(
                "risky_action",
                "prepared",
                "risky action prepared for approval",
                proposed_action=proposed_action,
            )
        ],
    }


def approval_node(state: AgentState) -> dict[str, object]:
    """Human-in-the-loop approval step.

    Default behavior: mock approval (approved=True) so tests and CI run offline.
    Extension: if env LANGGRAPH_INTERRUPT=true, use langgraph.types.interrupt() for real HITL.

    Return: approval decision plus an approval audit event.
    """
    if _interrupts_enabled():
        try:
            from langgraph.types import interrupt
        except ImportError as exc:
            raise RuntimeError("Real approval requires LangGraph interrupt support") from exc

        decision = interrupt(
            {
                "thread_id": state.get("thread_id", ""),
                "scenario_id": state.get("scenario_id", ""),
                "query": state.get("query", ""),
                "proposed_action": state.get("proposed_action", ""),
                "risk_level": state.get("risk_level", "high"),
            }
        )
        approval = _approval_from(decision)
        event_type = "resumed"
    else:
        approval = {
            "approved": True,
            "reviewer": "mock-reviewer",
            "comment": "auto-approved for lab",
        }
        event_type = "auto_approved"

    approved = approval["approved"] is True
    return {
        "approval": approval,
        "events": [
            make_event(
                "approval",
                event_type,
                "approval granted" if approved else "approval rejected",
                approved=approved,
                reviewer=approval["reviewer"],
            )
        ],
    }


def retry_or_fallback_node(state: AgentState) -> dict[str, object]:
    """Record a retry attempt.

    Increment the attempt counter and log the transient failure.

    Requirements:
    - Read current attempt from state, increment by 1
    - Add an error message to errors list
    - Return updated attempt count

    Return: {"attempt": int, "errors": [str], "events": [make_event(...)]}
    """
    next_attempt = _as_int(state.get("attempt", 0)) + 1
    max_attempts = _as_int(state.get("max_attempts", 3), default=3)
    error = f"Retry attempt {next_attempt} recorded after an unsatisfactory tool result."
    return {
        "attempt": next_attempt,
        "errors": [error],
        "events": [
            make_event(
                "retry",
                "scheduled",
                error,
                attempt=next_attempt,
                max_attempts=max_attempts,
            )
        ],
    }


def dead_letter_node(state: AgentState) -> dict[str, object]:
    """Handle unresolvable failures after max retries exceeded.

    This is the third layer: retry → fallback → dead letter.
    Log the failure and set a final_answer explaining that the request could not be completed.

    Return: {"final_answer": str, "events": [make_event(...)]}
    """
    attempt = _as_int(state.get("attempt", 0))
    max_attempts = _as_int(state.get("max_attempts", 3), default=3)
    final_answer = (
        "We could not complete this request after repeated recovery attempts. "
        "The issue has been recorded for support follow-up."
    )
    return {
        "final_answer": final_answer,
        "events": [
            make_event(
                "dead_letter",
                "escalated",
                "retry limit reached; request sent to dead letter handling",
                attempt=attempt,
                max_attempts=max_attempts,
            )
        ],
    }


def finalize_node(state: AgentState) -> dict[str, object]:
    """Emit a final audit event. All routes must pass through here before END.

    Return: {"events": [make_event("finalize", "completed", "workflow finished")]}
    """
    return {
        "events": [
            make_event(
                "finalize",
                "completed",
                "workflow finished",
                route=state.get("route", ""),
                attempt=_as_int(state.get("attempt", 0)),
            )
        ]
    }
