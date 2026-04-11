"""
Baseline LLM loop for the SQL debug environment (OpenEnv hackathon baseline).

Emits machine-parseable ``[START]``, ``[STEP]``, ``[END]`` lines for automated judging.
"""

from __future__ import annotations

import asyncio
import os
import re
import textwrap
from typing import List, Optional

from openai import OpenAI

try:
    from models import SqlDebugAction
    from client import SqlDebugEnv
    from server.graders import _clamp
except ImportError:
    from sql_debug_env.models import SqlDebugAction
    from sql_debug_env.client import SqlDebugEnv
    from sql_debug_env.server.graders import _clamp

API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-72B-Instruct")
HF_TOKEN = os.getenv("HF_TOKEN")
ENV_BASE_URL = os.getenv("ENV_BASE_URL", "http://127.0.0.1:8000")
MAX_STEPS = 8
SUCCESS_THRESHOLD = 0.8

_SYSTEM_PROMPT = textwrap.dedent(
    """\
    You are an expert SQL debugger and query optimiser.

    You will receive:
    - A database schema (CREATE TABLE statements)
    - A broken or inefficient SQL query
    - An error message from the last attempt (if any)
    - The row count your last query returned vs the expected row count
    - Your previous query attempt

    Your job: return ONLY a single corrected SQL SELECT query. Nothing else.
    No explanation, no markdown, no backticks. Just the raw SQL query ending with a semicolon.

    Rules:
    1. Only write SELECT queries. Never use DROP, DELETE, UPDATE, INSERT, or ALTER.
    2. If you see a syntax error, fix the keywords first.
    3. If row counts don't match, check your JOIN conditions and WHERE clauses.
    4. If optimising, prefer JOINs over correlated subqueries.
    5. For aggregation bugs, check if JOINs are causing fan-out before GROUP BY.
    """
).strip()


def _normalize_score_display(raw: float) -> float:
    """Map internal (0.01, 0.99) rewards to an open interval — never exactly 0.0 or 1.0."""
    x = (float(raw) - 0.01) / 0.98
    return max(0.001, min(0.999, x))


def _clamp_aggregate(score: float) -> float:
    """Clamp aggregate / averaged values used for reporting (strictly between 0 and 1)."""
    return max(0.01, min(0.99, float(score)))


def _extract_sql(text: str) -> str:
    """Strip fences and take the first plausible SELECT statement."""
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:sql)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = cleaned.strip()
    if ";" in cleaned:
        cleaned = cleaned.split(";")[0].strip() + ";"
    elif not cleaned.endswith(";"):
        cleaned = cleaned + ";"
    return cleaned


def _sanitize_log_value(value: str, max_len: int = 200) -> str:
    """Single-line log field: no newlines, truncated."""
    single = " ".join(value.split())
    if len(single) > max_len:
        return single[: max_len - 3] + "..."
    return single


def _format_step_log(
    step: int,
    action: str,
    reward: float,
    done: bool,
    error: Optional[str],
) -> str:
    err = "null" if not error else _sanitize_log_value(error, 120)
    return (
        f"[STEP] step={step} action={_sanitize_log_value(action)} "
        f"reward={reward:.2f} done={str(done).lower()} error={err}"
    )


async def _run_one_task(
    env: SqlDebugEnv,
    client: OpenAI,
    task_id: str,
    model_name: str,
) -> tuple[float, int, List[float], float]:
    """Run a single task; returns cumulative score, steps, rewards, normalized episode score."""
    rewards: List[float] = []
    print(
        f"[START] task={task_id} env=sql-debug-env model={model_name}",
        flush=True,
    )
    obs = None
    steps_used = 0
    success = False
    total_score = 0.0
    episode_norm = _normalize_score_display(_clamp(0.0))

    try:
        result = await env.reset(task_id=task_id)
        obs = result.observation
        for step_idx in range(1, MAX_STEPS + 1):
            user_prompt = textwrap.dedent(
                f"""\
                Task: {obs.task_id}
                Step: {obs.step_number} / {obs.max_steps}

                === DATABASE SCHEMA ===
                {obs.schema_ddl}

                === ORIGINAL BROKEN QUERY ===
                {obs.broken_query}

                === YOUR LAST ATTEMPT ===
                {obs.last_query_ran if obs.last_query_ran else "No attempt yet — this is your first step."}

                === RESULT OF YOUR LAST ATTEMPT ===
                Error: {obs.error_message if obs.error_message else "None — query ran successfully"}
                Rows returned: {obs.actual_row_count if obs.actual_row_count is not None else "N/A"}
                Rows expected: {obs.expected_row_count}
                Score so far: {obs.score_so_far:.2f}

                {f"HINT: {obs.hint}" if obs.hint else ""}

                Return ONLY your corrected SQL query:
                """
            ).strip()

            completion = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=300,
                temperature=0.2,
            )
            raw = completion.choices[0].message.content or ""
            sql = _extract_sql(raw)

            step_result = await env.step(SqlDebugAction(fixed_query=sql))
            obs = step_result.observation
            reward = _clamp(
                float(step_result.reward if step_result.reward is not None else 0.0)
            )
            done = bool(step_result.done)
            err = obs.error_message
            rewards.append(reward)
            steps_used = step_idx

            print(
                _format_step_log(step_idx, sql, reward, done, err),
                flush=True,
            )

            if done:
                success = _normalize_score_display(reward) >= SUCCESS_THRESHOLD
                break

        total_score = float(obs.score_so_far) if obs is not None else 0.0
    finally:
        if rewards:
            episode_norm = _normalize_score_display(max(rewards))
        else:
            episode_norm = _normalize_score_display(_clamp(0.0))
        reward_str = ",".join(f"{r:.2f}" for r in rewards) if rewards else ""
        print(
            f"[END] success={str(success).lower()} steps={steps_used} "
            f"score={episode_norm:.3f} rewards={reward_str}",
            flush=True,
        )

    return total_score, steps_used, rewards, episode_norm


async def main_async() -> None:
    """Run all six tasks sequentially against a live server."""
    if HF_TOKEN is None:
        raise RuntimeError("HF_TOKEN must be set for inference (LLM calls require credentials).")

    client = OpenAI(base_url=API_BASE_URL, api_key=HF_TOKEN)

    task_ids = [
        "syntax-fix-001",
        "join-optimization-001",
        "aggregation-bug-001",
        "window-rank-001",
        "null-handling-001",
        "wrong-join-001",
    ]
    scores: List[float] = []

    async with SqlDebugEnv(base_url=ENV_BASE_URL) as env:
        for tid in task_ids:
            _, _, _, episode_norm = await _run_one_task(env, client, tid, MODEL_NAME)
            scores.append(episode_norm)

    if scores:
        avg_raw = sum(scores) / len(scores)
        avg = _clamp_aggregate(avg_raw)
        print(f"Average score across tasks: {avg:.3f}", flush=True)


def main() -> None:
    """Entry point for ``python inference.py`` from the environment root."""
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
