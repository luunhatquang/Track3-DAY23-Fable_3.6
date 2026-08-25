"""Defensive routing functions for conditional graph edges."""
from __future__ import annotations
from .state import AgentState

def route_after_classify(state: AgentState) -> str:
    routes = {"simple": "answer", "tool": "tool", "missing_info": "clarify",
              "risky": "risky_action", "error": "retry"}
    return routes.get(str(state.get("route", "")), "answer")

def route_after_evaluate(state: AgentState) -> str:
    return "retry" if state.get("evaluation_result") == "needs_retry" else "answer"

def route_after_retry(state: AgentState) -> str:
    attempt = _safe_int(state.get("attempt"), 0)
    maximum = max(0, _safe_int(state.get("max_attempts"), 3))
    return "tool" if attempt < maximum else "dead_letter"

def route_after_approval(state: AgentState) -> str:
    approval = state.get("approval")
    return "tool" if isinstance(approval, dict) and approval.get("approved") is True else "clarify"

def _safe_int(value: object, default: int) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError, OverflowError):
        return default
