"""Comment monitoring service - Monitor posts for new comments"""

import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from threading import Thread, Event

from ...services.account_service import AccountService
from ...api.instagram_client import InstagramClient
from ...utils.logger import get_logger
from .comment_service import CommentService
from .comment_to_dm_service import CommentToDMService

logger = get_logger(__name__)


class CommentMonitor:
    """
    Monitors Instagram posts for new comments and triggers auto-reply.
    
    Features:
    - Periodic monitoring of recent posts
    - Automatic comment processing
    - Configurable check intervals
    """
    
    def __init__(
        self,
        account_service: AccountService,
        comment_service: CommentService,
        comment_to_dm_service: Optional[CommentToDMService] = None,
        check_interval_seconds: int = 60,  # Check every minute
        monitor_recent_posts: int = 5,  # Monitor last 5 posts
    ):
        self.account_service = account_service
        self.comment_service = comment_service
        self.comment_to_dm_service = comment_to_dm_service
        self.check_interval_seconds = check_interval_seconds
        self.monitor_recent_posts = monitor_recent_posts
        
        self.monitoring: Dict[str, bool] = {}  # account_id -> is_monitoring
        self.monitor_threads: Dict[str, Thread] = {}
        self.stop_events: Dict[str, Event] = {}
    
    def get_recent_media(self, account_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent media posts for an account
        
        Args:
            account_id: Account identifier
            limit: Number of recent posts to retrieve
            
        Returns:
            List of media posts
        """
        client = self.account_service.get_client(account_id)
        
        try:
            response = client._make_request(
                "GET",
                "me/media",
                params={
                    "fields": "id,caption,timestamp,like_count,comments_count",
                    "limit": limit,
                }
            )
            
            media_list = response.get("data", [])
            logger.debug(
                "Retrieved recent media",
                account_id=account_id,
                count=len(media_list),
            )
            
            return media_list
            
        except Exception as e:
            logger.error(
                "Failed to get recent media",
                account_id=account_id,
                error=str(e),
            )
            return []
    
    def monitor_account_comments(self, account_id: str):
        """
        Monitor comments for a specific account (runs in thread)
        
        Args:
            account_id: Account identifier
        """
        stop_event = self.stop_events.get(account_id)
        if not stop_event:
            stop_event = Event()
            self.stop_events[account_id] = stop_event
        
        logger.info(
            "Starting comment monitoring",
            account_id=account_id,
            check_interval=self.check_interval_seconds,
        )
        
        while not stop_event.is_set():
            try:
                # Check if monitoring is enabled for this account
                account = self.account_service.get_account(account_id)
                
                # Check if Comment-to-DM is enabled
                is_dm_enabled = account.comment_to_dm and account.comment_to_dm.enabled
                
                # Check if auto-reply is enabled (from comment_service config)
                is_auto_reply_enabled = self.comment_service.auto_reply_enabled
                
                # If no monitoring features are enabled, skip this cycle
                if not is_dm_enabled and not is_auto_reply_enabled:
                    logger.debug("Comment monitoring skipped (all features disabled)", account_id=account_id)
                    stop_event.wait(timeout=self.check_interval_seconds)
                    continue

                # Get recent posts
                recent_media = self.get_recent_media(account_id, self.monitor_recent_posts)
                
                # Process comments for each post
                # Note: We check ALL posts, not just those with comments_count > 0
                # because Instagram API may not always return accurate comment counts
                for media in recent_media:
                    media_id = media.get("id")
                    comments_count = media.get("comments_count", 0)
                    media_caption = media.get("caption", "")
                    
                    # Always check for comments (comments_count may be inaccurate)
                    logger.debug(
                        "Checking comments on post",
                        account_id=account_id,
                        media_id=media_id,
                        comments_count=comments_count,
                    )
                    
                    # Get comments for processing (always try, even if count is 0)
                    comments = self.comment_service.get_comments(account_id, media_id)
                    
                    # Process comments for auto-reply (existing functionality)
                    results = self.comment_service.process_new_comments(
                        account_id=account_id,
                        media_id=media_id,
                    )
                    
                    if results["replied"] > 0:
                        logger.info(
                            "Auto-replied to comments",
                            account_id=account_id,
                            media_id=media_id,
                            replied_count=results["replied"],
                        )
                    
                    # Process comments for comment-to-DM automation
                    # Uses new method that tracks last processed comment ID per post
                    if self.comment_to_dm_service:
                        # Filter out own comments before processing
                        account = self.account_service.get_account(account_id)
                        other_users_comments = [
                            c for c in comments
                            if c.get("username", "").lower() != account.username.lower()
                        ]
                        
                        # Process new comments (tracks last processed comment ID per post)
                        dm_results = self.comment_to_dm_service.process_new_comments_for_dm(
                            account_id=account_id,
                            media_id=media_id,
                            comments=other_users_comments,
                            post_caption=media_caption,
                        )
                        
                        if dm_results["sent"] > 0 or dm_results["failed"] > 0:
                            logger.info(
                                "Comment-to-DM automation completed",
                                account_id=account_id,
                                media_id=media_id,
                                new_comments=dm_results.get("new_comments", 0),
                                dms_sent=dm_results["sent"],
                                skipped=dm_results["skipped"],
                                failed=dm_results["failed"],
                            )
                
                # Wait for next check interval
                stop_event.wait(timeout=self.check_interval_seconds)
                
            except Exception as e:
                logger.error(
                    "Error in comment monitoring",
                    account_id=account_id,
                    error=str(e),
                    exc_info=True,
                )
                # Wait a bit before retrying
                stop_event.wait(timeout=10)
        
        logger.info("Comment monitoring stopped", account_id=account_id)
    
    def start_monitoring(self, account_id: str):
        """Start monitoring comments for an account"""
        if account_id in self.monitoring and self.monitoring[account_id]:
            logger.warning("Already monitoring", account_id=account_id)
            return
        
        self.monitoring[account_id] = True
        
        # Create stop event if it doesn't exist
        if account_id not in self.stop_events:
            self.stop_events[account_id] = Event()
        else:
            self.stop_events[account_id].clear()
        
        # Start monitoring thread
        thread = Thread(
            target=self.monitor_account_comments,
            args=(account_id,),
            daemon=True,
        )
        thread.start()
        self.monitor_threads[account_id] = thread
        
        logger.info("Started comment monitoring", account_id=account_id)
    
    def stop_monitoring(self, account_id: str):
        """Stop monitoring comments for an account"""
        if account_id not in self.monitoring or not self.monitoring[account_id]:
            return
        
        self.monitoring[account_id] = False
        
        # Signal stop
        if account_id in self.stop_events:
            self.stop_events[account_id].set()
        
        # Wait for thread to finish
        if account_id in self.monitor_threads:
            thread = self.monitor_threads[account_id]
            thread.join(timeout=5)
            del self.monitor_threads[account_id]
        
        logger.info("Stopped comment monitoring", account_id=account_id)
    
    def start_monitoring_all_accounts(self):
        """Start monitoring for all accounts"""
        accounts = self.account_service.list_accounts()
        for account in accounts:
            self.start_monitoring(account.account_id)
    
    def stop_monitoring_all_accounts(self):
        """Stop monitoring for all accounts"""
        for account_id in list(self.monitoring.keys()):
            self.stop_monitoring(account_id)
