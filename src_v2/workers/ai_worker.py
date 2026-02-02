"""
V2 AI worker. Bound to user context; error isolated.
"""

from __future__ import annotations

from typing import Any, Dict

from src_v2.core.user_context import UserContext
from src_v2.services.ai_dm_service_v2 import AIDMServiceV2


def run_ai_worker(
    context: UserContext,
    sender_id: str,
    message_text: str,
    message_id: str | None = None,
) -> Dict[str, Any]:
    """Run AI reply for this context only."""
    try:
        svc = AIDMServiceV2()
        return svc.process_incoming_dm(context, sender_id, message_text, message_id)
    except Exception as e:
        _mark_account_error(context, str(e))
        raise


def _mark_account_error(context: UserContext, error: str) -> None:
    try:
        from src_v2.meta.models import load_accounts, save_accounts
        accounts = load_accounts()
        for a in accounts:
            if a.id == context.account_id:
                a.status = "error"
                a.error_message = error
                break
        save_accounts(accounts)
    except Exception:
        pass
