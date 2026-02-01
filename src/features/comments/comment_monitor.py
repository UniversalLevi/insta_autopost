"""Comment monitoring service - Monitor posts for new comments"""

import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from threading import Thread, Event

from ...services.account_service import AccountService
from ...api.instagram_client import InstagramClient
from ...utils.logger import get_logger
from ...utils.exceptions import AccountError
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
        try:
            client = self.account_service.get_client(account_id)
        except AccountError as e:
            logger.warning(
                "Comment monitor: account/client not found, skipping media fetch",
                account_id=account_id,
                error=str(e),
            )
            return []
        
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
                try:
                    account = self.account_service.get_account(account_id)
                except AccountError as e:
                    logger.warning(
                        "Comment monitor: account not found, skipping cycle",
                        account_id=account_id,
                        error=str(e),
                    )
                    stop_event.wait(timeout=self.check_interval_seconds)
                    continue
                
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
                    logger.info(
                        "Processing comments for post",
                        account_id=account_id,
                        media_id=media_id,
                        comments_count=comments_count,
                        caption_preview=media_caption[:50] if media_caption else None,
                    )
                    
                    # Get comments for processing (always try, even if count is 0)
                    comments = self.comment_service.get_comments(account_id, media_id)
                    
                    logger.debug(
                        "Retrieved comments for post",
                        account_id=account_id,
                        media_id=media_id,
                        comment_count=len(comments),
                    )
                    
                    # Filter out own comments
                    try:
                        account = self.account_service.get_account(account_id)
                    except AccountError as e:
                        logger.warning(
                            "Comment monitor: account not found for post, skipping post",
                            account_id=account_id,
                            media_id=media_id,
                            error=str(e),
                        )
                        continue
                    other_users_comments = [
                        c for c in comments
                        if c.get("username", "").lower() != account.username.lower()
                    ]
                    
                    # Check if DM automation should run for this post
                    # Priority: Post-specific config > Account-level config
                    post_config = None
                    if self.comment_to_dm_service:
                        post_config = self.comment_to_dm_service.post_dm_config.get_post_dm_config(account_id, media_id)
                    
                    # DM should run if:
                    # 1. Post has specific config with a link (even if account-level is disabled)
                    # 2. OR account-level is enabled
                    has_post_specific_link = post_config and post_config.get("file_url")
                    should_run_dm = self.comment_to_dm_service and (has_post_specific_link or is_dm_enabled)
                    
                    # Determine which comments comment-to-DM will handle
                    comments_for_dm = []
                    comments_for_auto_reply = []
                    
                    if should_run_dm:
                        # Get DM config to check trigger keyword
                        dm_config = self.comment_to_dm_service._get_dm_config(account_id)
                        
                        # Determine trigger (post-specific > account global)
                        trigger_keyword = "AUTO"
                        if post_config and post_config.get("trigger_mode") == "KEYWORD":
                            trigger_keyword = post_config.get("trigger_word", "") or ""
                            logger.info(
                                "Using post-specific trigger keyword",
                                account_id=account_id,
                                media_id=media_id,
                                keyword=trigger_keyword
                            )
                        elif dm_config:
                            trigger_keyword = dm_config.get("trigger_keyword", "AUTO")
                            logger.info(
                                "Using account-global trigger keyword",
                                account_id=account_id,
                                media_id=media_id,
                                keyword=trigger_keyword
                            )
                        
                        # Split comments: those matching DM trigger go to DM, others to auto-reply
                        for comment in other_users_comments:
                            comment_text = comment.get("text", "")
                            if self.comment_to_dm_service._should_trigger(comment_text, trigger_keyword):
                                comments_for_dm.append(comment)
                            else:
                                comments_for_auto_reply.append(comment)
                    else:
                        # No DM automation, all comments go to auto-reply
                        comments_for_auto_reply = other_users_comments
                    
                    # Process comments for comment-to-DM automation FIRST
                    # Uses new method that tracks last processed comment ID per post
                    dm_handled_comment_ids = set()
                    dm_results = {"processed": 0, "sent": 0, "skipped": 0, "failed": 0, "new_comments": 0, "fallback_replied": 0}
                    if self.comment_to_dm_service and comments_for_dm:
                        # Process new comments (tracks last processed comment ID per post)
                        dm_results = self.comment_to_dm_service.process_new_comments_for_dm(
                            account_id=account_id,
                            media_id=media_id,
                            comments=comments_for_dm,
                            post_caption=media_caption,
                        )
                        
                        # Track which comments actually got a response (DM sent OR fallback replied)
                        # We mark them as processed in auto-reply to prevent duplicates
                        # Comments that were skipped for other reasons (already DM'd, safety limit, etc.) are NOT marked,
                        # so auto-reply can still handle them
                        if self.comment_service and (dm_results.get("sent", 0) > 0 or dm_results.get("fallback_replied", 0) > 0):
                            # At least one comment got a response (DM or fallback reply). Mark all DM-targeted comments.
                            # This prevents auto-reply from also replying to the same comments.
                            if account_id not in self.comment_service.processed_comments:
                                self.comment_service.processed_comments[account_id] = []
                            for comment in comments_for_dm:
                                comment_id = comment.get("id")
                                if comment_id and comment_id not in self.comment_service.processed_comments[account_id]:
                                    self.comment_service.processed_comments[account_id].append(comment_id)
                                    dm_handled_comment_ids.add(comment_id)
                        
                        # Log DM results
                        if dm_results.get("sent", 0) > 0 or dm_results.get("failed", 0) > 0 or dm_results.get("skipped", 0) > 0 or dm_results.get("fallback_replied", 0) > 0:
                            logger.info(
                                "Comment-to-DM automation completed",
                                account_id=account_id,
                                media_id=media_id,
                                new_comments=dm_results.get("new_comments", 0),
                                dms_sent=dm_results.get("sent", 0),
                                skipped=dm_results.get("skipped", 0),
                                failed=dm_results.get("failed", 0),
                                fallback_replied=dm_results.get("fallback_replied", 0),
                            )
                    
                    # Process comments for auto-reply (comments NOT handled by DM)
                    # This includes: comments that don't match DM trigger, AND comments that matched trigger but DM skipped them
                    if comments_for_auto_reply and is_auto_reply_enabled:
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
        
        # Wait for thread to finish (but don't block too long). Daemon threads will exit with process.
        if account_id in self.monitor_threads:
            thread = self.monitor_threads[account_id]
            try:
                thread.join(timeout=2)
                if thread.is_alive():
                    logger.warning(
                        "Comment monitor thread still alive after timeout, continuing shutdown",
                        account_id=account_id,
                    )
            except Exception as e:
                logger.warning(
                    "Comment monitor stop wait interrupted, continuing shutdown",
                    account_id=account_id,
                    error=str(e),
                )
            finally:
                self.monitor_threads.pop(account_id, None)
        
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
