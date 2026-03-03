from typing import Any, Dict, Optional

import os
import requests

from src.utils.logger import get_logger

logger = get_logger(__name__)


class EazyDSClient:
    """
    Small HTTP client for calling the EazyDS internal API from InstaForge.
    """

    def __init__(self) -> None:
        base_url = os.getenv("EAZYDS_API_URL") or os.getenv("EAZYDS_BASE_URL")
        if not base_url:
            logger.warning(
                "EazyDSClient initialized without EAZYDS_API_URL/EAZYDS_BASE_URL; "
                "DM onboarding calls will fail until configured."
            )
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = os.getenv("INSTAFORGE_SECRET")

    def _endpoint(self, path: str) -> str:
        if not self.base_url:
            raise RuntimeError("EAZYDS_API_URL/EAZYDS_BASE_URL is not configured")
        return f"{self.base_url}{path}"

    def create_user_and_store_for_dm(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call EazyDS internal endpoint to create/reuse a user + store.

        Expected request body (subset, validated server-side):
          - email?: str
          - mobile?: str
          - name?: str
          - storeName: str
          - currency?: 'INR' | 'USD' | 'EUR' | 'GBP'
          - instagramUserId: str
          - instagramUsername?: str
        """
        try:
            url = self._endpoint("/api/internal/instagram/create-user-and-store")
        except RuntimeError as e:
            logger.error("EazyDS internal API not configured", error=str(e))
            return {
                "success": False,
                "errorCode": "CONFIG_MISSING",
                "message": "EAZYDS_API_URL/EAZYDS_BASE_URL is not configured on the InstaForge side.",
            }

        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["x-api-key"] = self.api_key
        else:
            logger.error(
                "INSTAFORGE_SECRET is not configured; EazyDS internal API will reject requests"
            )

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=20)
        except requests.RequestException as exc:
            logger.error(
                "Failed to call EazyDS internal API",
                url=url,
                error=str(exc),
            )
            return {
                "success": False,
                "errorCode": "NETWORK_ERROR",
                "message": f"Failed to reach EazyDS backend: {exc}",
            }

        try:
            data: Dict[str, Any] = resp.json()
        except Exception:
            logger.error(
                "EazyDS internal API responded with non-JSON body",
                url=url,
                status_code=resp.status_code,
                text_preview=resp.text[:500],
            )
            return {
                "success": False,
                "errorCode": "INVALID_RESPONSE",
                "message": "EazyDS backend returned a non-JSON response.",
            }

        if resp.status_code >= 400 or not data.get("success"):
            logger.warning(
                "EazyDS internal API returned error",
                url=url,
                status_code=resp.status_code,
                response=data,
            )
            return {
                "success": False,
                "errorCode": data.get("errorCode") or f"HTTP_{resp.status_code}",
                "message": data.get("message") or "EazyDS internal API reported an error.",
                "raw": data,
            }

        return data


def get_eazyds_client() -> EazyDSClient:
    """
    Convenience accessor so other modules don't have to manage instances.
    """
    return EazyDSClient()

