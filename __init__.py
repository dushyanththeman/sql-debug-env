"""SQL debug OpenEnv package.

Imports are lazy to avoid loading the full OpenEnv/Gradio stack on ``import sql_debug_env``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

__all__ = [
    "SqlDebugAction",
    "SqlDebugObservation",
    "SqlDebugState",
    "SqlDebugEnv",
]


def __getattr__(name: str) -> Any:
    if name == "SqlDebugAction":
        from models import SqlDebugAction

        return SqlDebugAction
    if name == "SqlDebugObservation":
        from models import SqlDebugObservation

        return SqlDebugObservation
    if name == "SqlDebugState":
        from models import SqlDebugState

        return SqlDebugState
    if name == "SqlDebugEnv":
        from client import SqlDebugEnv

        return SqlDebugEnv
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


if TYPE_CHECKING:
    from client import SqlDebugEnv
    from models import SqlDebugAction, SqlDebugObservation, SqlDebugState
