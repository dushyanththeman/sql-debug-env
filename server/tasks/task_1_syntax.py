"""
Task 1: fix SQL syntax errors (misspelled keywords).
"""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Tuple

TASK_ID = "syntax-fix-001"

# Hardcoded expected result: active employees (active = 1) — name and department.
EXPECTED_ROWS: List[Tuple[Any, ...]] = [
    ("Alice Chen", "Engineering"),
    ("Ben Ortiz", "Engineering"),
    ("Clara Nguyen", "Marketing"),
    ("Diego Alvarez", "HR"),
    ("Elena Brooks", "Marketing"),
    ("Frank Okonkwo", "Engineering"),
]

TASK_CONFIG: Dict[str, Any] = {
    "TASK_ID": TASK_ID,
    "broken_query": "SELCT name, department FROM employees WHER active = 1",
    "expected_rows": EXPECTED_ROWS,
    "expected_row_count": 6,
    "hint": "Check for typos in SQL keywords — SELCT and WHER are not valid SQL",
    "max_steps": 5,
    "check_plan": False,
    "order_matters": False,
    "schema_ddl": """
CREATE TABLE employees (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    department TEXT NOT NULL,
    salary REAL NOT NULL,
    active INTEGER NOT NULL
);
""".strip(),
}


def seed_database(conn: sqlite3.Connection) -> None:
    """Create the employees table and insert eight realistic rows."""
    conn.execute(
        """
        CREATE TABLE employees (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            department TEXT NOT NULL,
            salary REAL NOT NULL,
            active INTEGER NOT NULL
        )
        """
    )
    rows = [
        (1, "Alice Chen", "Engineering", 142000.0, 1),
        (2, "Ben Ortiz", "Engineering", 118500.0, 1),
        (3, "Clara Nguyen", "Marketing", 96500.0, 1),
        (4, "Diego Alvarez", "HR", 87400.0, 1),
        (5, "Elena Brooks", "Marketing", 101200.0, 1),
        (6, "Frank Okonkwo", "Engineering", 129800.0, 1),
        (7, "Grace Patel", "HR", 0.0, 0),
        (8, "Hannah Lee", "Marketing", 0.0, 0),
    ]
    conn.executemany(
        "INSERT INTO employees (id, name, department, salary, active) VALUES (?, ?, ?, ?, ?)",
        rows,
    )
