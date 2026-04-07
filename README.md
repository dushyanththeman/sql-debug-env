---
title: Sql Debug Env
emoji: 🛢️
colorFrom: blue
colorTo: green
sdk: docker
pinned: false
app_port: 8000
---

# sql-debug-env

> **OpenEnv environment for the Meta × Hugging Face × Scaler AI Hackathon**
> An RL environment where AI agents debug and optimise broken SQL queries against a live SQLite database — simulating real data engineering workflows.

---

## 1. Overview

SQL debugging is one of the most frequent real-world tasks for data engineers, analysts, and backend developers. Mistakes like keyword typos, N+1 correlated subqueries, JOIN fan-out before GROUP BY, incorrect window frame boundaries, NULL mishandling, and wrong JOIN types cause silent data errors in production daily.

This environment gives RL agents a structured way to learn SQL debugging through iterative feedback. The agent receives a broken SQL query and a database schema, submits corrected `SELECT` statements against a live in-memory SQLite database, and receives graded rewards based on correctness and (for one task) query plan efficiency.

Each episode is fully isolated — a fresh in-memory SQLite database is seeded per task, per reset. The environment is stateless across episodes and safe for concurrent use.

---

## 2. Environment Description

- **Input to agent:** Task ID, full schema DDL, the broken query, error from last attempt (if any), last submitted query, actual vs expected row counts, step counter, max steps, cumulative score, and optional progressive hints.
- **Agent action:** A single corrected SQL `SELECT` string.
- **Feedback:** A score from `0.0–1.0` per step with partial credit signals, plus structured error messages from SQLite execution.
- **Episode termination:** Perfect score (`1.0`) on any step, or max steps reached.
- **Destructive SQL:** Any query containing `DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, or similar DDL/DML is blocked before execution and scores `0.0`.

---

## 3. Action Space

| Field | Type | Description |
|---|---|---|
| `fixed_query` | `str` | The agent's corrected or optimised SQL query. Must be a `SELECT` statement. |
| `metadata` | `dict` | Optional metadata (OpenEnv base field). |

Model: `SqlDebugAction` in `models.py`.

---

## 4. Observation Space

| Field | Type | Description |
|---|---|---|
| `task_id` | `str` | Active task identifier (e.g. `syntax-fix-001`). |
| `schema_ddl` | `str` | `CREATE TABLE` statements for all tables in the episode database. |
| `broken_query` | `str` | The original broken query the agent must fix. |
| `error_message` | `Optional[str]` | SQLite error from the last attempt, or `None` if no error. |
| `last_query_ran` | `Optional[str]` | The exact query submitted on the previous step. |
| `actual_row_count` | `Optional[int]` | Row count returned by the last query attempt. |
| `expected_row_count` | `int` | Target row count the correct query must return. |
| `hint` | `Optional[str]` | Always shown on the easy task. Unlocks after 2 failed steps on harder tasks. |
| `step_number` | `int` | Current step number within the episode. |
| `max_steps` | `int` | Maximum steps allowed for this task. |
| `score_so_far` | `float` | Cumulative reward this episode. |
| `step_info` | `dict \| null` | Diagnostics: `task_id`, `step`, `score`, `error`. |
| `done` / `reward` | base fields | Episode termination flag and last step reward. |

Model: `SqlDebugObservation` in `models.py`.

---

## 5. Tasks

| ID | Difficulty | Max Steps | Objective |
|---|---|---|---|
| `syntax-fix-001` | Easy | 5 | Fix typos in SQL keywords (`SELCT`, `WHER`) |
| `join-optimization-001` | Medium | 6 | Replace N+1 correlated subquery with efficient JOIN |
| `aggregation-bug-001` | Hard | 8 | Fix double-counting from JOIN fan-out before GROUP BY |
| `window-rank-001` | Hard | 8 | Fix window frame boundary bug in running total |
| `null-handling-001` | Medium | 8 | Fix NULL exclusion bug in WHERE clause |
| `wrong-join-001` | Medium | 8 | Fix INNER JOIN silently dropping unmatched rows |

### Task Details

**`syntax-fix-001` — Easy**
The query has two keyword typos: `SELCT` and `WHER`. The agent must return a valid `SELECT` returning 6 active employee rows (name, department). A hint is always visible.

**`join-optimization-001` — Medium**
A correlated subquery runs once per row to look up the user name — the classic N+1 pattern. The agent must rewrite it as a `JOIN`. The grader also checks `EXPLAIN QUERY PLAN` and awards a bonus for avoiding full table scans.

**`aggregation-bug-001` — Hard**
The query runs successfully and returns plausible-looking numbers, but `COUNT(o.id)` and `SUM(i.price)` are silently double-counted because `order_items` fans out rows before `GROUP BY`. The fix requires `COUNT(DISTINCT o.id)` or pre-aggregating items in a subquery.

**`window-rank-001` — Hard**
`SUM(amount) OVER (... ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING)` sums the entire table for every row instead of computing a running total. The fix is `ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW`.

**`null-handling-001` — Medium**
`WHERE department != 'Engineering'` silently excludes rows where `department IS NULL` because `NULL != 'Engineering'` evaluates to `NULL`, not `TRUE`. The fix requires `OR department IS NULL`.

**`wrong-join-001` — Medium**
`INNER JOIN` drops customers with zero orders from the result. The fix is `LEFT JOIN` to retain all customers, returning `0` for those with no orders.

---

## 6. Reward Function

### Non-aggregation tasks (`syntax-fix-001`, `join-optimization-001`, `null-handling-001`, `wrong-join-001`, `window-rank-001`)

| Condition | Score |
|---|---|
| Query fails to parse or execute | `0.0` |
| Query runs without error | `+0.2` (cumulative `0.2`) |
| Row count matches expected (partial credit if close) | `+0.3` (cumulative `0.5`) |
| Exact row match to expected set | `+0.3` (cumulative `0.8`) |
| Plan bonus (`check_plan=true`, task 2 only): no full table scan | `+0.2` (cumulative `1.0`) |
| No plan check (`check_plan=false`): row match already satisfied | `+0.2` (cumulative `1.0`) |

### Aggregation task (`aggregation-bug-001`)

| Condition | Score |
|---|---|
| Query fails to execute | `0.0` |
| Query runs | `+0.2` |
| Correct row count | `+0.3` (cumulative `0.5`) |
| Correct names, counts, and totals (within `0.01` float tolerance) | `+0.5` (cumulative `1.0`) |

### Partial credit for row count proximity

If the row count is wrong but close, a partial signal of up to `+0.15` is awarded proportional to proximity:

```
proximity = 1.0 - min(|actual - expected| / expected, 1.0)
partial_credit = 0.15 * proximity
```

This gives the agent a gradient signal even when the count is off, rather than a flat `0.5` cliff.

### Step efficiency bonus

Solving a task faster earns a bonus on top of the perfect score:

```
efficiency_bonus = 0.2 * max(0, (max_steps - step_number) / max_steps)
step_reward = min(1.0, raw_score + efficiency_bonus)
```

### Progressive hints

- **Task 1 (`syntax-fix-001`):** Hint always visible.
- **Tasks 2–6:** Hint unlocks after 2 failed steps with no perfect score, giving the agent a nudge without giving away the answer upfront.

### Destructive SQL

Any query matching `DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `CREATE`, `ATTACH`, `DETACH`, `VACUUM`, or `PRAGMA writable_schema` scores `0.0` and is never executed.

