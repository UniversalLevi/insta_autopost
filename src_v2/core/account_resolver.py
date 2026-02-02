"""
V2 account resolver: build UserContext from user_id + instagram_id.

Fetches from connected_accounts_v2, decrypts page token, loads limits/prefs.
"""

from __future__ import annotations

from typing import Optional

from src_v2.core.user_context import UserContext
from src_v2.meta.models import get_account_by_user_and_instagram


def _load_limits_for_user(user_id: str) -> dict:
    try:
        from src_v2.stores.user_limits import get_limits
        return get_limits(user_id)
    except Exception:
        return {}


def resolve_context(user_id: str, instagram_id: str) -> Optional[UserContext]:
    """
    Resolve UserContext for (user_id, instagram_id).

    Returns None if account not found, disconnected, or token decrypt fails.
    """
    account = get_account_by_user_and_instagram(user_id, instagram_id)
    if not account:
        return None
    try:
        from src_v2.meta.crypto import decrypt_token
        page_token = decrypt_token(account.page_token_encrypted)
    except Exception:
        return None
    limits = _load_limits_for_user(user_id)
    rate_limits = {
        "posts_per_day": limits.get("posts_per_day", 10),
        "dms_per_day": limits.get("dms_per_day", 50),
        "ai_tokens_per_day": limits.get("ai_tokens_per_day", 10000),
        "schedules_max": limits.get("schedules_max", 100),
    }
    return UserContext(
        user_id=user_id,
        instagram_id=account.instagram_id,
        page_id=account.page_id,
        page_token=page_token,
        account_id=account.id,
        ai_profile=None,
        rate_limits=rate_limits,
        preferences=limits.get("preferences", {}),
    )
