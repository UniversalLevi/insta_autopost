"""
V2 engine API. All routes require UserContext (X-USER-ID + X-INSTAGRAM-ID).
Backend validates ownership; no shared state.
"""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends

from web_v2.auth_middleware import require_context
from src_v2.core.user_context import UserContext
from src_v2.services.posting_service_v2 import PostingServiceV2
from src_v2.services.scheduler_service_v2 import SchedulerServiceV2
from src_v2.stores.user_limits import get_limits


router = APIRouter(prefix="/v2/engine", tags=["v2-engine"])


@router.get("/posts")
async def list_posts(ctx: UserContext = Depends(require_context)) -> List[Dict[str, Any]]:
    """List posts for this user+instagram context. Requires X-USER-ID and X-INSTAGRAM-ID."""
    svc = PostingServiceV2()
    return svc.list_posts_for_context(ctx)


@router.get("/schedules")
async def list_schedules(ctx: UserContext = Depends(require_context)) -> List[Dict[str, Any]]:
    """List schedules for this context. Requires X-USER-ID and X-INSTAGRAM-ID."""
    svc = SchedulerServiceV2()
    return svc.list_schedules_for_context(ctx)


@router.get("/limits")
async def get_limits_route(ctx: UserContext = Depends(require_context)) -> Dict[str, Any]:
    """Get rate limits for this user. Requires X-USER-ID and X-INSTAGRAM-ID."""
    return {
        "user_id": ctx.user_id,
        "instagram_id": ctx.instagram_id,
        "rate_limits": ctx.rate_limits,
        "preferences": ctx.preferences,
    }
