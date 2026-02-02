"""
V2 AI DM service. Per-user isolated; accepts UserContext only.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from src_v2.core.user_context import UserContext
from src_v2.core.locks import acquire_lock, lock_key_dm
from src_v2.stores.dm_logs_v2 import append_dm_log, list_dm_logs
from src_v2.stores.ai_memory_v2 import get_memory, set_memory
from src_v2.stores.user_limits import get_limits


class AIDMServiceV2:
    """AI DM handler bound to user context. No globals."""

    def __init__(self) -> None:
        pass

    def process_incoming_dm(
        self,
        context: UserContext,
        sender_id: str,
        message_text: str,
        message_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        limits = get_limits(context.user_id)
        logs_today = list_dm_logs(context.user_id, context.instagram_id, limit=1000)
        today_prefix = __import__("datetime").datetime.utcnow().strftime("%Y-%m-%d")
        dms_today = len([e for e in logs_today if (e.get("timestamp") or "").startswith(today_prefix)])
        max_dms = context.rate_limits.get("dms_per_day", 50)
        if dms_today >= max_dms:
            return {"status": "rate_limited", "reply_text": None}
        memory = get_memory(context.user_id, context.instagram_id)
        with acquire_lock(lock_key_dm(context.user_id, context.instagram_id)):
            append_dm_log(context.user_id, context.instagram_id, {
                "sender_id": sender_id,
                "message": message_text[:500],
                "message_id": message_id,
                "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
            })
        reply = f"[V2 stub] Received: {message_text[:50]}..."
        return {"status": "ok", "reply_text": reply}
