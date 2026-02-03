"""Browser automation service - coordinates browser actions"""

import asyncio
import time
from typing import Optional, Dict

from .browser_manager import BrowserManager
from .session_manager import BrowserSessionManager
from ...utils.logger import get_logger

logger = get_logger(__name__)


class BrowserService:
    """
    Service for browser-based Instagram automation.
    
    Coordinates browser instances, sessions, and actions.
    """
    
    def __init__(self, headless: bool = True):
        self.browser_manager = BrowserManager(headless=headless)
        self.session_manager = BrowserSessionManager()
        self._initialized = False
    
    async def ensure_account_logged_in(
        self,
        account_id: str,
        username: str,
        password: Optional[str] = None,
        proxy_url: Optional[str] = None,
    ) -> bool:
        """
        Ensure account is logged into Instagram
        
        Args:
            account_id: Account identifier
            username: Instagram username
            password: Instagram password (if needed)
            proxy_url: Optional proxy URL
            
        Returns:
            True if logged in, False otherwise
        """
        try:
            page = await self.browser_manager.get_page_for_account(account_id, proxy_url)
            
            # Try to load saved session
            session_loaded = await self.session_manager.load_session(account_id, page)
            
            # Check if already logged in
            if await self.session_manager.is_logged_in(page):
                logger.info("Account already logged in", account_id=account_id, username=username)
                return True
            
            # If not logged in and we have password, try to login
            if password:
                logger.info("Logging in to Instagram", account_id=account_id, username=username)
                success = await self.session_manager.login(page, username, password, account_id)
                if success:
                    logger.info("Login successful", account_id=account_id, username=username)
                    return True
                else:
                    logger.error("Login failed", account_id=account_id, username=username)
                    return False
            else:
                logger.warning(
                    "Not logged in and no password provided",
                    account_id=account_id,
                    username=username,
                )
                return False
                
        except Exception as e:
            logger.error("Error ensuring login", account_id=account_id, error=str(e))
            return False
    
    async def like_post(
        self,
        account_id: str,
        post_url: str,
        username: str,
        password: Optional[str] = None,
        proxy_url: Optional[str] = None,
    ) -> Dict:
        """
        Like a post using browser automation
        
        Args:
            account_id: Account identifier
            post_url: Instagram post URL
            username: Instagram username (for login)
            password: Instagram password (for login if needed)
            proxy_url: Optional proxy URL
            
        Returns:
            Action result dictionary
        """
        try:
            # Ensure logged in
            logged_in = await self.ensure_account_logged_in(
                account_id=account_id,
                username=username,
                password=password,
                proxy_url=proxy_url,
            )
            
            if not logged_in:
                return {
                    "action": "like",
                    "post_url": post_url,
                    "status": "failed",
                    "error": "Not logged into Instagram",
                    "timestamp": time.time(),
                }
            
            # Get page and perform like
            page = await self.browser_manager.get_page_for_account(account_id, proxy_url)
            
            from .actions.like_action import BrowserLikeAction
            like_action = BrowserLikeAction(page)
            
            result = await like_action.like_post_by_url(post_url)
            
            return result
            
        except Exception as e:
            logger.error("Error liking post", account_id=account_id, post_url=post_url, error=str(e))
            return {
                "action": "like",
                "post_url": post_url,
                "status": "failed",
                "error": str(e),
                "timestamp": time.time(),
            }
    
    async def close_account(self, account_id: str):
        """Close browser for an account"""
        await self.browser_manager.close_account_browser(account_id)
    
    async def close_all(self):
        """Close all browsers"""
        await self.browser_manager.close_all()

    async def save_post(
        self,
        account_id: str,
        post_url: str,
        username: str,
        password=None,
        proxy_url=None,
    ) -> Dict:
        """Save (bookmark) a post via browser."""
        try:
            logged_in = await self.ensure_account_logged_in(account_id, username, password, proxy_url)
            if not logged_in:
                return {"action": "save", "post_url": post_url, "status": "failed", "error": "Not logged in"}
            page = await self.browser_manager.get_page_for_account(account_id, proxy_url)
            from .actions.save_action import BrowserSaveAction
            action = BrowserSaveAction(page)
            return await action.save_post_by_url(post_url)
        except Exception as e:
            logger.error("Save failed", account_id=account_id, error=str(e))
            return {"action": "save", "post_url": post_url, "status": "failed", "error": str(e)}

    async def follow_profile(
        self,
        account_id: str,
        profile_url: str,
        username: str,
        password=None,
        proxy_url=None,
    ) -> Dict:
        """Follow a profile via browser."""
        try:
            logged_in = await self.ensure_account_logged_in(account_id, username, password, proxy_url)
            if not logged_in:
                return {"action": "follow", "profile_url": profile_url, "status": "failed", "error": "Not logged in"}
            page = await self.browser_manager.get_page_for_account(account_id, proxy_url)
            from .actions.follow_action import BrowserFollowAction
            action = BrowserFollowAction(page)
            return await action.follow_by_profile_url(profile_url)
        except Exception as e:
            logger.error("Follow failed", account_id=account_id, error=str(e))
            return {"action": "follow", "profile_url": profile_url, "status": "failed", "error": str(e)}

    async def comment_on_post(
        self,
        account_id: str,
        post_url: str,
        text: str,
        username: str,
        password=None,
        proxy_url=None,
    ) -> Dict:
        """Comment on a post via browser."""
        try:
            logged_in = await self.ensure_account_logged_in(account_id, username, password, proxy_url)
            if not logged_in:
                return {"action": "comment", "post_url": post_url, "status": "failed", "error": "Not logged in"}
            page = await self.browser_manager.get_page_for_account(account_id, proxy_url)
            from .actions.comment_action import BrowserCommentAction
            action = BrowserCommentAction(page)
            return await action.comment_on_post_by_url(post_url, text)
        except Exception as e:
            logger.error("Comment failed", account_id=account_id, error=str(e))
            return {"action": "comment", "post_url": post_url, "status": "failed", "error": str(e)}

    async def discover_post_urls(
        self,
        account_id: str,
        hashtags: list,
        limit_per_hashtag: int = 5,
        username: str = "",
        password=None,
        proxy_url=None,
    ) -> list:
        """Discover post URLs from hashtag pages."""
        urls = []
        try:
            logged_in = await self.ensure_account_logged_in(account_id, username, password, proxy_url)
            if not logged_in:
                return []
            page = await self.browser_manager.get_page_for_account(account_id, proxy_url)
            from .actions.explore_action import BrowserExploreAction
            action = BrowserExploreAction(page)
            for tag in (hashtags or ["explore"])[:3]:
                found = await action.get_post_urls_from_hashtag(tag, limit=limit_per_hashtag)
                for u in found:
                    if u not in urls:
                        urls.append(u)
                if len(urls) >= limit_per_hashtag * 3:
                    break
            if not urls:
                urls = await action.get_post_urls_from_explore(limit=10)
        except Exception as e:
            logger.warning("Discovery failed", account_id=account_id, error=str(e))
        return urls
