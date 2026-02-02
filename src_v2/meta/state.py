"""
V2 OAuth state/CSRF protection.

We sign the state payload using itsdangerous (HMAC) so:
- State can't be forged/tampered
- State can expire (max_age)

Env vars:
- V2_META_STATE_SECRET (required): secret for signing state tokens
"""

from __future__ import annotations

import os
import secrets
from typing import Any, Dict

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer


def _serializer() -> URLSafeTimedSerializer:
    secret = os.getenv("V2_META_STATE_SECRET") or ""
    if not secret:
        raise RuntimeError("V2_META_STATE_SECRET must be set for Meta OAuth CSRF protection.")
    return URLSafeTimedSerializer(secret_key=secret, salt="instaforge-v2-meta-oauth")


def create_state(user_id: str, redirect_next: str | None = None) -> str:
    payload: Dict[str, Any] = {
        "user_id": user_id,
        "nonce": secrets.token_urlsafe(16),
        "next": redirect_next or "",
    }
    return _serializer().dumps(payload)


def validate_state(state: str, max_age_seconds: int = 15 * 60) -> Dict[str, Any]:
    try:
        data = _serializer().loads(state, max_age=max_age_seconds)
    except SignatureExpired:
        raise ValueError("OAuth state expired. Please try connecting again.")
    except BadSignature:
        raise ValueError("Invalid OAuth state. Please try connecting again.")
    if not isinstance(data, dict) or "user_id" not in data:
        raise ValueError("Invalid OAuth state payload.")
    return data

