"""Tests for ``graders.grade_submission``."""

from __future__ import annotations

import sqlite3

import pytest

from sql_debug_env.server.db import DatabaseManager
from sql_debug_env.server.graders import grade_submission
from sql_debug_env.server.tasks import task_1_syntax, task_2_join, task_3_aggregation


def _db_with_task(seed_fn) -> DatabaseManager:
    db = DatabaseManager()
    db.initialize(seed_fn)
    return db


def test_task1_wrong_query_zero() -> None:
    """A syntactically invalid query should score 0.0."""
    db = _db_with_task(task_1_syntax.seed_database)
    score = grade_submission("SELECT * FROM nowhere", task_1_syntax.TASK_CONFIG, db)
    assert score == 0.0
    db.close()


def test_task1_runs_wrong_rows_partial() -> None:
    """Valid SQL with wrong cardinality should land in the 0.2–0.5 band."""
    db = _db_with_task(task_1_syntax.seed_database)
    score = grade_submission(
        "SELECT name FROM employees WHERE active = 1",
        task_1_syntax.TASK_CONFIG,
        db,
    )
    assert 0.2 <= score <= 0.5
    db.close()


def test_task1_perfect_score() -> None:
    """The reference fix should reach 1.0."""
    db = _db_with_task(task_1_syntax.seed_database)
    sql = "SELECT name, department FROM employees WHERE active = 1;"
    score = grade_submission(sql, task_1_syntax.TASK_CONFIG, db)
    assert score == 1.0
    db.close()


def test_destructive_query_blocked() -> None:
    """Destructive statements never execute and always score 0.0."""
    db = _db_with_task(task_1_syntax.seed_database)
    score = grade_submission(
        "DROP TABLE employees;",
        task_1_syntax.TASK_CONFIG,
        db,
    )
    assert score == 0.0
    conn = db.conn
    assert conn is not None
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='employees'"
    )
    assert cur.fetchone() is not None
    db.close()


def test_task2_join_expected() -> None:
    """JOIN rewrite should match expected rows and plan bonus when applicable."""
    db = _db_with_task(task_2_join.seed_database)
    sql = (
        "SELECT o.id, o.amount, u.name AS user_name "
        "FROM orders o JOIN users u ON u.id = o.user_id "
        "ORDER BY o.created_at DESC;"
    )
    score = grade_submission(sql, task_2_join.TASK_CONFIG, db)
    assert score == 1.0
    db.close()


def test_task3_aggregation_fix() -> None:
    """COUNT DISTINCT + SUM should match hardcoded expected rows."""
    db = _db_with_task(task_3_aggregation.seed_database)
    sql = (
        "SELECT c.name, COUNT(DISTINCT o.id) AS order_count, SUM(i.price) AS total_spent "
        "FROM customers c "
        "JOIN orders o ON o.customer_id = c.id AND o.status = 'completed' "
        "JOIN order_items i ON i.order_id = o.id "
        "GROUP BY c.id, c.name "
        "ORDER BY total_spent DESC;"
    )
    score = grade_submission(sql, task_3_aggregation.TASK_CONFIG, db)
    assert score == 1.0
    db.close()
