"""Agent Ops Console — Streamlit entrypoint."""
from __future__ import annotations

from pathlib import Path

import streamlit as st

APP_DIR = Path(__file__).parent


def inject_css() -> None:
    css_path = APP_DIR / "styles.css"
    st.markdown(f"<style>{css_path.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def main() -> None:
    st.set_page_config(page_title="Agent Ops Console", layout="wide")
    inject_css()
    st.markdown("<h1>Agent Ops Console</h1>", unsafe_allow_html=True)
    st.markdown('<p class="muted">Scaffold booted — tabs added in later tasks.</p>', unsafe_allow_html=True)


main()
