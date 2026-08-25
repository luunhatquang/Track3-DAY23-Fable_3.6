"""Pure normalize/build helpers and Streamlit render helpers for the Agent Ops Console."""
from __future__ import annotations

from typing import Any

STATUS_TO_LABEL: dict[str, tuple[str, str]] = {
    "completed": ("Completed", "success"),
    "resumed": ("Resumed", "success"),
    "pending_approval": ("Pending approval", "warn"),
    "retry": ("Retrying", "warn"),
    "needs_retry": ("Retrying", "warn"),
    "error": ("Error", "danger"),
    "dead_letter": ("Dead letter", "danger"),
}

SESSION_DEFAULTS: dict[str, Any] = {
    "graph": None,
    "checkpointer": None,
    "_graph_cache_key": None,
    "checkpointer_kind": "memory",
    "interrupt_enabled": False,
    "thread_id": None,
    "current_state": None,
    "pending_interrupt": None,
    "last_error": None,
    "metrics_report": None,
}

RESET_KEYS: tuple[str, ...] = (
    "thread_id",
    "current_state",
    "pending_interrupt",
    "last_error",
)


def normalize_events(events: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Normalize raw LabEvent dicts into a shape safe for rendering."""
    rows: list[dict[str, Any]] = []
    for event in events or []:
        rows.append(
            {
                "node": str(event.get("node", "unknown")),
                "event_type": str(event.get("event_type", "unknown")),
                "message": str(event.get("message", "")),
                "latency_ms": int(event.get("latency_ms") or 0),
                "metadata": dict(event.get("metadata") or {}),
            }
        )
    return rows


def build_resume_payload(approved: bool, reviewer: str, comment: str) -> dict[str, Any]:
    """Build the ApprovalPayload dict expected by approval_node / Command(resume=...)."""
    clean_reviewer = reviewer.strip() or "ui-reviewer"
    return {"approved": bool(approved), "reviewer": clean_reviewer, "comment": comment.strip()}


def extract_interrupt(result: Any) -> dict[str, Any] | None:
    """Return the interrupt payload dict if the graph run paused for approval, else None."""
    if not isinstance(result, dict):
        return None
    interrupts = result.get("__interrupt__")
    if not interrupts:
        return None
    first = interrupts[0]
    value = getattr(first, "value", first)
    return dict(value) if isinstance(value, dict) else {"raw": value}


def render_status_badge(status: str) -> str:
    label, tone = STATUS_TO_LABEL.get(status, (status.replace("_", " ").title() or "Unknown", "muted"))
    return f'<span class="badge badge-{tone}"><span class="badge-dot"></span>{label}</span>'


def build_checkpoint_rows(checkpoint_tuples: list[Any]) -> list[dict[str, Any]]:
    """Normalize LangGraph CheckpointTuple objects into display rows, newest last."""
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(checkpoint_tuples):
        checkpoint = getattr(item, "checkpoint", None) or {}
        metadata = getattr(item, "metadata", None) or {}
        rows.append(
            {
                "step": metadata.get("step", index),
                "node": metadata.get("source") or checkpoint.get("id", "unknown"),
                "ts": checkpoint.get("ts", ""),
            }
        )
    return rows
