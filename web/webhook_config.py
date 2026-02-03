"""Webhook configuration for Meta app setup."""

import os


def get_webhook_config() -> dict:
    """
    Get webhook config for Meta app setup.
    Returns production_url, callback_url, and verify_token.
    """
    base_url = (os.getenv("BASE_URL") or os.getenv("APP_URL") or "").strip().rstrip("/")
    prod_url = f"{base_url}/webhooks/instagram" if base_url else "https://veilforce.com/webhooks/instagram"
    verify_token = os.environ.get("WEBHOOK_VERIFY_TOKEN", "my_test_token_for_instagram_verification")
    return {
        "production_url": prod_url,
        "callback_url": prod_url,
        "verify_token": verify_token,
    }
