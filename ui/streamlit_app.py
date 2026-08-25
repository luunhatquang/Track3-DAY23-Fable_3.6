"""Agent Ops Console — Streamlit entrypoint."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from uuid import uuid4

import streamlit as st
from dotenv import load_dotenv

from langgraph_agent_lab.graph import build_graph
from langgraph_agent_lab.persistence import build_checkpointer
from langgraph_agent_lab.state import Scenario, initial_state

from components import (
    RESET_KEYS,
    SESSION_DEFAULTS,
    extract_interrupt,
    render_status_badge,
)

APP_DIR = Path(__file__).parent

load_dotenv()


def inject_css() -> None:
    css_path = APP_DIR / "styles.css"
    st.markdown(f"<style>{css_path.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def init_session_state() -> None:
    for key, default in SESSION_DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = default


def get_graph(checkpointer_kind: str, interrupt_enabled: bool) -> tuple[Any, Any]:
    cache_key = (checkpointer_kind, interrupt_enabled)
    if st.session_state["graph"] is not None and st.session_state["_graph_cache_key"] == cache_key:
        return st.session_state["graph"], st.session_state["checkpointer"]

    if interrupt_enabled:
        os.environ["LANGGRAPH_INTERRUPT"] = "true"
    else:
        os.environ.pop("LANGGRAPH_INTERRUPT", None)

    checkpointer = build_checkpointer(checkpointer_kind)
    graph = build_graph(checkpointer=checkpointer)
    st.session_state["graph"] = graph
    st.session_state["checkpointer"] = checkpointer
    st.session_state["_graph_cache_key"] = cache_key
    return graph, checkpointer


def new_ticket_thread() -> None:
    for key in RESET_KEYS:
        st.session_state[key] = SESSION_DEFAULTS[key]


def run_ticket(query: str, max_attempts: int) -> None:
    graph, _ = get_graph(st.session_state["checkpointer_kind"], st.session_state["interrupt_enabled"])
    thread_id = st.session_state["thread_id"] or f"ui-{uuid4().hex[:8]}"
    st.session_state["thread_id"] = thread_id

    scenario = Scenario(id="ui-ticket", query=query, expected_route="simple", max_attempts=max_attempts)
    state = initial_state(scenario)
    state["thread_id"] = thread_id
    config = {"configurable": {"thread_id": thread_id}}

    try:
        result = graph.invoke(state, config=config)
    except Exception as exc:
        st.session_state["last_error"] = str(exc)
        return

    st.session_state["last_error"] = None
    st.session_state["pending_interrupt"] = extract_interrupt(result)
    st.session_state["current_state"] = result


def resume_ticket(decision: dict[str, Any]) -> None:
    from langgraph.types import Command

    graph, _ = get_graph(st.session_state["checkpointer_kind"], st.session_state["interrupt_enabled"])
    thread_id = st.session_state["thread_id"]
    config = {"configurable": {"thread_id": thread_id}}

    try:
        result = graph.invoke(Command(resume=decision), config=config)
    except Exception as exc:
        st.session_state["last_error"] = str(exc)
        return

    st.session_state["last_error"] = None
    st.session_state["pending_interrupt"] = extract_interrupt(result)
    st.session_state["current_state"] = result


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown('<h3 class="section-title">Session</h3>', unsafe_allow_html=True)
        interrupt_enabled = st.toggle(
            "Real HITL (interrupt thật)",
            value=st.session_state["interrupt_enabled"],
            help="Bật trước khi Run để dùng approval thật thay vì mock-approve.",
        )
        st.session_state["interrupt_enabled"] = interrupt_enabled

        if st.session_state["thread_id"]:
            st.text_input("Thread ID", value=st.session_state["thread_id"], disabled=True)

        if st.button("New ticket", use_container_width=True):
            new_ticket_thread()
            st.rerun()

        if st.session_state["last_error"]:
            with st.expander("Debug: lỗi backend gần nhất", expanded=False):
                st.code(st.session_state["last_error"])


def render_ticket_runner_tab() -> None:
    st.markdown('<h3 class="section-title">Ticket Runner</h3>', unsafe_allow_html=True)
    query = st.text_area("Query", placeholder="Mô tả yêu cầu của bạn...", key="ticket_query", height=100)
    max_attempts = st.number_input("Max attempts", min_value=1, max_value=10, value=3, step=1)

    disabled = st.session_state["pending_interrupt"] is not None
    if disabled:
        st.markdown('<p class="muted">Đang chờ approval — xử lý ở tab Approval trước khi chạy ticket mới.</p>', unsafe_allow_html=True)

    if st.button("Run", type="primary", disabled=disabled, key="run_ticket_btn"):
        if not query.strip():
            st.error("Query không được để trống.")
        else:
            with st.spinner("Đang gọi graph..."):
                run_ticket(query.strip(), int(max_attempts))
            st.rerun()

    if st.session_state["last_error"]:
        st.error(f"Backend error: {st.session_state['last_error']}")
        return

    state = st.session_state["current_state"]
    if not state:
        return

    st.markdown("---")
    route = state.get("route", "")
    if route:
        status = "pending_approval" if st.session_state["pending_interrupt"] is not None else route
        st.markdown(render_status_badge(status), unsafe_allow_html=True)
    st.markdown(f"**Risk level:** {state.get('risk_level', 'unknown')}")
    st.text_input("Thread ID (copyable)", value=st.session_state["thread_id"] or "", disabled=True, key="thread_id_display")
    if state.get("final_answer"):
        st.markdown(f"**Final answer:** {state['final_answer']}")
    elif state.get("pending_question"):
        st.markdown(f"**Pending question:** {state['pending_question']}")


def render_approval_tab() -> None:
    interrupt_payload = st.session_state["pending_interrupt"]
    if not interrupt_payload:
        st.markdown('<p class="muted">Không có approval nào đang chờ.</p>', unsafe_allow_html=True)
        return

    st.markdown('<h3 class="section-title">Approval required</h3>', unsafe_allow_html=True)
    st.markdown(f"**Query gốc:** {interrupt_payload.get('query', '')}")
    st.markdown(f"**Đề xuất hành động:** {interrupt_payload.get('proposed_action', '')}")
    st.markdown(render_status_badge("pending_approval"), unsafe_allow_html=True)
    st.caption(f"Risk level: {interrupt_payload.get('risk_level', 'high')}")

    reviewer = st.text_input("Reviewer", value="", key="approval_reviewer")
    comment = st.text_area("Comment", value="", key="approval_comment")

    from components import build_resume_payload

    col_approve, col_reject = st.columns(2)
    decision = None
    with col_approve:
        if st.button("Approve", type="primary", use_container_width=True, key="approve_btn"):
            decision = build_resume_payload(True, reviewer, comment)
    with col_reject:
        if st.button("Reject", use_container_width=True, key="reject_btn"):
            decision = build_resume_payload(False, reviewer, comment)

    if decision is not None:
        with st.spinner("Đang resume..."):
            resume_ticket(decision)
        st.rerun()


def render_timeline_tab() -> None:
    state = st.session_state["current_state"]
    if not state:
        st.markdown('<p class="muted">Chạy một ticket để xem timeline.</p>', unsafe_allow_html=True)
        return

    from components import normalize_events

    rows = normalize_events(state.get("events", []))
    if not rows:
        st.markdown('<p class="muted">Chưa có event nào.</p>', unsafe_allow_html=True)
        return
    for row in rows:
        badge = render_status_badge(row["event_type"])
        latency = f'{row["latency_ms"]} ms' if row["latency_ms"] else ""
        st.markdown(
            f"""<div class="timeline-row">
  <div class="timeline-node">{row['node']}</div>
  <div class="timeline-body">{badge}<span class="timeline-message">{row['message']}</span>
    <span class="timeline-latency">{latency}</span></div>
</div>""",
            unsafe_allow_html=True,
        )


def main() -> None:
    st.set_page_config(page_title="Agent Ops Console", layout="wide")
    inject_css()
    init_session_state()
    st.markdown("<h1>Agent Ops Console</h1>", unsafe_allow_html=True)
    render_sidebar()

    tab_runner, tab_timeline, tab_approval = st.tabs(["Ticket Runner", "Timeline", "Approval"])
    with tab_runner:
        render_ticket_runner_tab()
    with tab_timeline:
        render_timeline_tab()
    with tab_approval:
        render_approval_tab()


main()
