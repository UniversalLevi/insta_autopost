"""
V2 warming service. Per-user isolated; accepts UserContext only.
"""

from __future__ import annotations

from typing import Any, Dict, List

from src_v2.core.user_context import UserContext
from src_v2.stores.warming_stats_v2 import get_stats, set_stats


class WarmingServiceV2:
    """Warming service bound to user context. No globals."""

    def __init__(self) -> None:
        pass

    def run_warming(self, context: UserContext) -> Dict[str, Any]:
        stats = get_stats(context.user_id, context.instagram_id)
        actions_done = stats.get("actions_today", 0)
        set_stats(context.user_id, context.instagram_id, {
            "actions_today": actions_done + 1,
            "last_run": __import__("datetime").datetime.utcnow().isoformat(),
        })
        return {"status": "ok", "actions_today": actions_done + 1}

    def get_stats_for_context(self, context: UserContext) -> Dict[str, Any]:
        return get_stats(context.user_id, context.instagram_id)
