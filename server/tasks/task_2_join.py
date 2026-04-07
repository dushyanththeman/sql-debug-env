"""
Task 2: replace correlated subquery (N+1) with an efficient JOIN.
"""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Tuple

TASK_ID = "join-optimization-001"

# Order matters: same as ORDER BY o.created_at DESC (newest first).
EXPECTED_ROWS: List[Tuple[Any, ...]] = [
    (20, 120.0, "Nina Rossi"),
    (19, 116.5, "Oliver Grant"),
    (18, 113.0, "Priya Singh"),
    (17, 109.5, "Marcus Webb"),
    (16, 106.0, "Alice Chen"),
    (15, 102.5, "Nina Rossi"),
    (14, 99.0, "Oliver Grant"),
    (13, 95.5, "Priya Singh"),
    (12, 92.0, "Marcus Webb"),
    (11, 88.5, "Alice Chen"),
    (10, 85.0, "Nina Rossi"),
    (9, 81.5, "Oliver Grant"),
    (8, 78.0, "Priya Singh"),
    (7, 74.5, "Marcus Webb"),
    (6, 71.0, "Alice Chen"),
    (5, 67.5, "Nina Rossi"),
    (4, 64.0, "Oliver Grant"),
    (3, 60.5, "Priya Singh"),
    (2, 57.0, "Marcus Webb"),
    (1, 53.5, "Alice Chen"),
]

TASK_CONFIG: Dict[str, Any] = {
    "TASK_ID": TASK_ID,
    "broken_query": (
        "SELECT o.id, o.amount, (SELECT u.name FROM users u WHERE u.id = o.user_id) AS user_name\n"
        "FROM orders o\n"
        "ORDER BY o.created_at DESC"
    ),
    "expected_rows": EXPECTED_ROWS,
    "expected_row_count": 20,
    "hint": None,
    "progressive_hint": "The correlated subquery runs once per row. Try replacing it with a JOIN between orders and users.",
    "max_steps": 6,
    "check_plan": True,
    "order_matters": True,
    "schema_ddl": """
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    tier TEXT NOT NULL
);
CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    amount REAL NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
""".strip(),
}


def seed_database(conn: sqlite3.Connection) -> None:
    """Create users and orders and seed realistic e-commerce rows."""
    conn.executescript(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            tier TEXT NOT NULL
        );
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        """
    )
    users = [
        (1, "Alice Chen", "alice.chen@example.com", "gold"),
        (2, "Marcus Webb", "marcus.webb@example.com", "silver"),
        (3, "Priya Singh", "priya.singh@example.com", "gold"),
        (4, "Oliver Grant", "oliver.grant@example.com", "bronze"),
        (5, "Nina Rossi", "nina.rossi@example.com", "silver"),
    ]
    conn.executemany(
        "INSERT INTO users (id, name, email, tier) VALUES (?, ?, ?, ?)",
        users,
    )

    order_rows: List[Tuple[int, int, float, str]] = []
    for oid in range(1, 21):
        uid = ((oid - 1) % 5) + 1
        amount = 50.0 + oid * 3.5
        created_at = f"2024-06-{oid:02d} 12:00:00"
        order_rows.append((oid, uid, amount, created_at))
    conn.executemany(
        "INSERT INTO orders (id, user_id, amount, created_at) VALUES (?, ?, ?, ?)",
        order_rows,
    )
