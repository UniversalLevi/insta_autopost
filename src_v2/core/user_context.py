"""
V2 per-user execution context.

All V2 automation services and workers receive a UserContext.
No shared globals; every operation is scoped to (user_id, instagram_id).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass(frozen=False)
class UserContext:
    """
    Isolated context for a single user + Instagram Business account.

    All V2 services accept (context: UserContext).
    """
    user_id: str
    instagram_id: str
    page_id: str
    page_token: str  # decrypted; never persisted in logs
    account_id: str  # ConnectedAccountV2.id

    # Optional profile/settings (loaded from isolated stores)
    ai_profile: Optional[Dict[str, Any]] = None
    rate_limits: Dict[str, int] = field(default_factory=lambda: {
        "posts_per_day": 10,
        "dms_per_day": 50,
        "ai_tokens_per_day": 10000,
        "schedules_max": 100,
    })
    preferences: Dict[str, Any] = field(default_factory=dict)

    def scoped_key(self, prefix: str) -> str:
        """Lock/key prefix for this context."""
        return f"{prefix}:user:{self.user_id}:ig:{self.instagram_id}"
