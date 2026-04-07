"""
Task 6: fix wrong JOIN type — INNER JOIN silently drops customers with no orders.
"""
from __future__ import annotations
import sqlite3
from typing import Any, Dict, List, Tuple

TASK_ID = "wrong-join-001"

EXPECTED_ROWS: List[Tuple[Any, ...]] = [
    ("Alice Chen", 3),
    ("Ben Ortiz", 0),
    ("Clara Nguyen", 2),
    ("Diego Alvarez", 0),
    ("Elena Brooks", 1),
]

TASK_CONFIG: Dict[str, Any] = {
    "TASK_ID": TASK_ID,
    "broken_query": (
        "SELECT c.name, COUNT(o.id) AS order_count\n"
        "FROM customers c\n"
        "INNER JOIN orders o ON o.customer_id = c.id\n"
        "GROUP BY c.id, c.name\n"
        "ORDER BY c.name"
    ),
    "expected_rows": EXPECTED_ROWS,
    "expected_row_count": 5,
    "hint": None,
    "max_steps": 8,
    "check_plan": False,
    "order_matters": True,
    "progressive_hint": "INNER JOIN drops customers with no matching orders. Use LEFT JOIN to keep all customers.",
    "schema_ddl": """
CREATE TABLE customers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL
);
CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    amount REAL NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers(id)
);
""".strip(),
}

def seed_database(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE customers (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        );
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        );
    """)
    customers = [
        (1, "Alice Chen"),
        (2, "Ben Ortiz"),
        (3, "Clara Nguyen"),
        (4, "Diego Alvarez"),
        (5, "Elena Brooks"),
    ]
    conn.executemany("INSERT INTO customers VALUES (?, ?)", customers)
    orders = [
        (1, 1, 100.0),
        (2, 1, 200.0),
        (3, 1, 150.0),
        (4, 3, 80.0),
        (5, 3, 120.0),
        (6, 5, 90.0),
    ]
    conn.executemany("INSERT INTO orders VALUES (?, ?, ?)", orders)
