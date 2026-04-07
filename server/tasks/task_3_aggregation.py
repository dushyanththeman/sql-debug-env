"""
Task 3: fix silent double-counting from JOIN fan-out before GROUP BY.
"""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Tuple

TASK_ID = "aggregation-bug-001"

# Order matches ORDER BY total_spent DESC (broken query and correct fix).
EXPECTED_ROWS: List[Tuple[Any, ...]] = [
    ("Oliver Grant", 1, 150.0),
    ("Alice Chen", 2, 100.0),
    ("Marcus Webb", 2, 80.0),
    ("Priya Singh", 3, 75.0),
]

TASK_CONFIG: Dict[str, Any] = {
    "TASK_ID": TASK_ID,
    "broken_query": (
        "SELECT c.name, COUNT(o.id) AS order_count, SUM(i.price) AS total_spent\n"
        "FROM customers c\n"
        "JOIN orders o ON o.customer_id = c.id\n"
        "JOIN order_items i ON i.order_id = o.id\n"
        "WHERE o.status = 'completed'\n"
        "GROUP BY c.id, c.name\n"
        "ORDER BY total_spent DESC"
    ),
    "expected_rows": EXPECTED_ROWS,
    "expected_row_count": 4,
    "hint": None,
    "progressive_hint": "Joining order_items before GROUP BY multiplies rows. Use COUNT(DISTINCT o.id) instead of COUNT(o.id).",
    "max_steps": 8,
    "check_plan": False,
    "order_matters": True,
    "schema_ddl": """
CREATE TABLE customers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL
);
CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers(id)
);
CREATE TABLE order_items (
    id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL,
    product_name TEXT NOT NULL,
    price REAL NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(id)
);
""".strip(),
}


def seed_database(conn: sqlite3.Connection) -> None:
    """Create customers, orders, and order_items with a fan-out that breaks naive counts."""
    conn.executescript(
        """
        CREATE TABLE customers (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        );
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        );
        CREATE TABLE order_items (
            id INTEGER PRIMARY KEY,
            order_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            price REAL NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders(id)
        );
        """
    )
    customers = [
        (1, "Alice Chen"),
        (2, "Marcus Webb"),
        (3, "Priya Singh"),
        (4, "Oliver Grant"),
    ]
    conn.executemany(
        "INSERT INTO customers (id, name) VALUES (?, ?)",
        customers,
    )

    orders = [
        (1, 1, "completed"),
        (2, 1, "completed"),
        (3, 1, "pending"),
        (4, 2, "completed"),
        (5, 2, "completed"),
        (6, 3, "completed"),
        (7, 3, "completed"),
        (8, 3, "completed"),
        (9, 4, "completed"),
        (10, 4, "cancelled"),
    ]
    conn.executemany(
        "INSERT INTO orders (id, customer_id, status) VALUES (?, ?, ?)",
        orders,
    )

    # Twenty-five line items across completed orders only (orders 1,2,4,5,6,7,8,9).
    prices_o1 = [10.0, 5.0, 5.0, 5.0, 5.0, 3.0]
    prices_o2 = [20.0, 20.0, 15.0, 12.0]
    prices_o4 = [25.0, 25.0, 10.0]
    prices_o5 = [15.0, 5.0]
    prices_o6 = [10.0, 10.0, 10.0]
    prices_o7 = [20.0, 5.0]
    prices_o8 = [8.0, 7.0, 5.0]
    prices_o9 = [100.0, 50.0]

    item_rows: List[Tuple[int, int, str, float]] = []
    nid = 1
    for p in prices_o1:
        item_rows.append((nid, 1, f"Desk lamp SKU-{nid}", p))
        nid += 1
    for p in prices_o2:
        item_rows.append((nid, 2, f"Monitor SKU-{nid}", p))
        nid += 1
    for p in prices_o4:
        item_rows.append((nid, 4, f"Keyboard SKU-{nid}", p))
        nid += 1
    for p in prices_o5:
        item_rows.append((nid, 5, f"Webcam SKU-{nid}", p))
        nid += 1
    for p in prices_o6:
        item_rows.append((nid, 6, f"Dock SKU-{nid}", p))
        nid += 1
    for p in prices_o7:
        item_rows.append((nid, 7, f"Headset SKU-{nid}", p))
        nid += 1
    for p in prices_o8:
        item_rows.append((nid, 8, f"Mouse SKU-{nid}", p))
        nid += 1
    for p in prices_o9:
        item_rows.append((nid, 9, f"Chair SKU-{nid}", p))
        nid += 1

    conn.executemany(
        "INSERT INTO order_items (id, order_id, product_name, price) VALUES (?, ?, ?, ?)",
        item_rows,
    )
