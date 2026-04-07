"""
FastAPI application exposing the SQL debug environment over HTTP/WebSocket.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.routing import APIRoute
from openenv.core.env_server import create_app

from sql_debug_env.models import SqlDebugAction, SqlDebugObservation

from .sql_environment import SqlDebugEnvironment

app = create_app(
    SqlDebugEnvironment,
    SqlDebugAction,
    SqlDebugObservation,
)


def _strip_default_health(fastapi_app: FastAPI) -> None:
    """Remove the default OpenEnv /health route so we can expose a richer payload."""
    kept: list = []
    for route in fastapi_app.router.routes:
        if isinstance(route, APIRoute) and route.path == "/health":
            methods = getattr(route, "methods", None) or set()
            if methods == {"GET"}:
                continue
        kept.append(route)
    fastapi_app.router.routes = kept


_strip_default_health(app)


@app.get("/health")
def health_check() -> dict[str, str]:
    """Health probe compatible with ``openenv validate`` and Docker HEALTHCHECK."""
    return {"status": "healthy", "env": "sql-debug-env"}


def main() -> None:
    """CLI entry point for ``uv run server`` and ``python -m sql_debug_env.server.app``."""
    import uvicorn

    uvicorn.run(
        "sql_debug_env.server.app:app",
        host="0.0.0.0",
        port=8000,
        workers=1,
    )


if __name__ == "__main__":
    main()
