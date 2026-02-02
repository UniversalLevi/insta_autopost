"""
V2 webhook service. Routes by instagram_business_id → user_id only.
Never broadcast; each event goes to one user context.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from src_v2.meta.models import get_account_by_instagram_id
from src_v2.core.account_resolver import resolve_context
from src_v2.services.ai_dm_service_v2 import AIDMServiceV2
from src_v2.services.comment_dm_service_v2 import CommentDMServiceV2


def route_webhook_event(instagram_business_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Route incoming webhook to the single owner of this Instagram account.
    Returns result for that user only; never broadcast.
    """
    account = get_account_by_instagram_id(instagram_business_id)
    if not account:
        return {"status": "ignored", "reason": "no_connected_account"}
    context = resolve_context(account.user_id, account.instagram_id)
    if not context:
        return {"status": "ignored", "reason": "context_unavailable"}
    try:
        return _dispatch_event(context, payload)
    except Exception as e:
        return {"status": "error", "error": str(e)}


def _dispatch_event(context: Any, payload: Dict[str, Any]) -> Dict[str, Any]:
    object_type = (payload.get("object") or "").lower()
    entries = payload.get("entry", []) or []
    for entry in entries:
        messaging = (entry.get("messaging") or []) if isinstance(entry, dict) else []
        for ev in messaging:
            if ev.get("message"):
                svc = AIDMServiceV2()
                return svc.process_incoming_dm(
                    context,
                    sender_id=str(ev.get("sender", {}).get("id", "")),
                    message_text=(ev.get("message", {}).get("text") or ""),
                    message_id=ev.get("message", {}).get("mid"),
                )
            if ev.get("postback"):
                pass  # log only
        changes = (entry.get("changes") or []) if isinstance(entry, dict) else []
        for ch in changes:
            if ch.get("field") == "feed" and ch.get("value"):
                pass  # feed event; can hand to comment_dm or post
    return {"status": "processed"}
