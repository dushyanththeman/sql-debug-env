"""
Task 5: fix NULL handling bug — WHERE column != 'value' silently excludes NULLs.
"""
from __future__ import annotations
import sqlite3
from typing import Any, Dict, List, Tuple

TASK_ID = "null-handling-001"

# Correct result: all employees NOT in Engineering, INCLUDING those with NULL department
EXPECTED_ROWS: List[Tuple[Any, ...]] = [
    ("Clara Nguyen", None),
    ("Diego Alvarez", "HR"),
    ("Elena Brooks", "Marketing"),
    ("Grace Patel", None),
]

TASK_CONFIG: Dict[str, Any] = {
    "TASK_ID": TASK_ID,
    "broken_query": (
        "SELECT name, department FROM employees\n"
        "WHERE department != 'Engineering'\n"
        "ORDER BY name"
    ),
    "expected_rows": EXPECTED_ROWS,
    "expected_row_count": 4,
    "hint": None,
    "max_steps": 8,
    "check_plan": False,
    "order_matters": True,
    "progressive_hint": "In SQL, NULL != 'Engineering' evaluates to NULL, not TRUE. Use IS NULL to include rows with no department.",
    "schema_ddl": """
CREATE TABLE employees (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    department TEXT,
    salary REAL NOT NULL,
    active INTEGER NOT NULL
);
""".strip(),
}

def seed_database(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE employees (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            department TEXT,
            salary REAL NOT NULL,
            active INTEGER NOT NULL
        )
    """)
    rows = [
        (1, "Alice Chen", "Engineering", 142000.0, 1),
        (2, "Ben Ortiz", "Engineering", 118500.0, 1),
        (3, "Clara Nguyen", None, 96500.0, 1),
        (4, "Diego Alvarez", "HR", 87400.0, 1),
        (5, "Elena Brooks", "Marketing", 101200.0, 1),
        (6, "Frank Okonkwo", "Engineering", 129800.0, 1),
        (7, "Grace Patel", None, 76000.0, 1),
    ]
    conn.executemany("INSERT INTO employees VALUES (?, ?, ?, ?, ?)", rows)
