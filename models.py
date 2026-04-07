"""
Pydantic models for the SQL debug environment.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from openenv.core.env_server.types import Action, Observation, State
from pydantic import Field


class SqlDebugAction(Action):
    """Agent action: a single corrected SQL string."""

    fixed_query: str = Field(
        description="The agent's corrected or optimised SQL query string"
    )


class SqlDebugObservation(Observation):
    """Observation returned after reset or each step."""

    task_id: str = Field(description="Which task is currently active")
    schema_ddl: str = Field(
        description="CREATE TABLE DDL statements for all tables in scope"
    )
    broken_query: str = Field(
        description="The original broken query the agent must fix"
    )
    error_message: Optional[str] = Field(
        default=None,
        description="SQLite error from the agent's last attempt, or None if no error",
    )
    last_query_ran: Optional[str] = Field(
        default=None,
        description="The exact query the agent submitted on the previous step",
    )
    actual_row_count: Optional[int] = Field(
        default=None,
        description="Row count returned by the agent's last query attempt",
    )
    expected_row_count: int = Field(
        description="Number of rows the correct query must return"
    )
    hint: Optional[str] = Field(
        default=None,
        description="Optional hint — only present on Task 1 (easy)",
    )
    step_number: int = Field(description="Current step number within the episode")
    max_steps: int = Field(description="Maximum steps allowed for this task")
    score_so_far: float = Field(
        default=0.0, description="Cumulative score this episode"
    )
    step_info: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Diagnostics for the last step (task_id, step, score, error)",
    )


class SqlDebugState(State):
    """Serializable environment state for clients."""

    task_id: str = Field(description="Active task identifier")
    total_reward: float = Field(default=0.0, description="Sum of step rewards")
    steps_taken: int = Field(default=0, description="Steps taken this episode")
    best_score_so_far: float = Field(
        default=0.0, description="Best single-step score seen this episode"
    )
    is_done: bool = Field(default=False, description="Whether the episode has ended")
