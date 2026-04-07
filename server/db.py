"""
In-memory SQLite database manager with thread safety and execution timeouts.
"""

from __future__ import annotations

import sqlite3
import threading
from typing import Any, Callable, List, Optional, Tuple

# Maximum SQLite VM instructions before we abort (approximate timeout for agent queries).
_DEFAULT_PROGRESS_LIMIT = 50_000_000


class DatabaseManager:
    """
    Manages an isolated in-memory SQLite connection per episode.

    All operations are serialized with a lock for safe concurrent FastAPI access.
    """

    def __init__(self, db_path: str = ":memory:") -> None:
        self.db_path = db_path
        self._lock = threading.Lock()
        self.conn: Optional[sqlite3.Connection] = None
        self._progress_limit: int = _DEFAULT_PROGRESS_LIMIT

    def initialize(self, task_seed_fn: Callable[[sqlite3.Connection], None]) -> None:
        """
        Create a fresh in-memory DB and seed it with task data.

        Args:
            task_seed_fn: Callable that receives an open connection and creates schema/data.
        """
        with self._lock:
            if self.conn is not None:
                try:
                    self.conn.close()
                except sqlite3.Error:
                    pass
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            self._set_progress_handler()
            task_seed_fn(self.conn)
            self.conn.commit()

    def _set_progress_handler(self) -> None:
        """Abort runaway queries after a large number of VM instructions."""
        if self.conn is None:
            return
        counter = [0]

        def _handler() -> int:
            counter[0] += 1
            if counter[0] >= self._progress_limit:
                return 1
            return 0

        self.conn.set_progress_handler(_handler, 1000)

    def run_query(self, sql: str) -> Tuple[List[Tuple[Any, ...]], Optional[str]]:
        """
        Execute SQL and return rows or an error string.

        Never raises; failures are returned as ``([], error_message)``.

        Args:
            sql: SQL string to execute.

        Returns:
            ``(rows, None)`` on success, or ``([], error_message)`` on failure.
        """
        with self._lock:
            if self.conn is None:
                return [], "Database is not initialized"
            try:
                cur = self.conn.execute(sql)
                rows = [tuple(row) for row in cur.fetchall()]
                return rows, None
            except sqlite3.Error as exc:
                return [], str(exc)

    def explain_query_plan(self, sql: str) -> str:
        """
        Run ``EXPLAIN QUERY PLAN`` for the given SQL and return the plan text.

        Args:
            sql: SQL string to explain.

        Returns:
            Human-readable plan lines joined with newlines, or an error description.
        """
        with self._lock:
            if self.conn is None:
                return "Database is not initialized"
            try:
                cur = self.conn.execute(f"EXPLAIN QUERY PLAN {sql}")
                lines = [str(row) for row in cur.fetchall()]
                return "\n".join(lines)
            except sqlite3.Error as exc:
                return f"EXPLAIN failed: {exc}"

    def close(self) -> None:
        """Close the underlying connection if open."""
        with self._lock:
            if self.conn is not None:
                try:
                    self.conn.close()
                except sqlite3.Error:
                    pass
                self.conn = None
