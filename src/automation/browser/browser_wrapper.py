"""Synchronous wrapper for async browser operations"""

import asyncio
from typing import Optional, Dict

from .browser_service import BrowserService
from ...utils.logger import get_logger

logger = get_logger(__name__)


class BrowserWrapper:
    """
    Synchronous wrapper for browser automation service.
    
    This allows browser automation to be used from synchronous code.
    """
    
    def __init__(self, headless: bool = True):
        self.browser_service = BrowserService(headless=headless)
        self._loop = None
    
    def _get_event_loop(self):
        """Get or create event loop"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                raise RuntimeError("Loop is closed")
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop
    
    def like_post_sync(
        self,
        account_id: str,
        post_url: str,
        username: str,
        password: Optional[str] = None,
        proxy_url: Optional[str] = None,
    ) -> Dict:
        """
        Like a post synchronously
        
        Args:
            account_id: Account identifier
            post_url: Instagram post URL
            username: Instagram username
            password: Instagram password (optional)
            proxy_url: Optional proxy URL
            
        Returns:
            Action result dictionary
        """
        loop = self._get_event_loop()
        return loop.run_until_complete(
            self.browser_service.like_post(
                account_id=account_id,
                post_url=post_url,
                username=username,
                password=password,
                proxy_url=proxy_url,
            )
        )
    
    def close_account(self, account_id: str):
        """Close browser for an account"""
        loop = self._get_event_loop()
        loop.run_until_complete(self.browser_service.close_account(account_id))
    
    def close_all(self):
        """Close all browsers"""
        try:
            loop = self._get_event_loop()
            if loop.is_running():
                import asyncio
                asyncio.create_task(self.browser_service.close_all())
            else:
                loop.run_until_complete(self.browser_service.close_all())
        except RuntimeError:
            pass

    def save_post_sync(self, account_id: str, post_url: str, username: str, password=None, proxy_url=None) -> Dict:
        """Save a post (sync wrapper)."""
        loop = self._get_event_loop()
        return loop.run_until_complete(
            self.browser_service.save_post(account_id, post_url, username, password, proxy_url)
        )

    def follow_profile_sync(self, account_id: str, profile_url: str, username: str, password=None, proxy_url=None) -> Dict:
        """Follow a profile (sync wrapper)."""
        loop = self._get_event_loop()
        return loop.run_until_complete(
            self.browser_service.follow_profile(account_id, profile_url, username, password, proxy_url)
        )

    def comment_on_post_sync(self, account_id: str, post_url: str, text: str, username: str, password=None, proxy_url=None) -> Dict:
        """Comment on a post (sync wrapper)."""
        loop = self._get_event_loop()
        return loop.run_until_complete(
            self.browser_service.comment_on_post(account_id, post_url, text, username, password, proxy_url)
        )

    def discover_post_urls_sync(self, account_id: str, hashtags: list, limit_per_hashtag: int = 5, username: str = "", password=None, proxy_url=None) -> list:
        """Discover post URLs (sync wrapper)."""
        loop = self._get_event_loop()
        return loop.run_until_complete(
            self.browser_service.discover_post_urls(account_id, hashtags, limit_per_hashtag, username, password, proxy_url)
        )
