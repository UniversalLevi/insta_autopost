"""
V2 comment-to-DM service. Per-user isolated; accepts UserContext only.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from src_v2.core.user_context import UserContext
from src_v2.stores.dm_logs_v2 import append_dm_log


class CommentDMServiceV2:
    """Comment-to-DM logic bound to user context. No globals."""

    def __init__(self) -> None:
        pass

    def process_comment_for_dm(
        self,
        context: UserContext,
        comment_id: str,
        comment_text: str,
        commenter_id: str,
        media_id: str,
    ) -> Dict[str, Any]:
        append_dm_log(context.user_id, context.instagram_id, {
            "type": "comment_dm",
            "comment_id": comment_id,
            "comment_text": comment_text[:200],
            "commenter_id": commenter_id,
            "media_id": media_id,
            "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
        })
        return {"status": "logged"}
