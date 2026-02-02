"""
V2 scheduler service. Per-user isolated; accepts UserContext only.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src_v2.core.user_context import UserContext
from src_v2.stores.schedules_v2 import append_schedule, list_schedules
from src_v2.stores.user_limits import get_limits


class SchedulerServiceV2:
    """Scheduler bound to user context. No globals."""

    def __init__(self) -> None:
        pass

    def schedule(
        self,
        context: UserContext,
        scheduled_time: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        limits = get_limits(context.user_id)
        schedules = list_schedules(context.user_id, context.instagram_id)
        max_schedules = context.rate_limits.get("schedules_max", 100)
        if len(schedules) >= max_schedules:
            raise RuntimeError(f"Schedule limit reached ({max_schedules}).")
        entry = {
            "id": __import__("uuid").uuid4().hex,
            "scheduled_time": scheduled_time,
            "payload": payload,
            "status": "scheduled",
            "created_at": __import__("datetime").datetime.utcnow().isoformat(),
        }
        append_schedule(context.user_id, context.instagram_id, entry)
        return entry

    def list_schedules_for_context(self, context: UserContext) -> List[Dict[str, Any]]:
        return list_schedules(context.user_id, context.instagram_id)
