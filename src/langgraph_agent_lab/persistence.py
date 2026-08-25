"""Checkpointer adapter."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from langgraph.graph.state import Checkpointer


def _sqlite_path(database_url: str | None) -> str:
    """Normalize a local SQLite path while rejecting unsupported URLs."""
    if not database_url:
        return "checkpoints.db"
    if database_url == ":memory:":
        return database_url
    if database_url.startswith("sqlite:///"):
        path = database_url.removeprefix("sqlite:///")
    elif "://" in database_url:
        raise ValueError("SQLite checkpointer requires a file path or sqlite:/// URL")
    else:
        path = database_url
    if not path:
        raise ValueError("SQLite database path must not be empty")
    return path


def build_checkpointer(kind: str = "memory", database_url: str | None = None) -> Checkpointer:
    """Return a LangGraph checkpointer.

    SQLite connections remain owned by the returned saver so graph and UI callers
    can reuse the same checkpointer throughout their lifecycle.
    """
    if kind == "none":
        return None
    if kind == "memory":
        from langgraph.checkpoint.memory import MemorySaver

        return MemorySaver()
    if kind == "sqlite":
        try:
            from langgraph.checkpoint.sqlite import SqliteSaver
        except ImportError as exc:
            raise RuntimeError(
                "SQLite persistence requires: pip install langgraph-checkpoint-sqlite"
            ) from exc

        sqlite_path = _sqlite_path(database_url)
        if sqlite_path != ":memory:":
            Path(sqlite_path).expanduser().parent.mkdir(parents=True, exist_ok=True)
            sqlite_path = str(Path(sqlite_path).expanduser())
        connection = sqlite3.connect(sqlite_path, check_same_thread=False)
        if sqlite_path != ":memory:":
            connection.execute("PRAGMA journal_mode=WAL")
        return SqliteSaver(conn=connection)
    if kind == "postgres":
        raise NotImplementedError(
            "TODO(student): implement Postgres checkpointer (optional extension)"
        )
    raise ValueError(f"Unknown checkpointer kind: {kind}")
