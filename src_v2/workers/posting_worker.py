"""
V2 posting worker. Bound to user context; error isolated.
"""

from __future__ import annotations

from typing import Any, Dict

from src_v2.core.user_context import UserContext
from src_v2.services.posting_service_v2 import PostingServiceV2


def run_posting_worker(context: UserContext, job: Dict[str, Any]) -> Dict[str, Any]:
    """Run a single posting job for this context. One user failure does not affect others."""
    try:
        svc = PostingServiceV2()
        return svc.create_post(
            context,
            media_type=job.get("media_type", "image"),
            url=job.get("url", ""),
            caption=job.get("caption"),
            **{k: v for k, v in job.items() if k not in ("media_type", "url", "caption")},
        )
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
