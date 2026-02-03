"""Browser-based save (bookmark) action for Instagram posts."""

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


class BrowserSaveAction:
    """Save a post via browser (bookmark)."""

    def __init__(self, page: Page):
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError("Playwright is required")
        self.page = page

    async def save_post_by_url(self, post_url: str) -> Dict[str, Any]:
        """Save a post by its URL."""
        try:
            logger.info("Saving post via browser", post_url=post_url)
            await self.page.goto(post_url, wait_until="networkidle", timeout=30000)
            await self.page.wait_for_timeout(2000)

            save_selectors = [
                'svg[aria-label="Save"]',
                'button[aria-label="Save"]',
                '[aria-label="Save"]',
                'svg[aria-label*="Save"]',
            ]
            for selector in save_selectors:
                try:
                    btn = await self.page.wait_for_selector(selector, timeout=5000)
                    if btn:
                        parent = await btn.query_selector("..")
                        if parent:
                            aria = await parent.get_attribute("aria-label")
                            if aria and "Unsave" in aria:
                                return {"action": "save", "post_url": post_url, "status": "already_saved"}
                        await btn.click()
                        await self.page.wait_for_timeout(random.randint(500, 1200))
                        return {"action": "save", "post_url": post_url, "status": "completed"}
                except Exception:
                    continue
            return {"action": "save", "post_url": post_url, "status": "failed", "error": "Save button not found"}
        except Exception as e:
            logger.error("Save failed", post_url=post_url, error=str(e))
            return {"action": "save", "post_url": post_url, "status": "failed", "error": str(e)}
