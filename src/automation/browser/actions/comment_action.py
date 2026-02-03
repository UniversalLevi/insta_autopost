"""Browser-based comment action for Instagram posts."""

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


class BrowserCommentAction:
    """Comment on a post via browser."""

    def __init__(self, page: Page):
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError("Playwright is required")
        self.page = page

    async def comment_on_post_by_url(self, post_url: str, text: str) -> Dict[str, Any]:
        """Comment on a post by URL."""
        try:
            logger.info("Commenting via browser", post_url=post_url)
            await self.page.goto(post_url, wait_until="networkidle", timeout=30000)
            await self.page.wait_for_timeout(2000)

            # Instagram comment box: textarea or div with contenteditable
            comment_selectors = [
                'textarea[placeholder*="Add a comment"]',
                'textarea[aria-label*="comment"]',
                'form textarea',
                'div[contenteditable="true"][aria-label*="comment"]',
            ]
            for sel in comment_selectors:
                try:
                    box = await self.page.wait_for_selector(sel, timeout=5000)
                    if box:
                        await box.click()
                        await self.page.wait_for_timeout(500)
                        await box.fill(text)
                        await self.page.wait_for_timeout(500)
                        # Submit: Enter or Post button
                        await box.press("Enter")
                        await self.page.wait_for_timeout(random.randint(1000, 2000))
                        return {"action": "comment", "post_url": post_url, "status": "completed"}
                except Exception:
                    continue
            return {"action": "comment", "post_url": post_url, "status": "failed", "error": "Comment box not found"}
        except Exception as e:
            logger.error("Comment failed", post_url=post_url, error=str(e))
            return {"action": "comment", "post_url": post_url, "status": "failed", "error": str(e)}
