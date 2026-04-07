"""
Registered SQL debug tasks.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .task_1_syntax import TASK_CONFIG as TASK_1
from .task_2_join import TASK_CONFIG as TASK_2
from .task_3_aggregation import TASK_CONFIG as TASK_3
from .task_4_window import TASK_CONFIG as TASK_4
from .task_5_null import TASK_CONFIG as TASK_5
from .task_6_join import TASK_CONFIG as TASK_6

TASK_ORDER: List[Dict[str, Any]] = [TASK_1, TASK_2, TASK_3, TASK_4, TASK_5, TASK_6]

TASK_REGISTRY: Dict[str, Dict[str, Any]] = {
    cfg["TASK_ID"]: cfg for cfg in TASK_ORDER
}

__all__ = ["TASK_ORDER", "TASK_REGISTRY"]
