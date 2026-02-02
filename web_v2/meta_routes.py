"""
V2 Meta OAuth routes.

Endpoints:
- GET  /v2/meta/connect
- GET  /v2/meta/callback
- POST /v2/meta/disconnect

Optional helper endpoints (for UI):
- GET /v2/meta/accounts

This router is V2-only and requires V2 auth (cookie/header session).
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse

from src_v2.auth.models import UserV2
from web_v2.auth_middleware import require_login

from src_v2.meta import service as meta_service
from src_v2.meta.config import load_meta_config
from src_v2.meta.models import list_accounts_for_user, log_meta_oauth_event
from src_v2.meta.state import create_state, validate_state


router = APIRouter(prefix="/v2/meta", tags=["v2-meta"])


def _effective_redirect_uri(request: Request) -> str:
    """
    Determine the redirect URI used for the Meta OAuth flow.

    - If META_REDIRECT_URI env is set, use it (and validate HTTPS in prod).
    - Else, derive from current request host: /v2/meta/callback
    """
    cfg = load_meta_config()
    if cfg.redirect_uri:
        return cfg.redirect_uri
    # Derive from request
    url = str(request.url_for("v2_meta_callback"))
    return url


def _ensure_https_in_prod(redirect_uri: str) -> None:
    if (os.getenv("ENVIRONMENT") or "").strip().lower() == "production":
        if not redirect_uri.lower().startswith("https://"):
            raise HTTPException(
                status_code=500,
                detail="Production requires HTTPS redirect URI (set META_REDIRECT_URI=https://...).",
            )


@router.get("/connect")
async def connect(
    request: Request,
    page_id: str,
    next: Optional[str] = None,
    current_user: UserV2 = Depends(require_login),
):
    """
    Start Meta OAuth connect flow.

    Requires:
    - page_id query param (selected Page ID)
    - authenticated V2 user
    """
    try:
        redirect_uri = _effective_redirect_uri(request)
        _ensure_https_in_prod(redirect_uri)
        state = create_state(user_id=current_user.id, redirect_next=next)
        url = meta_service.build_connect_url(redirect_uri=redirect_uri, state=state)
        # Persist the chosen page_id alongside state via query param to callback
        # (Meta returns state as-is; we keep page_id in callback query too.)
        return RedirectResponse(url=f"{url}&page_id={page_id}", status_code=302)
    except Exception as e:
        log_meta_oauth_event(current_user.id, "connect", "error", error=str(e))
        raise


@router.get("/callback", name="v2_meta_callback")
async def callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    page_id: Optional[str] = None,
):
    """
    Meta OAuth callback.

    Steps:
    - validate CSRF state (HMAC + expiry)
    - exchange code -> short token -> long-lived user token
    - fetch page token + instagram_business_account.id
    - subscribe webhooks (best-effort)
    - store encrypted page token as ConnectedAccountV2 for this user
    """
    if not code:
        raise HTTPException(status_code=400, detail="Missing ?code from Meta callback.")
    if not state:
        raise HTTPException(status_code=400, detail="Missing ?state from Meta callback.")
    if not page_id:
        raise HTTPException(status_code=400, detail="Missing ?page_id (selected Facebook Page).")

    state_data = validate_state(state)
    user_id = str(state_data.get("user_id"))
    redirect_next = (state_data.get("next") or "").strip() or "/v2/connect-meta"

    redirect_uri = _effective_redirect_uri(request)
    _ensure_https_in_prod(redirect_uri)

    try:
        acct = meta_service.connect_user_account(
            user_id=user_id,
            code=code,
            redirect_uri=redirect_uri,
            page_id=page_id,
        )
        # Redirect to UI page; UI will call /v2/meta/accounts to show status
        return RedirectResponse(url=redirect_next, status_code=302)
    except meta_service.MetaOAuthError as e:
        log_meta_oauth_event(user_id, "callback", "error", error=str(e), extra={"page_id": page_id})
        return HTMLResponse(
            status_code=400,
            content=f"<html><body><h2>Meta Connect Failed</h2><p>{str(e)}</p></body></html>",
        )
    except Exception as e:
        log_meta_oauth_event(user_id, "callback", "error", error=str(e), extra={"page_id": page_id})
        raise HTTPException(status_code=500, detail="Meta connect failed. Check logs.")


@router.post("/disconnect")
async def disconnect(
    account_id: str = Form(...),
    current_user: UserV2 = Depends(require_login),
) -> Dict[str, str]:
    """
    Disconnect a connected Meta/IG account from the current user.

    Marks it disconnected in V2 storage (best-effort revoke/unsubscribe is future work).
    """
    meta_service.disconnect_account(user_id=current_user.id, account_id=account_id)
    return {"status": "success"}


@router.get("/accounts")
async def accounts(current_user: UserV2 = Depends(require_login)) -> List[Dict[str, Any]]:
    """
    List connected accounts for the current user.
    """
    items = list_accounts_for_user(current_user.id)
    out: List[Dict[str, Any]] = []
    for a in items:
        expires_at = a.expires_at.isoformat() if a.expires_at else None
        out.append(
            {
                "id": a.id,
                "page_id": a.page_id,
                "instagram_id": a.instagram_id,
                "expires_at": expires_at,
                "status": a.status,
                "created_at": a.created_at.isoformat(),
                "error_message": a.error_message,
            }
        )
    return out

