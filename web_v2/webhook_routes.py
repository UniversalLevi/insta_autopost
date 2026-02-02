"""
V2 webhook router. Routes by instagram_business_id → user_id only.
Never broadcast; each event dispatched to single owner.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from src_v2.services.webhook_service_v2 import route_webhook_event


router = APIRouter(prefix="/v2/webhooks", tags=["v2-webhooks"])


def _extract_instagram_id_from_payload(payload: Dict[str, Any]) -> str | None:
    """Extract Instagram business account ID from Meta webhook payload."""
    for entry in payload.get("entry", []) or []:
        if not isinstance(entry, dict):
            continue
        # Page-level: entry has id = page_id; instagram may be in field
        for change in entry.get("changes", []) or []:
            val = change.get("value") if isinstance(change, dict) else {}
            if isinstance(val, dict) and "instagram_business_account" in val:
                ig = val["instagram_business_account"]
                if isinstance(ig, dict) and ig.get("id"):
                    return ig["id"]
        # Messaging: sender.id is PSID; we need to resolve from page/entry
        # In messaging webhooks, entry.id is page_id; we look up instagram_id from our DB
        page_id = entry.get("id")
        if page_id:
            from src_v2.meta.models import load_accounts
            for a in load_accounts():
                if a.page_id == page_id and a.status == "connected":
                    return a.instagram_id
    return None


@router.post("/instagram")
async def instagram_webhook(request: Request) -> JSONResponse:
    """
    Meta Instagram webhook. Route by instagram_business_id → single user.
    Never broadcast.
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "invalid_json"})
    instagram_id = _extract_instagram_id_from_payload(body)
    if not instagram_id:
        return JSONResponse(status_code=200, content={"status": "ignored", "reason": "no_instagram_id"})
    result = route_webhook_event(instagram_id, body)
    return JSONResponse(status_code=200, content=result)
