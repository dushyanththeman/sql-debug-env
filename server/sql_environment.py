"""
Server-side SQL debug environment implementation.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
from uuid import uuid4

from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import EnvironmentMetadata

from sql_debug_env.models import SqlDebugAction, SqlDebugObservation, SqlDebugState

from .db import DatabaseManager
from .graders import grade_submission_with_feedback, is_destructive_sql
from .tasks import TASK_ORDER, TASK_REGISTRY


class SqlDebugEnvironment(Environment[SqlDebugAction, SqlDebugObservation, SqlDebugState]):
    """
    Episodic environment where an agent submits SQL and receives graded feedback.

    Each episode uses an isolated in-memory SQLite database seeded from the task.
    """

    SUPPORTS_CONCURRENT_SESSIONS: bool = True

    def __init__(self) -> None:
        super().__init__()
        self._episode_id: str = str(uuid4())
        self._rotation_index: int = 0
        self._current_task: Dict[str, Any] = dict(TASK_ORDER[0])
        self._db: Optional[DatabaseManager] = None
        self._step_count: int = 0
        self._cumulative_score: float = 0.0
        self._best_score: float = 0.0
        self._last_query: Optional[str] = None
        self._last_error: Optional[str] = None
        self._last_row_count: Optional[int] = None
        self._done: bool = False

    def _pick_task(self, task_id: Optional[str]) -> Dict[str, Any]:
        if task_id is not None:
            if task_id not in TASK_REGISTRY:
                raise ValueError(f"Unknown task_id: {task_id}")
            return dict(TASK_REGISTRY[task_id])
        cfg = TASK_ORDER[self._rotation_index % len(TASK_ORDER)]
        self._rotation_index = (self._rotation_index + 1) % len(TASK_ORDER)
        return dict(cfg)

    def _build_observation(
        self,
        *,
        after_step: bool,
        step_reward: Optional[float] = None,
        step_info: Optional[Dict[str, Any]] = None,
    ) -> SqlDebugObservation:
        task = self._current_task
        obs_reward = step_reward if after_step else None
        return SqlDebugObservation(
            task_id=task["TASK_ID"],
            schema_ddl=task["schema_ddl"],
            broken_query=task["broken_query"],
            error_message=self._last_error,
            last_query_ran=self._last_query,
            actual_row_count=self._last_row_count,
            expected_row_count=int(task["expected_row_count"]),
            hint=self._get_hint(task),
            step_number=self._step_count,
            max_steps=int(task["max_steps"]),
            score_so_far=self._cumulative_score,
            done=self._done,
            reward=obs_reward,
            step_info=(dict(step_info) if step_info else None),
            metadata={},
        )

    def reset(
        self,
        seed: Optional[int] = None,
        episode_id: Optional[str] = None,
        **kwargs: Any,
    ) -> SqlDebugObservation:
        """Start a new episode, optionally selecting a task by id."""
        self._reset_rubric()
        self._episode_id = episode_id or str(uuid4())
        task_id = kwargs.get("task_id")
        if isinstance(task_id, str):
            self._current_task = self._pick_task(task_id)
        else:
            self._current_task = self._pick_task(None)

        self._db = DatabaseManager()
        seed_fn = self._current_task["_seed_fn"]
        self._db.initialize(seed_fn)

        self._step_count = 0
        self._cumulative_score = 0.0
        self._best_score = 0.0
        self._last_query = None
        self._last_error = None
        self._last_row_count = None
        self._done = False

        return self._build_observation(after_step=False)

    def step(
        self,
        action: SqlDebugAction,
        timeout_s: Optional[float] = None,
        **kwargs: Any,
    ) -> SqlDebugObservation:
        """Grade the submitted query and return the next observation."""
        assert self._db is not None
        task = self._current_task
        max_steps = int(task["max_steps"])

        raw_score, feedback_err = grade_submission_with_feedback(
            action.fixed_query,
            task,
            self._db,
        )

        self._last_query = action.fixed_query
        self._last_error = feedback_err

        if is_destructive_sql(action.fixed_query):
            self._last_row_count = None
        else:
            rows, run_err = self._db.run_query(action.fixed_query)
            if run_err is not None:
                self._last_row_count = None
                if self._last_error is None:
                    self._last_error = run_err
            else:
                self._last_row_count = len(rows)

        self._step_count += 1

        step_reward = float(raw_score)
        if raw_score >= 1.0:
            # Efficiency bonus: reward solving faster. Max +0.2 on step 1, 0 by step 8
            max_steps = int(task["max_steps"])
            efficiency_bonus = 0.2 * max(0, (max_steps - self._step_count) / max_steps)
            step_reward = min(1.0, raw_score + efficiency_bonus)

        self._cumulative_score += step_reward
        self._best_score = max(self._best_score, raw_score)

        done = bool(raw_score >= 1.0 or self._step_count >= max_steps)
        self._done = done

        info = {
            "task_id": task["TASK_ID"],
            "step": self._step_count,
            "score": raw_score,
            "error": feedback_err,
        }
        return self._build_observation(
            after_step=True,
            step_reward=step_reward,
            step_info=info,
        )

    @property
    def state(self) -> SqlDebugState:
        """Return structured state for HTTP/WebSocket clients."""
        task = self._current_task
        return SqlDebugState(
            episode_id=self._episode_id,
            step_count=self._step_count,
            task_id=task["TASK_ID"],
            total_reward=self._cumulative_score,
            steps_taken=self._step_count,
            best_score_so_far=self._best_score,
            is_done=self._done,
        )

    def get_metadata(self) -> EnvironmentMetadata:
        """Describe this environment for OpenEnv tooling."""
        return EnvironmentMetadata(
            name="sql-debug-env",
            description="Debug and optimise broken SQL queries against a live SQLite database.",
            version="0.1.0",
            author="Dushyanth S",
        )

    def _get_hint(self, task: Dict[str, Any]) -> Optional[str]:
        """Return hint only on easy task upfront, or after 2 failed steps on harder tasks."""
        static_hint = task.get("hint")
        if static_hint:
            return static_hint  # task 1 always shows hint
        # Progressive hint: unlock after step 2 with no perfect score yet
        if self._step_count >= 2 and self._best_score < 1.0:
            return task.get("progressive_hint")
        return None

    def close(self) -> None:
        """Release database resources."""
        if self._db is not None:
            self._db.close()
            self._db = None


def _attach_seed_functions() -> None:
    """Populate task configs with seed callables (avoids circular imports)."""
    from .tasks import task_1_syntax, task_2_join, task_3_aggregation, task_4_window, task_5_null, task_6_join

    task_1_syntax.TASK_CONFIG["_seed_fn"] = task_1_syntax.seed_database
    task_2_join.TASK_CONFIG["_seed_fn"] = task_2_join.seed_database
    task_3_aggregation.TASK_CONFIG["_seed_fn"] = task_3_aggregation.seed_database
    task_4_window.TASK_CONFIG["_seed_fn"] = task_4_window.seed_database
    task_5_null.TASK_CONFIG["_seed_fn"] = task_5_null.seed_database
    task_6_join.TASK_CONFIG["_seed_fn"] = task_6_join.seed_database


_attach_seed_functions()
