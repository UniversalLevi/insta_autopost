"""
V2 Meta app configuration.

All values are loaded from environment variables (typically via .env):

- META_APP_ID
- META_APP_SECRET
- META_REDIRECT_URI  (optional; falls back to request URL)
- META_WEBHOOK_VERIFY_TOKEN
- V2_META_ENC_KEY    (Fernet key for token encryption; base64 urlsafe 32 bytes)
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class MetaConfigV2:
    app_id: str
    app_secret: str
    redirect_uri: str | None
    webhook_verify_token: str | None
    enc_key: str


def load_meta_config() -> MetaConfigV2:
    app_id = os.getenv("META_APP_ID") or ""
    app_secret = os.getenv("META_APP_SECRET") or ""
    redirect_uri = os.getenv("META_REDIRECT_URI") or None
    webhook_verify_token = os.getenv("META_WEBHOOK_VERIFY_TOKEN") or None
    enc_key = os.getenv("V2_META_ENC_KEY") or ""

    if not app_id or not app_secret:
        raise RuntimeError(
            "META_APP_ID and META_APP_SECRET must be set in environment for V2 Meta OAuth."
        )
    if not enc_key:
        raise RuntimeError(
            "V2_META_ENC_KEY must be set to a Fernet key for secure token encryption."
        )
    return MetaConfigV2(
        app_id=app_id,
        app_secret=app_secret,
        redirect_uri=redirect_uri,
        webhook_verify_token=webhook_verify_token,
        enc_key=enc_key,
    )

