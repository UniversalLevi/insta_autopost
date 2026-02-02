"""
V2 Meta OAuth service.

Implements the connect/callback/disconnect workflow for Instagram Business accounts.

Meta App Config (env/.env):
- META_APP_ID (required)
- META_APP_SECRET (required)
- META_REDIRECT_URI (optional; if set, used and validated)
- META_WEBHOOK_VERIFY_TOKEN (optional; reserved for webhook verification later)

Security (env/.env):
- V2_META_ENC_KEY (required): Fernet key for encrypting tokens at rest
- V2_META_STATE_SECRET (required): HMAC secret for OAuth state signing

Notes:
- Uses Graph API v19.0 as requested.
- Stores ONLY encrypted tokens (never plaintext).
- Multi-account: supports multiple IG accounts per V2 user (no overwrite).
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode

import requests

from .config import load_meta_config
from .crypto import encrypt_token
from .models import (
    ConnectedAccountV2,
    log_meta_oauth_event,
    upsert_account,
)


GRAPH_VERSION = "v19.0"
FB_OAUTH_BASE = f"https://www.facebook.com/{GRAPH_VERSION}/dialog/oauth"
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"

SCOPES = [
    "pages_show_list",
    "pages_read_engagement",
    "pages_manage_metadata",
    "pages_messaging",
    "instagram_basic",
    "instagram_manage_messages",
    "instagram_content_publish",
]


class MetaOAuthError(RuntimeError):
    def __init__(self, message: str, code: str = "meta_oauth_error"):
        super().__init__(message)
        self.code = code


def _is_https_required() -> bool:
    return (os.getenv("ENVIRONMENT") or "").strip().lower() == "production"


def _validate_redirect_uri(redirect_uri: str) -> None:
    if _is_https_required() and not redirect_uri.lower().startswith("https://"):
        raise MetaOAuthError("HTTPS is required for OAuth redirect URI in production.")


def build_connect_url(redirect_uri: str, state: str) -> str:
    cfg = load_meta_config()
    _validate_redirect_uri(redirect_uri)

    params = {
        "client_id": cfg.app_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": ",".join(SCOPES),
        "state": state,
    }
    return f"{FB_OAUTH_BASE}?{urlencode(params)}"


def exchange_code_for_user_token(code: str, redirect_uri: str) -> str:
    cfg = load_meta_config()
    _validate_redirect_uri(redirect_uri)

    r = requests.get(
        f"{GRAPH_BASE}/oauth/access_token",
        params={
            "client_id": cfg.app_id,
            "redirect_uri": redirect_uri,
            "client_secret": cfg.app_secret,
            "code": code,
        },
        timeout=30,
    )
    data = r.json()
    if "error" in data:
        raise MetaOAuthError(_format_graph_error(data["error"]))
    token = data.get("access_token")
    if not token:
        raise MetaOAuthError("Meta did not return an access_token.")
    return token


def exchange_for_long_lived_token(short_lived_token: str) -> Tuple[str, Optional[datetime]]:
    cfg = load_meta_config()
    r = requests.get(
        f"{GRAPH_BASE}/oauth/access_token",
        params={
            "grant_type": "fb_exchange_token",
            "client_id": cfg.app_id,
            "client_secret": cfg.app_secret,
            "fb_exchange_token": short_lived_token,
        },
        timeout=30,
    )
    data = r.json()
    if "error" in data:
        raise MetaOAuthError(_format_graph_error(data["error"]))
    token = data.get("access_token")
    if not token:
        raise MetaOAuthError("Meta did not return a long-lived access_token.")
    expires_in = data.get("expires_in")
    expires_at = None
    try:
        if expires_in:
            expires_at = datetime.utcnow() + timedelta(seconds=int(expires_in))
    except Exception:
        expires_at = None
    return token, expires_at


def get_pages(user_token: str) -> List[Dict[str, Any]]:
    r = requests.get(
        f"{GRAPH_BASE}/me/accounts",
        params={
            "access_token": user_token,
            "fields": "id,name,access_token,instagram_business_account",
        },
        timeout=30,
    )
    data = r.json()
    if "error" in data:
        raise MetaOAuthError(_format_graph_error(data["error"]))
    return data.get("data", []) or []


def get_page_instagram_business_id(page_id: str, user_token: str) -> Tuple[str, str]:
    """
    Return (instagram_business_account_id, page_access_token).

    Uses user_token to fetch page details and a page token.
    """
    # First: read page access_token + instagram_business_account from /me/accounts list
    pages = get_pages(user_token)
    page = next((p for p in pages if p.get("id") == page_id), None)
    if not page:
        raise MetaOAuthError("Selected Page not found in your accessible Pages list.")
    page_token = page.get("access_token")
    if not page_token:
        raise MetaOAuthError("Meta did not return a Page access token. Check permissions.")

    ig = page.get("instagram_business_account")
    if ig and isinstance(ig, dict) and ig.get("id"):
        return ig["id"], page_token

    # Fallback: query the page directly for instagram_business_account
    r = requests.get(
        f"{GRAPH_BASE}/{page_id}",
        params={
            "fields": "instagram_business_account",
            "access_token": user_token,
        },
        timeout=30,
    )
    data = r.json()
    if "error" in data:
        raise MetaOAuthError(_format_graph_error(data["error"]))
    ig2 = data.get("instagram_business_account")
    if not ig2 or not ig2.get("id"):
        raise MetaOAuthError(
            "This Page is not linked to an Instagram Business account. "
            "Connect IG to the Page in Meta Business Suite, then retry."
        )
    return ig2["id"], page_token


def subscribe_page_webhooks(page_id: str, page_token: str) -> None:
    """
    Subscribe the app to Page webhooks.

    Subscribes to: messages, messaging_postbacks, message_reactions, feed
    """
    r = requests.post(
        f"{GRAPH_BASE}/{page_id}/subscribed_apps",
        data={
            "subscribed_fields": "messages,messaging_postbacks,message_reactions,feed",
            "access_token": page_token,
        },
        timeout=30,
    )
    data = r.json()
    if "error" in data:
        raise MetaOAuthError(_format_graph_error(data["error"]))
    # data typically: {"success": true}


def connect_user_account(
    *,
    user_id: str,
    code: str,
    redirect_uri: str,
    page_id: str,
) -> ConnectedAccountV2:
    """
    Full callback flow:
    - exchange code -> short token
    - exchange short -> long-lived user token
    - get IG business id and page token
    - subscribe page webhooks
    - store encrypted page token for this user's connected account
    """
    log_meta_oauth_event(user_id=user_id, action="callback_start", result="ok", extra={"page_id": page_id})

    short_token = exchange_code_for_user_token(code, redirect_uri)
    long_token, user_expires_at = exchange_for_long_lived_token(short_token)

    instagram_id, page_token = get_page_instagram_business_id(page_id, long_token)

    # Subscribe webhooks (best-effort; if it fails, we still store account but mark error)
    try:
        subscribe_page_webhooks(page_id, page_token)
        sub_ok = True
        sub_err = None
    except MetaOAuthError as e:
        sub_ok = False
        sub_err = str(e)

    encrypted_page_token = encrypt_token(page_token)
    status = "connected" if sub_ok else "error"
    error_message = None if sub_ok else f"Connected, but webhook subscription failed: {sub_err}"

    account = upsert_account(
        user_id=user_id,
        page_id=page_id,
        instagram_id=instagram_id,
        page_token_encrypted=encrypted_page_token,
        expires_at=user_expires_at,
        status=status,  # type: ignore[arg-type]
        error_message=error_message,
    )

    log_meta_oauth_event(
        user_id=user_id,
        action="callback_complete",
        result="ok" if sub_ok else "partial",
        error=error_message,
        extra={"page_id": page_id, "instagram_id": instagram_id},
    )
    return account


def disconnect_account(*, user_id: str, account_id: str) -> None:
    """
    Disconnect a connected account (best-effort).

    We mark it disconnected in storage. Permission revocation requires a user token
    which we do not persist (by design). Webhook unsubscription can be added later
    when we persist a revocation-capable token or implement user re-auth for revoke.
    """
    from .models import mark_disconnected

    mark_disconnected(account_id=account_id)
    log_meta_oauth_event(user_id=user_id, action="disconnect", result="ok", extra={"account_id": account_id})


def _format_graph_error(err: Any) -> str:
    """
    Convert Graph API error objects into human-readable messages and include hints
    for common failure modes (dev mode / missing permissions / review pending).
    """
    if not isinstance(err, dict):
        return str(err)
    message = err.get("message") or "Meta Graph API error"
    error_type = err.get("type")
    code = err.get("code")
    subcode = err.get("error_subcode")

    # Helpful hints for common cases
    hint = ""
    msg_lower = str(message).lower()
    if "permissions" in msg_lower or "permission" in msg_lower:
        hint = "Ensure all requested permissions are granted and approved for your app."
    if "not authorized" in msg_lower or "not authorized" in str(error_type).lower():
        hint = "Your app may be in Development mode or missing App Review approvals; add yourself as tester/admin."
    if code in (190,):
        hint = "Token expired or invalid. Reconnect to refresh tokens."
    if code in (10, 200, 100):
        hint = hint or "Check scopes, app mode, and the selected Page's linked Instagram Business account."

    parts = [message]
    meta_bits = []
    if code is not None:
        meta_bits.append(f"code={code}")
    if subcode is not None:
        meta_bits.append(f"subcode={subcode}")
    if meta_bits:
        parts.append(f"({', '.join(meta_bits)})")
    if hint:
        parts.append(f"Hint: {hint}")
    return " ".join(parts)

