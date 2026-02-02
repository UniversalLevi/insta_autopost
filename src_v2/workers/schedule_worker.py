"""
V2 schedule worker. Bound to user context; error isolated.
"""

from __future__ import annotations

from typing import Any, Dict

from src_v2.core.user_context import UserContext
from src_v2.services.scheduler_service_v2 import SchedulerServiceV2


def run_schedule_worker(context: UserContext, job: Dict[str, Any]) -> Dict[str, Any]:
    """Run a scheduled job for this context only."""
    try:
        svc = SchedulerServiceV2()
        return svc.schedule(
            context,
            scheduled_time=job.get("scheduled_time", ""),
            payload=job.get("payload", {}),
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
