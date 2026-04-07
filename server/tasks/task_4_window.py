"""
Task 4: fix a running total query that uses incorrect window frame,
causing cumulative sum to include future rows instead of only preceding ones.
"""
from __future__ import annotations
import sqlite3
from typing import Any, Dict, List, Tuple

TASK_ID = "window-rank-001"

EXPECTED_ROWS: List[Tuple[Any, ...]] = [
    (1, "2024-01-01", 500.0, 500.0),
    (2, "2024-01-02", 300.0, 800.0),
    (3, "2024-01-03", 750.0, 1550.0),
    (4, "2024-01-04", 200.0, 1750.0),
    (5, "2024-01-05", 900.0, 2650.0),
]

TASK_CONFIG: Dict[str, Any] = {
    "TASK_ID": TASK_ID,
    "broken_query": (
        "SELECT id, sale_date, amount,\n"
        "       SUM(amount) OVER (\n"
        "           ORDER BY sale_date\n"
        "           ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING\n"
        "       ) AS running_total\n"
        "FROM sales\n"
        "ORDER BY sale_date"
    ),
    "expected_rows": EXPECTED_ROWS,
    "expected_row_count": 5,
    "hint": None,
    "progressive_hint": "Check the ROWS BETWEEN clause — UNBOUNDED FOLLOWING includes future rows in the sum.",
    "max_steps": 8,
    "check_plan": False,
    "order_matters": True,
    "schema_ddl": """
CREATE TABLE sales (
    id INTEGER PRIMARY KEY,
    sale_date TEXT NOT NULL,
    amount REAL NOT NULL
);
""".strip(),
}

def seed_database(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE sales (
            id INTEGER PRIMARY KEY,
            sale_date TEXT NOT NULL,
            amount REAL NOT NULL
        )
    """)
    rows = [
        (1, "2024-01-01", 500.0),
        (2, "2024-01-02", 300.0),
        (3, "2024-01-03", 750.0),
        (4, "2024-01-04", 200.0),
        (5, "2024-01-05", 900.0),
    ]
    conn.executemany("INSERT INTO sales VALUES (?, ?, ?)", rows)
