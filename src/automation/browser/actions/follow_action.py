"""Browser-based follow action for Instagram profiles."""

import random
import time
from typing import Dict, Any

from ....utils.logger import get_logger

logger = get_logger(__name__)

try:
    from playwright.async_api import Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    Page = None


class BrowserFollowAction:
    """Follow a user via browser by profile URL."""

    def __init__(self, page: Page):
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError("Playwright is required")
        self.page = page

    async def follow_by_profile_url(self, profile_url: str) -> Dict[str, Any]:
        """Follow a user by their profile URL."""
        try:
            logger.info("Following via browser", profile_url=profile_url)
            url = profile_url.rstrip("/")
            if "/reel/" in url or "/p/" in url:
                url = url.split("/")[3]  # username from /username/reel/...
                url = f"https://www.instagram.com/{url}/"
            elif not url.startswith("http"):
                url = f"https://www.instagram.com/{url.lstrip('/')}/"
            await self.page.goto(url, wait_until="networkidle", timeout=30000)
            await self.page.wait_for_timeout(2000)

            follow_selectors = [
                'button:has-text("Follow")',
                'div[role="button"]:has-text("Follow")',
                'span:has-text("Follow")',
                '[aria-label="Follow"]',
            ]
            for sel in follow_selectors:
                try:
                    btn = await self.page.wait_for_selector(sel, timeout=5000)
                    if btn:
                        text = await btn.text_content()
                        if text and "Following" in text:
                            return {"action": "follow", "profile_url": url, "status": "already_following"}
                        await btn.click()
                        await self.page.wait_for_timeout(random.randint(800, 1500))
                        return {"action": "follow", "profile_url": url, "status": "completed"}
                except Exception:
                    continue
            return {"action": "follow", "profile_url": url, "status": "failed", "error": "Follow button not found"}
        except Exception as e:
            logger.error("Follow failed", profile_url=profile_url, error=str(e))
            return {"action": "follow", "profile_url": profile_url, "status": "failed", "error": str(e)}
