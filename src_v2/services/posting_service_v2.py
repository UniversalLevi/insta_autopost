"""
V2 posting service. Per-user isolated; accepts UserContext only.
Clone of posting logic for V2; no shared state.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src_v2.core.user_context import UserContext
from src_v2.core.locks import acquire_lock, lock_key_posting
from src_v2.stores.posts_v2 import append_post, list_posts
from src_v2.stores.user_limits import get_limits


class PostingServiceV2:
    """Posting service bound to a user context. No globals."""

    def __init__(self) -> None:
        pass

    def create_post(
        self,
        context: UserContext,
        media_type: str,
        url: str,
        caption: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Create a post record in isolated store (no v1 API call in this stub)."""
        limits = get_limits(context.user_id)
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        posts_today = len([
            p for p in list_posts(context.user_id, context.instagram_id)
            if (p.get("created_at") or "").startswith(today)
        ])
        max_posts = context.rate_limits.get("posts_per_day", 10)
        if posts_today >= max_posts:
            raise RuntimeError(f"Daily post limit reached ({max_posts}/day).")
        post_id = __import__("uuid").uuid4().hex
        entry = {
            "id": post_id,
            "media_type": media_type,
            "url": url,
            "caption": caption or "",
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
            **kwargs,
        }
        with acquire_lock(lock_key_posting(context.user_id, context.instagram_id)):
            append_post(context.user_id, context.instagram_id, entry)
        return entry

    def list_posts_for_context(self, context: UserContext) -> List[Dict[str, Any]]:
        return list_posts(context.user_id, context.instagram_id)
