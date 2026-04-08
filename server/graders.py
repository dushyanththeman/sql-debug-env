"""
Score agent SQL submissions against task-specific expected results.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .db import DatabaseManager

_NUMERIC_TOLERANCE = 0.01

_DESTRUCTIVE_PATTERN = re.compile(
    r"\b(DROP|DELETE|UPDATE|INSERT|ALTER|CREATE|ATTACH|DETACH|VACUUM|PRAGMA\s+writable_schema)\b",
    re.IGNORECASE,
)


def is_destructive_sql(sql: str) -> bool:
    """Return True when the query must not be executed (public guard for callers)."""
    return bool(_DESTRUCTIVE_PATTERN.search(sql))


def _is_destructive(sql: str) -> bool:
    """Return True when the query must not be executed."""
    return is_destructive_sql(sql)


def _normalize_cell(value: Any) -> Any:
    """Strip strings and round floats for stable comparisons."""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, float):
        return round(value, 6)
    return value


def _normalize_row(row: Sequence[Any]) -> Tuple[Any, ...]:
    return tuple(_normalize_cell(c) for c in row)


def _rows_close(
    a: Sequence[Sequence[Any]],
    b: Sequence[Sequence[Any]],
    *,
    aggregation_numeric: bool,
) -> bool:
    """Return True when row sets match under task rules."""
    if len(a) != len(b):
        return False
    if not aggregation_numeric:
        sa = {_normalize_row(r) for r in a}
        sb = {_normalize_row(r) for r in b}
        return sa == sb

    if len(a) != len(b):
        return False
    for ra, rb in zip(a, b):
        if len(ra) != len(rb):
            return False
        for x, y in zip(ra, rb):
            if isinstance(x, (int, float)) and isinstance(y, (int, float)):
                if abs(float(x) - float(y)) > _NUMERIC_TOLERANCE:
                    return False
            elif _normalize_cell(x) != _normalize_cell(y):
                return False
    return True


def _plan_qualifies_for_bonus(plan: str) -> bool:
    """
    Return False when EXPLAIN QUERY PLAN shows a disqualifying full table scan.

    Lines that contain ``SCAN`` without ``USING INDEX`` / primary-key search
    are treated as full table scans for scoring purposes.
    """
    try:
        for line in plan.splitlines():
            upper = line.upper()
            if "SCAN" not in upper:
                continue
            if "USING INDEX" in upper:
                continue
            if "USING INTEGER PRIMARY KEY" in upper:
                continue
            if "USING COVERING INDEX" in upper:
                continue
            if "SEARCH" in upper and "USING" in upper:
                continue
            return False
        return True
    except Exception:
        return False


def _clamp_score(raw_score: float) -> float:
    """Clamp scores to validator-safe open interval (0, 1)."""
    return max(0.01, min(0.99, raw_score))


def grade_submission(
    fixed_query: str,
    task_config: Dict[str, Any],
    db_manager: DatabaseManager,
) -> float:
    """
    Compute a score in ``[0.0, 1.0]`` for the agent query.

    Non-aggregation tasks: 0.2 run + 0.3 row count + 0.3 exact rows
    (+0.2 plan when ``check_plan`` is True, else +0.2 when exact and not aggregation).

    Aggregation task: 0.2 run + 0.3 row count + 0.5 value match.
    """
    score, _ = grade_submission_with_feedback(fixed_query, task_config, db_manager)
    return _clamp_score(score)


def grade_submission_with_feedback(
    fixed_query: str,
    task_config: Dict[str, Any],
    db_manager: DatabaseManager,
) -> Tuple[float, Optional[str]]:
    """
    Return ``(score, error_message)`` where error is None on success paths.

    Destructive queries are rejected before execution.
    """
    try:
        task_id = str(task_config.get("TASK_ID", ""))
        if _is_destructive(fixed_query):
            return _clamp_score(0.01), "Destructive queries are not permitted"

        rows, err = db_manager.run_query(fixed_query)
        if err is not None:
            return _clamp_score(0.01), err

        score = 0.2
        expected_count = int(task_config["expected_row_count"])
        actual_count = len(rows)

        if task_id == "aggregation-bug-001":
            return _score_aggregation(
                rows,
                task_config,
                score,
                actual_count,
                expected_count,
                db_manager,
                fixed_query,
            )

        if actual_count != expected_count:
            # Partial credit for proximity: closer row count = higher signal
            if expected_count > 0:
                proximity = 1.0 - min(abs(actual_count - expected_count) / expected_count, 1.0)
                score += round(0.15 * proximity, 4)  # up to 0.15 partial instead of full 0.3
            return _clamp_score(score), None

        score += 0.3
        expected_rows = task_config["expected_rows"]
        order_matters = bool(task_config.get("order_matters", False))
        aggregation_numeric = False

        if order_matters:
            match = _rows_ordered_match(rows, expected_rows)
        else:
            match = _rows_close(rows, expected_rows, aggregation_numeric=False)

        if not match:
            return _clamp_score(score), None

        score += 0.3
        if bool(task_config.get("check_plan", False)):
            plan = db_manager.explain_query_plan(fixed_query)
            if _plan_qualifies_for_bonus(plan):
                score += 0.2
            return _clamp_score(min(1.0, score)), None

        score += 0.2
        return _clamp_score(min(1.0, score)), None
    except Exception as exc:
        return _clamp_score(0.01), str(exc)


def _score_aggregation(
    rows: List[Tuple[Any, ...]],
    task_config: Dict[str, Any],
    base_score: float,
    actual_count: int,
    expected_count: int,
    db_manager: DatabaseManager,
    fixed_query: str,
) -> Tuple[float, Optional[str]]:
    """Scoring path for the aggregation fan-out task."""
    score = base_score
    if actual_count != expected_count:
        if expected_count > 0:
            proximity = 1.0 - min(abs(actual_count - expected_count) / expected_count, 1.0)
            score += round(0.15 * proximity, 4)
        return _clamp_score(score), None

    score += 0.3
    expected_rows = task_config["expected_rows"]
    order_matters = bool(task_config.get("order_matters", False))
    if order_matters:
        match = _rows_ordered_match_numeric(rows, expected_rows)
    else:
        match = _rows_close(rows, expected_rows, aggregation_numeric=True)

    if not match:
        return _clamp_score(score), None

    score += 0.5
    _ = db_manager.explain_query_plan(fixed_query)
    return _clamp_score(min(1.0, score)), None


def _rows_ordered_match(
    actual: Sequence[Sequence[Any]],
    expected: Sequence[Sequence[Any]],
) -> bool:
    if len(actual) != len(expected):
        return False
    for ra, rb in zip(actual, expected):
        if _normalize_row(ra) != _normalize_row(rb):
            return False
    return True


def _rows_ordered_match_numeric(
    actual: Sequence[Sequence[Any]],
    expected: Sequence[Sequence[Any]],
) -> bool:
    if len(actual) != len(expected):
        return False
    for ra, rb in zip(actual, expected):
        if len(ra) != len(rb):
            return False
        for x, y in zip(ra, rb):
            if isinstance(x, (int, float)) and isinstance(y, (int, float)):
                if abs(float(x) - float(y)) > _NUMERIC_TOLERANCE:
                    return False
            elif _normalize_cell(x) != _normalize_cell(y):
                return False
    return True
