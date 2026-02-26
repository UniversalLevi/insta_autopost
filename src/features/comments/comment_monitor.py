"""Comment monitoring service - Monitor posts for new comments (cron-style with rate limits)."""

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
    Monitors Instagram posts for new comments and triggers auto-reply / comment-to-DM.
    Runs as a single cron-style loop: one cycle every check_interval_seconds, with
    stagger_seconds between accounts to avoid bursting Instagram API (rate limits).
    """

    def __init__(
        self,
        account_service: AccountService,
        comment_service: CommentService,
        comment_to_dm_service: Optional[CommentToDMService] = None,
        check_interval_seconds: int = 300,  # Cron: run comment check every 5 min (rate limit friendly)
        stagger_between_accounts_seconds: int = 45,  # Delay between accounts in one cycle
        monitor_recent_posts: int = 5,
    ):
        self.account_service = account_service
        self.comment_service = comment_service
        self.comment_to_dm_service = comment_to_dm_service
        self.check_interval_seconds = check_interval_seconds
        self.stagger_between_accounts_seconds = stagger_between_accounts_seconds
        self.monitor_recent_posts = monitor_recent_posts

        self.monitoring: Dict[str, bool] = {}
        self._global_stop = Event()
        self._global_thread: Optional[Thread] = None
    
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
            err_str = str(e)
            logger.error(
                "Failed to get recent media",
                account_id=account_id,
                error=err_str,
            )
            if "API access blocked" in err_str or "(code: 200)" in err_str:
                logger.warning(
                    "Account API access is restricted by Instagram. Reconnect the account in Meta for Developers or re-add the account.",
                    account_id=account_id,
                )
            return []
    
    def _run_one_cycle_for_account(self, account_id: str) -> None:
        """Run one comment-check cycle for a single account (cron job step)."""
        try:
            try:
                account = self.account_service.get_account(account_id)
            except AccountError as e:
                logger.warning(
                    "Comment monitor: account not found, skipping cycle",
                    account_id=account_id,
                    error=str(e),
                )
                return

            is_dm_enabled = account.comment_to_dm and account.comment_to_dm.enabled
            is_auto_reply_enabled = self.comment_service.auto_reply_enabled
            if not is_dm_enabled and not is_auto_reply_enabled:
                logger.debug("Comment monitoring skipped (all features disabled)", account_id=account_id)
                return

            recent_media = self.get_recent_media(account_id, self.monitor_recent_posts)
            for media in recent_media:
                media_id = media.get("id")
                comments_count = media.get("comments_count", 0)
                media_caption = media.get("caption", "")

                logger.debug(
                    "Processing comments for post",
                    account_id=account_id,
                    media_id=media_id,
                    comments_count=comments_count,
                )
                comments = self.comment_service.get_comments(account_id, media_id)

                try:
                    account = self.account_service.get_account(account_id)
                except AccountError:
                    continue
                other_users_comments = [
                    c for c in comments
                    if c.get("username", "").lower() != account.username.lower()
                ]

                post_config = None
                if self.comment_to_dm_service:
                    post_config = self.comment_to_dm_service.post_dm_config.get_post_dm_config(account_id, media_id)
                has_post_specific_link = post_config and post_config.get("file_url")
                should_run_dm = self.comment_to_dm_service and (has_post_specific_link or is_dm_enabled)

                comments_for_dm = []
                comments_for_auto_reply = []
                if should_run_dm:
                    dm_config = self.comment_to_dm_service._get_dm_config(account_id)
                    trigger_keyword = "AUTO"
                    if post_config and post_config.get("trigger_mode") == "KEYWORD":
                        trigger_keyword = post_config.get("trigger_word", "") or ""
                    elif dm_config:
                        trigger_keyword = dm_config.get("trigger_keyword", "AUTO")
                    for comment in other_users_comments:
                        comment_text = comment.get("text", "")
                        if self.comment_to_dm_service._should_trigger(comment_text, trigger_keyword):
                            comments_for_dm.append(comment)
                        else:
                            comments_for_auto_reply.append(comment)
                else:
                    comments_for_auto_reply = other_users_comments

                if self.comment_to_dm_service and comments_for_dm:
                    dm_results = self.comment_to_dm_service.process_new_comments_for_dm(
                        account_id=account_id,
                        media_id=media_id,
                        comments=comments_for_dm,
                        post_caption=media_caption,
                    )
                    if self.comment_service and (dm_results.get("sent", 0) > 0 or dm_results.get("fallback_replied", 0) > 0):
                        if account_id not in self.comment_service.processed_comments:
                            self.comment_service.processed_comments[account_id] = []
                        for comment in comments_for_dm:
                            cid = comment.get("id")
                            if cid and cid not in self.comment_service.processed_comments[account_id]:
                                self.comment_service.processed_comments[account_id].append(cid)
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
        except Exception as e:
            logger.error(
                "Error in comment monitoring cycle",
                account_id=account_id,
                error=str(e),
                exc_info=True,
            )

    def _cron_loop(self) -> None:
        """Single cron-style loop: every check_interval_seconds run one cycle per account with stagger."""
        logger.info(
            "Comment monitor cron started",
            check_interval_seconds=self.check_interval_seconds,
            stagger_seconds=self.stagger_between_accounts_seconds,
        )
        while not self._global_stop.is_set():
            try:
                account_ids = [aid for aid, on in self.monitoring.items() if on]
                for i, account_id in enumerate(account_ids):
                    if self._global_stop.is_set():
                        break
                    if i > 0:
                        self._global_stop.wait(timeout=self.stagger_between_accounts_seconds)
                    self._run_one_cycle_for_account(account_id)
            except Exception as e:
                logger.error("Comment monitor cron cycle error", error=str(e))
            try:
                self._global_stop.wait(timeout=self.check_interval_seconds)
            except Exception as e:
                logger.warning("Comment monitor wait error", error=str(e))
        logger.info("Comment monitor cron stopped")

    def start_monitoring(self, account_id: str) -> None:
        """Start monitoring comments for an account (adds to cron loop)."""
        if self.monitoring.get(account_id):
            logger.warning("Already monitoring", account_id=account_id)
            return
        self.monitoring[account_id] = True
        if self._global_thread is None or not self._global_thread.is_alive():
            self._global_stop.clear()
            self._global_thread = Thread(target=self._cron_loop, daemon=True, name="comment-monitor-cron")
            self._global_thread.start()
        logger.info("Started comment monitoring", account_id=account_id)

    def stop_monitoring(self, account_id: str) -> None:
        """Stop monitoring comments for an account."""
        if not self.monitoring.get(account_id):
            return
        self.monitoring[account_id] = False
        logger.info("Stopped comment monitoring", account_id=account_id)

    def start_monitoring_all_accounts(self) -> None:
        """Start monitoring for all accounts (single cron thread)."""
        for account in self.account_service.list_accounts():
            self.start_monitoring(account.account_id)

    def stop_monitoring_all_accounts(self) -> None:
        """Stop monitoring for all accounts."""
        self.monitoring.clear()
        self._global_stop.set()
        if self._global_thread:
            self._global_thread.join(timeout=5)
            if self._global_thread.is_alive():
                logger.warning("Comment monitor cron thread still alive after timeout")
            self._global_thread = None
        logger.info("Comment monitor stopped for all accounts")
