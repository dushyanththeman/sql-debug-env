"""
FastAPI application exposing the SQL debug environment over HTTP/WebSocket.
"""

from __future__ import annotations

try:
    from ..models import SqlDebugAction, SqlDebugObservation
    from .sql_environment import SqlDebugEnvironment
except ImportError:
    from models import SqlDebugAction, SqlDebugObservation
    from server.sql_environment import SqlDebugEnvironment

from openenv.core.env_server import create_app

TASKS_PAYLOAD = [
    {
        "id": "syntax-fix-001",
        "description": "Fix SQL keyword typos (SELCT, WHER)",
        "difficulty": "easy",
    },
    {
        "id": "join-optimization-001",
        "description": "Replace N+1 correlated subquery with efficient JOIN",
        "difficulty": "medium",
    },
    {
        "id": "aggregation-bug-001",
        "description": "Fix double-counting from JOIN fan-out before GROUP BY",
        "difficulty": "hard",
    },
    {
        "id": "window-rank-001",
        "description": "Fix window frame boundary bug in running total",
        "difficulty": "hard",
    },
    {
        "id": "null-handling-001",
        "description": "Fix NULL exclusion bug in WHERE clause",
        "difficulty": "medium",
    },
    {
        "id": "wrong-join-001",
        "description": "Fix INNER JOIN silently dropping unmatched rows",
        "difficulty": "medium",
    },
]

app = create_app(
    SqlDebugEnvironment,
    SqlDebugAction,
    SqlDebugObservation,
    env_name="sql-debug-env",
)


@app.get("/tasks")
def list_tasks() -> list[dict[str, str]]:
    """Return all task ids, descriptions, and difficulties (OpenEnv validator)."""
    return TASKS_PAYLOAD


def main() -> None:
    """CLI entry point for ``uv run server`` and ``python -m server.app``."""
    import uvicorn

    uvicorn.run(
        "server.app:app",
        host="0.0.0.0",
        port=8000,
        workers=1,
    )


if __name__ == "__main__":
    main()
