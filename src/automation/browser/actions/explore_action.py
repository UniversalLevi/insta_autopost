"""Browser-based Explore/hashtag discovery - collect post URLs for warm-up."""

import asyncio
import re
from typing import List

from ....utils.logger import get_logger

logger = get_logger(__name__)

try:
    from playwright.async_api import Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    Page = None

POST_URL_PATTERN = re.compile(r"https?://(?:www\.)?instagram\.com/p/([A-Za-z0-9_-]+)/?")
REEL_URL_PATTERN = re.compile(r"https?://(?:www\.)?instagram\.com/reel/([A-Za-z0-9_-]+)/?")


class BrowserExploreAction:
    """Discover post URLs from Explore or hashtag page."""

    def __init__(self, page: Page):
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError("Playwright is required")
        self.page = page

    async def get_post_urls_from_hashtag(self, hashtag: str, limit: int = 15) -> List[str]:
        """Navigate to hashtag explore page and collect post URLs."""
        urls = []
        try:
            tag = hashtag.replace("#", "").strip()
            url = f"https://www.instagram.com/explore/tags/{tag}/"
            logger.info("Discovering posts from hashtag", hashtag=tag)
            await self.page.goto(url, wait_until="networkidle", timeout=30000)
            await self.page.wait_for_timeout(3000)

            # Get all post/reel links from page
            links = await self.page.evaluate(
                """() => [...document.querySelectorAll('a[href*="/p/"], a[href*="/reel/"]')].map(a => a.href)"""
            )
            seen = set()
            for href in (links or []):
                if len(urls) >= limit:
                    break
                m = POST_URL_PATTERN.search(href) or REEL_URL_PATTERN.search(href)
                if m and href not in seen:
                    seen.add(href)
                    urls.append(href)
            logger.info("Found post URLs", count=len(urls), hashtag=tag)
        except Exception as e:
            logger.warning("Hashtag discovery failed", hashtag=hashtag, error=str(e))
        return urls[:limit]

    async def get_post_urls_from_explore(self, limit: int = 15) -> List[str]:
        """Navigate to Explore and collect post URLs."""
        urls = []
        try:
            await self.page.goto("https://www.instagram.com/explore/", wait_until="networkidle", timeout=30000)
            await self.page.wait_for_timeout(3000)
            links = await self.page.evaluate(
                """() => [...document.querySelectorAll('a[href*="/p/"], a[href*="/reel/"]')].map(a => a.href)"""
            )
            seen = set()
            for href in (links or []):
                if len(urls) >= limit:
                    break
                m = POST_URL_PATTERN.search(href) or REEL_URL_PATTERN.search(href)
                if m and href not in seen:
                    seen.add(href)
                    urls.append(href)
        except Exception as e:
            logger.warning("Explore discovery failed", error=str(e))
        return urls[:limit]
