from __future__ import annotations

from ui.components import (
    RESET_KEYS,
    SESSION_DEFAULTS,
    build_checkpoint_rows,
    build_resume_payload,
    extract_interrupt,
    normalize_events,
    render_status_badge,
)


def test_normalize_events_fills_missing_optional_fields():
    raw = [{"node": "intake", "event_type": "completed", "message": "ok"}]
    result = normalize_events(raw)
    assert result == [
        {"node": "intake", "event_type": "completed", "message": "ok", "latency_ms": 0, "metadata": {}}
    ]


def test_normalize_events_handles_none_and_empty():
    assert normalize_events(None) == []
    assert normalize_events([]) == []


def test_normalize_events_preserves_metadata_and_latency():
    raw = [{"node": "tool", "event_type": "error", "message": "boom", "latency_ms": 120, "metadata": {"attempt": 2}}]
    result = normalize_events(raw)
    assert result[0]["latency_ms"] == 120
    assert result[0]["metadata"] == {"attempt": 2}


def test_build_resume_payload_shape():
    payload = build_resume_payload(True, "alice", "looks fine")
    assert payload == {"approved": True, "reviewer": "alice", "comment": "looks fine"}


def test_build_resume_payload_defaults_blank_reviewer():
    payload = build_resume_payload(False, "   ", "  ")
    assert payload["reviewer"] == "ui-reviewer"
    assert payload["comment"] == ""


def test_extract_interrupt_returns_none_when_absent():
    assert extract_interrupt({"route": "simple", "final_answer": "hi"}) is None
    assert extract_interrupt("not-a-dict") is None


def test_extract_interrupt_reads_payload_value():
    class FakeInterrupt:
        def __init__(self, value):
            self.value = value

    payload = {"query": "delete account", "proposed_action": "delete", "risk_level": "high"}
    result = {"__interrupt__": (FakeInterrupt(payload),)}
    assert extract_interrupt(result) == payload


def test_render_status_badge_has_text_label_not_only_color():
    html = render_status_badge("completed")
    assert "Completed" in html
    assert "badge-success" in html


def test_render_status_badge_unknown_status_falls_back():
    html = render_status_badge("weird_status")
    assert "Weird Status" in html
    assert "badge-muted" in html


def test_session_defaults_and_reset_keys_never_touch_graph_or_checkpointer():
    assert "graph" in SESSION_DEFAULTS
    assert "checkpointer" in SESSION_DEFAULTS
    assert "graph" not in RESET_KEYS
    assert "checkpointer" not in RESET_KEYS
    assert "thread_id" in RESET_KEYS


class _FakeCheckpointTuple:
    def __init__(self, checkpoint, metadata):
        self.checkpoint = checkpoint
        self.metadata = metadata


def test_build_checkpoint_rows_reads_step_node_ts():
    tuples = [
        _FakeCheckpointTuple({"id": "chk-1", "ts": "2026-08-25T10:00:00Z"}, {"step": 0, "source": "input"}),
        _FakeCheckpointTuple({"id": "chk-2", "ts": "2026-08-25T10:00:01Z"}, {"step": 1, "source": "intake"}),
    ]
    rows = build_checkpoint_rows(tuples)
    assert rows == [
        {"step": 0, "node": "input", "ts": "2026-08-25T10:00:00Z"},
        {"step": 1, "node": "intake", "ts": "2026-08-25T10:00:01Z"},
    ]


def test_build_checkpoint_rows_handles_missing_metadata():
    tuples = [_FakeCheckpointTuple({"id": "chk-1", "ts": ""}, {})]
    rows = build_checkpoint_rows(tuples)
    assert rows == [{"step": 0, "node": "chk-1", "ts": ""}]


def test_build_checkpoint_rows_empty_input():
    assert build_checkpoint_rows([]) == []
