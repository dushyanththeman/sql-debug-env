"""
WebSocket client for the SQL debug environment (OpenEnv EnvClient).

Connects to the running server at ``ENV_BASE_URL`` (default ``http://127.0.0.1:8000``).
Uses WebSocket sessions so multi-step episodes keep server-side state.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from openenv.core.client_types import StepResult
from openenv.core.env_client import EnvClient

try:
    from models import SqlDebugAction, SqlDebugObservation, SqlDebugState
except ImportError:
    from sql_debug_env.models import SqlDebugAction, SqlDebugObservation, SqlDebugState


class SqlDebugEnv(EnvClient[SqlDebugAction, SqlDebugObservation, SqlDebugState]):
    """
    Async client that mirrors the OpenEnv pattern for typed actions and observations.

    Use ``async with SqlDebugEnv(base_url=...) as env`` or ``SqlDebugEnv(...).sync()``
    for synchronous code.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        connect_timeout_s: float = 10.0,
        message_timeout_s: float = 60.0,
        max_message_size_mb: float = 100.0,
        provider: Any = None,
        mode: Optional[str] = None,
    ) -> None:
        resolved = base_url or os.getenv("ENV_BASE_URL", "http://127.0.0.1:8000")
        super().__init__(
            resolved,
            connect_timeout_s=connect_timeout_s,
            message_timeout_s=message_timeout_s,
            max_message_size_mb=max_message_size_mb,
            provider=provider,
            mode=mode,
        )

    def _step_payload(self, action: SqlDebugAction) -> Dict[str, Any]:
        """Serialize the action for the WebSocket ``step`` message."""
        return action.model_dump()

    def _parse_result(self, payload: Dict[str, Any]) -> StepResult[SqlDebugObservation]:
        """Deserialize server payloads into :class:`StepResult` objects."""
        obs_raw = payload.get("observation", {})
        observation = SqlDebugObservation(
            task_id=obs_raw.get("task_id", ""),
            schema_ddl=obs_raw.get("schema_ddl", ""),
            broken_query=obs_raw.get("broken_query", ""),
            error_message=obs_raw.get("error_message"),
            last_query_ran=obs_raw.get("last_query_ran"),
            actual_row_count=obs_raw.get("actual_row_count"),
            expected_row_count=int(obs_raw.get("expected_row_count", 0)),
            hint=obs_raw.get("hint"),
            step_number=int(obs_raw.get("step_number", 0)),
            max_steps=int(obs_raw.get("max_steps", 0)),
            score_so_far=float(obs_raw.get("score_so_far", 0.0)),
            step_info=obs_raw.get("step_info"),
            done=bool(payload.get("done", False)),
            reward=payload.get("reward"),
            metadata=obs_raw.get("metadata", {}),
        )
        return StepResult(
            observation=observation,
            reward=payload.get("reward"),
            done=bool(payload.get("done", False)),
        )

    def _parse_state(self, payload: Dict[str, Any]) -> SqlDebugState:
        """Deserialize ``/state`` responses into :class:`SqlDebugState`."""
        return SqlDebugState(
            episode_id=payload.get("episode_id"),
            step_count=int(payload.get("step_count", 0)),
            task_id=str(payload.get("task_id", "")),
            total_reward=float(payload.get("total_reward", 0.0)),
            steps_taken=int(payload.get("steps_taken", 0)),
            best_score_so_far=float(payload.get("best_score_so_far", 0.0)),
            is_done=bool(payload.get("is_done", False)),
        )
