"""
V2 admin dashboard. Health and isolation metrics.
"""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status

from src_v2.auth.models import UserV2
from web_v2.auth_middleware import require_login


router = APIRouter(prefix="/v2/admin", tags=["v2-admin"])


def _require_admin(user: UserV2) -> None:
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin only",
        )


@router.get("/health")
async def admin_health(current_user: UserV2 = Depends(require_login)) -> Dict[str, Any]:
    """
    Dashboard: active users, running workers (contexts), failures, queue depth.
    Admin only.
    """
    _require_admin(current_user)
    from pathlib import Path
    import os
    from src_v2.meta.models import load_accounts
    from src_v2.stores import schedules_v2 as sched_store
    from src_v2.stores import posts_v2 as posts_store
    data_dir = Path(os.getenv("V2_DATA_DIR", "data"))
    logs_file = data_dir / "meta_oauth_logs_v2.jsonl"
    accounts = load_accounts()
    connected = [a for a in accounts if a.status == "connected"]
    active_user_ids = list({a.user_id for a in connected})
    schedules_data = getattr(sched_store, "_load_all", lambda: {})()
    posts_data = getattr(posts_store, "_load_all", lambda: {})()
    queue_depth = sum(len(v) for v in schedules_data.values()) if isinstance(schedules_data, dict) else 0
    posts_count = sum(len(v) for v in posts_data.values()) if isinstance(posts_data, dict) else 0
    failure_count = 0
    if logs_file.exists():
        try:
            lines = logs_file.read_text(encoding="utf-8").strip().split("\n")
            failure_count = sum(1 for ln in lines[-500:] if ln and '"result":"error"' in ln)
        except Exception:
            pass
    return {
        "active_users": len(active_user_ids),
        "active_user_ids": active_user_ids[:50],
        "connected_accounts": len(connected),
        "running_workers": "per-context (no global pool)",
        "queue_depth": queue_depth,
        "posts_stored": posts_count,
        "recent_failures": failure_count,
    }
