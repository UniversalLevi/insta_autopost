"""Browser automation service - coordinates browser actions"""

import asyncio
import time
from typing import Optional, Dict

from .browser_manager import BrowserManager
from .browser_utils import is_browser_closed_error, BrowserClosedError
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
                try:
                    success = await self.session_manager.login(page, username, password, account_id)
                    if success:
                        logger.info("Login successful", account_id=account_id, username=username)
                        return True
                    else:
                        logger.error("Login failed", account_id=account_id, username=username)
                        return False
                except BrowserClosedError:
                    logger.debug("Browser closed during login (likely shutdown)", account_id=account_id)
                    return False
            else:
                logger.warning(
                    "Not logged in and no password provided",
                    account_id=account_id,
                    username=username,
                )
                return False
                
        except Exception as e:
            if is_browser_closed_error(e):
                logger.debug("Browser closed during login (likely shutdown)", account_id=account_id)
            else:
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

    async def follow_by_post_or_reel_url(
        self,
        account_id: str,
        post_or_reel_url: str,
        username: str,
        password=None,
        proxy_url=None,
    ) -> Dict:
        """Open a post/reel, find the creator's profile, and follow via browser."""
        try:
            logged_in = await self.ensure_account_logged_in(account_id, username, password, proxy_url)
            if not logged_in:
                return {
                    "action": "follow",
                    "post_or_reel_url": post_or_reel_url,
                    "status": "failed",
                    "error": "Not logged in",
                }
            page = await self.browser_manager.get_page_for_account(account_id, proxy_url)
            from .actions.follow_action import BrowserFollowAction
            action = BrowserFollowAction(page)
            return await action.follow_by_post_or_reel_url(post_or_reel_url)
        except Exception as e:
            logger.error(
                "Follow by post/reel failed",
                account_id=account_id,
                post_or_reel_url=post_or_reel_url,
                error=str(e),
            )
            return {
                "action": "follow",
                "post_or_reel_url": post_or_reel_url,
                "status": "failed",
                "error": str(e),
            }

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
        """Discover post URLs: Reels tab first, then Explore, then hashtags, then built-in fallback hashtags."""
        # High-volume hashtags that almost always have posts (used when user hashtags yield nothing)
        FALLBACK_HASHTAGS = [
            "love", "photo", "instagood", "art", "nature", "travel",
            "fashion", "food", "music", "photography",
        ]
        target_count = max(10, limit_per_hashtag * 3)
        urls = []
        try:
            logged_in = await self.ensure_account_logged_in(account_id, username, password, proxy_url)
            if not logged_in:
                return []
            page = await self.browser_manager.get_page_for_account(account_id, proxy_url)
            from .actions.explore_action import BrowserExploreAction
            action = BrowserExploreAction(page)
            # 1. Try Reels tab first
            urls = await action.get_post_urls_from_reels(limit=target_count)
            if not urls:
                logger.info("Reels returned no URLs, falling back to Explore and hashtags")
            # 2. If needed, try Explore page (full target when Reels gave nothing)
            if len(urls) < target_count:
                need = target_count - len(urls)
                found = await action.get_post_urls_from_explore(limit=max(need, 10))
                for u in found:
                    if u not in urls:
                        urls.append(u)
            # 3. If needed, try user hashtags (skip literal "explore" as hashtag)
            user_tags = [t.replace("#", "").strip() for t in (hashtags or []) if t and str(t).strip().lower() != "explore"]
            for tag in user_tags[:3]:
                if len(urls) >= target_count:
                    break
                found = await action.get_post_urls_from_hashtag(tag, limit=limit_per_hashtag)
                for u in found:
                    if u not in urls:
                        urls.append(u)
            # 4. If still not enough, try built-in high-volume hashtags
            if len(urls) < target_count:
                for tag in FALLBACK_HASHTAGS:
                    if len(urls) >= target_count:
                        break
                    found = await action.get_post_urls_from_hashtag(tag, limit=limit_per_hashtag)
                    for u in found:
                        if u not in urls:
                            urls.append(u)
        except Exception as e:
            logger.warning("Discovery failed", account_id=account_id, error=str(e))
        return urls