---

## 7. Setup and Usage

### Install

```bash
cd sql_debug_env
pip install -e .
# or with uv:
uv sync
```

### Run the server

```bash
python -m sql_debug_env.server.app
# or with uv:
uv run server
```

Server starts at `http://0.0.0.0:8000`. Swagger UI at `http://localhost:8000/docs`.

### Docker

Build from the environment root (the directory containing `pyproject.toml`):

```bash
docker build -f server/Dockerfile -t sql-debug-env .
docker run --rm -p 8000:8000 sql-debug-env
```

### Validate

```bash
# Structural validation
openenv validate

# Runtime validation (with server running)
openenv validate --url http://127.0.0.1:8000
```

### Run baseline inference

```bash
export HF_TOKEN=your_api_key_here
export ENV_BASE_URL=http://127.0.0.1:8000
python -m sql_debug_env.inference
# or directly:
python inference.py
```

---

## 8. Baseline Scores

Run with `llama-3.3-70b-versatile` via Groq (OpenAI-compatible client):

| Task | Difficulty | Baseline Score |
|---|---|---|
| `syntax-fix-001` | Easy | 1.000 |
| `join-optimization-001` | Medium | 1.000 |
| `aggregation-bug-001` | Hard | 1.000 |
| `window-rank-001` | Hard | 1.000 |
| `null-handling-001` | Medium | 1.000 |
| `wrong-join-001` | Medium | 1.000 |

**Average across all tasks: 1.000**

