"""Browser-based like action for Instagram"""

import random
import time
from typing import Dict, Any, Optional

from ....utils.logger import get_logger

logger = get_logger(__name__)

try:
    from playwright.async_api import Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    Page = None


class BrowserLikeAction:
    """
    Browser-based like action using Playwright.
    
    This performs actual likes on Instagram posts by interacting with the web UI.
    """
    
    def __init__(self, page: Page):
        """
        Initialize browser like action
        
        Args:
            page: Playwright Page instance (logged into Instagram)
        """
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError("Playwright is required for browser automation")
        
        self.page = page
    
    async def like_post_by_url(self, post_url: str) -> Dict[str, Any]:
        """
        Like a post by its URL
        
        Args:
            post_url: Instagram post URL (e.g., https://www.instagram.com/p/ABC123/)
            
        Returns:
            Action result dictionary
        """
        try:
            logger.info("Liking post via browser", post_url=post_url)
            
            # Navigate to post
            await self.page.goto(post_url, wait_until="networkidle", timeout=30000)
            
            # Wait a bit for page to fully load
            await self.page.wait_for_timeout(2000)
            
            # Find and click the like button
            # Instagram's like button can be: svg[aria-label="Like"], button[aria-label="Like"], etc.
            like_selectors = [
                'svg[aria-label="Like"]',
                'button[aria-label="Like"]',
                '[aria-label="Like"]',
                'svg[aria-label*="Like"]',
            ]
            
            liked = False
            for selector in like_selectors:
                try:
                    like_button = await self.page.wait_for_selector(selector, timeout=5000)
                    if like_button:
                        # Check if already liked
                        parent = await like_button.query_selector("..")
                        if parent:
                            aria_label = await parent.get_attribute("aria-label")
                            if aria_label and "Unlike" in aria_label:
                                logger.debug("Post already liked", post_url=post_url)
                                return {
                                    "action": "like",
                                    "post_url": post_url,
                                    "status": "already_liked",
                                    "timestamp": time.time(),
                                }
                        
                        # Click like button
                        await like_button.click()
                        
                        # Wait for like animation
                        await self.page.wait_for_timeout(1000)
                        
                        liked = True
                        logger.info("Post liked successfully", post_url=post_url)
                        break
                except Exception as e:
                    logger.debug(f"Selector {selector} failed, trying next", error=str(e))
                    continue
            
            if not liked:
                logger.warning("Could not find like button", post_url=post_url)
                return {
                    "action": "like",
                    "post_url": post_url,
                    "status": "failed",
                    "error": "Could not find like button",
                    "timestamp": time.time(),
                }
            
            # Human-like delay after liking
            await self.page.wait_for_timeout(random.randint(500, 1500))
            
            return {
                "action": "like",
                "post_url": post_url,
                "status": "completed",
                "timestamp": time.time(),
            }
            
        except Exception as e:
            logger.error("Failed to like post", post_url=post_url, error=str(e))
            return {
                "action": "like",
                "post_url": post_url,
                "status": "failed",
                "error": str(e),
                "timestamp": time.time(),
            }
    
    async def like_post_by_shortcode(self, shortcode: str) -> Dict[str, Any]:
        """
        Like a post by its shortcode
        
        Args:
            shortcode: Instagram post shortcode (from media ID or URL)
            
        Returns:
            Action result dictionary
        """
        # Convert shortcode to URL
        post_url = f"https://www.instagram.com/p/{shortcode}/"
        return await self.like_post_by_url(post_url)
