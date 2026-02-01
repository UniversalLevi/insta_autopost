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
                # If loop is running, schedule close_all as a task
                import asyncio
                asyncio.create_task(self.browser_service.close_all())
            else:
                loop.run_until_complete(self.browser_service.close_all())
        except RuntimeError:
            # Event loop might be closed during shutdown
            pass