Model: `llama-3.3-70b-versatile` via `https://api.groq.com/openai/v1`

---

## 9. Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `HF_TOKEN` | Yes | none | Hugging Face token or API key for LLM inference. Used first. |
| `API_KEY` | Fallback | none | Alternative API key if `HF_TOKEN` is not set. |
| `API_BASE_URL` | No | `https://router.huggingface.co/v1` | OpenAI-compatible API endpoint. |
| `MODEL_NAME` | No | `Qwen/Qwen2.5-72B-Instruct` | Chat model identifier. |
| `ENV_BASE_URL` | No | `http://127.0.0.1:8000` | URL of the running environment server. |
| `LOCAL_IMAGE_NAME` | No | `sql-debug-env` | Docker image name hint for local runs. |

---

## 10. Project Structure

```
sql_debug_env/
├── inference.py              # Baseline inference script (mandatory at root)
├── models.py                 # SqlDebugAction, SqlDebugObservation, SqlDebugState
├── client.py                 # SqlDebugEnv HTTP client
├── __init__.py               # Package exports
├── openenv.yaml              # OpenEnv spec metadata
├── pyproject.toml
├── README.md
└── server/
    ├── Dockerfile
    ├── requirements.txt
    ├── app.py                # FastAPI application
    ├── sql_environment.py    # Environment logic
    ├── graders.py            # Scoring and grader functions
    ├── db.py                 # DatabaseManager (in-memory SQLite)
    └── tasks/
        ├── __init__.py
        ├── task_1_syntax.py        # syntax-fix-001
        ├── task_2_join.py          # join-optimization-001
        ├── task_3_aggregation.py   # aggregation-bug-001
        ├── task_4_window.py        # window-rank-001
        ├── task_5_null.py          # null-handling-001
        └── task_6_join.py          # wrong-join-001
```

---

## 11. API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health probe — returns `{"status": "healthy"}` |
| `GET` | `/metadata` | Environment name, description, version |
| `GET` | `/schema` | Action, observation, and state JSON schemas |
| `POST` | `/reset` | Start new episode. Optional body: `{"task_id": "syntax-fix-001"}` |
| `POST` | `/step` | Submit action. Body: `{"fixed_query": "SELECT ..."}` |
| `GET` | `/state` | Current episode state |
| `POST` | `/mcp` | MCP JSON-RPC endpoint |
| `GET` | `/openapi.json` | OpenAPI spec |
| `GET` | `/docs` | Swagger UI |

---

## 12. Design Principles

**Full episode isolation.** Each `reset()` creates a fresh in-memory SQLite database. No state leaks between episodes. Safe for concurrent sessions.

**Partial reward signals.** The grader awards incremental scores at each correctness milestone (executes → row count → exact rows → plan quality) rather than binary pass/fail. This gives agents a meaningful gradient to learn from.

**Real-world task fidelity.** Every task replicates a bug class that engineers encounter in production: not toy puzzles, but the actual failure modes that cause incorrect dashboards, slow queries, and silent data corruption.

**Deterministic grading.** Expected rows are hardcoded in each task config. Graders never raise exceptions — all code paths return a float in `[0.0, 1.0]`.

**Destructive query guard.** A regex pre-check blocks `DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, and related statements before they reach SQLite execution.

---

## 13. Submission

- **Hugging Face Space:** Deploy this package as a Docker Space. The Space must respond to `/health` and `/reset`.
- **GitHub:** Push source to a public GitHub repository.
- **Validate before submitting:**

```bash
# Local structural check
openenv validate

# Against deployed Space
openenv validate --url https://YOUR_USERNAME-sql-debug-env.hf.space

# Full pre-submission validator
chmod +x validate-submission.sh
./validate-submission.sh https://YOUR_USERNAME-sql-debug-env.hf.space
```

---

## 14. Why This Environment Matters

Training agents to debug SQL closes a real gap in the RL/agent evaluation ecosystem. Existing benchmarks focus on SQL generation from scratch (Text-to-SQL). This environment instead focuses on **iterative repair** — which is what engineers actually spend time on. An agent that can:

- Spot and fix syntax errors
- Identify N+1 query patterns and rewrite them
- Detect silent aggregation bugs from fan-out
- Understand window function frame semantics
- Handle NULL propagation correctly
- Choose the right JOIN type

...is an agent that can meaningfully assist in real data engineering workflows. This environment provides the structured, graded feedback loop needed to train and evaluate exactly that capability.

---

**Author:** Dushyanth S
**Version:** 0.1.0
**License:** MIT
