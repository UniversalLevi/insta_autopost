"""Comment-to-DM automation service - Send DMs when users comment

Extended implementation matching LinkDM/autodms.in behavior:
- Track last processed comment ID per post
- Flexible trigger keyword logic (AUTO or specific keyword)
- One DM per user per post per day
- Configurable safety limits (daily limits, cooldowns)
- Comprehensive logging at every step
- Graceful error handling with retry logic
"""

import time
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta
from collections import defaultdict

from ...services.account_service import AccountService
from ...utils.logger import get_logger
from ...utils.exceptions import InstagramAPIError
from ...ai.ai_reply_service import AIReplyService, FALLBACK_REPLY
from .post_dm_config import PostDMConfig
from .dm_tracking import DMTracking

logger = get_logger(__name__)


class CommentToDMService:
    """
    Service for automated comment-to-DM funnel (LinkDM/autodms.in style).
    
    Features:
    - Tracks last processed comment ID per post to avoid duplicates
    - Flexible trigger logic: AUTO (any comment) or keyword-based
    - One DM per user per post per day
    - Configurable safety limits (daily DM limits, cooldown intervals)
    - Comprehensive logging at every step
    - Retry logic with exponential backoff for API failures
    """
    
    def __init__(self, account_service: AccountService):
        self.account_service = account_service
        self.post_dm_config = PostDMConfig()  # Per-post file/link configuration
        self.dm_tracking = DMTracking()  # Persistent tracking of processed comments
        self.ai_reply_service = AIReplyService()
        
        # Track last processed comment ID per post
        # Format: account_id -> {media_id: last_processed_comment_id}
        self.last_processed_comment_id: Dict[str, Dict[str, str]] = defaultdict(dict)
        
        # Track users who received DM today (per user per post per day)
        # Format: account_id -> {(user_id, media_id, date): True}
        self.users_dm_today: Dict[str, Set[tuple]] = defaultdict(set)
        
        # Track daily DM counts per account
        # Format: account_id -> {date: count}
        self.daily_dm_counts: Dict[str, Dict[str, int]] = defaultdict(dict)
        
        # Track last DM send time per account (for cooldown)
        # Format: account_id -> last_send_timestamp
        self.last_dm_send: Dict[str, float] = {}
        
        # Track failed attempts for retry logic
        # Format: account_id -> {comment_id: (attempt_count, last_attempt_time)}
        self.failed_attempts: Dict[str, Dict[str, tuple]] = defaultdict(dict)
        
        # Default safety limits (can be overridden in config)
        self.default_cooldown_seconds = 5  # Minimum seconds between DMs
        self.default_daily_limit = 50  # Maximum DMs per day per account
        self.max_retry_attempts = 3  # Maximum retry attempts per comment
    
    def _is_automation_enabled(self, account_id: str) -> bool:
        """Check if comment-to-DM automation is enabled for account"""
        account = self.account_service.get_account(account_id)
        
        if hasattr(account, 'comment_to_dm') and account.comment_to_dm:
            return account.comment_to_dm.enabled
        
        return False
    
    def _get_dm_config(self, account_id: str) -> Optional[Dict[str, Any]]:
        """Get DM configuration for account"""
        account = self.account_service.get_account(account_id)
        
        if hasattr(account, 'comment_to_dm') and account.comment_to_dm:
            config = account.comment_to_dm
            return {
                "enabled": config.enabled if hasattr(config, 'enabled') else False,
                "trigger_keyword": getattr(config, 'trigger_keyword', None) or "AUTO",
                "dm_message_template": getattr(config, 'dm_message_template', None),
                "link_to_send": getattr(config, 'link_to_send', None),
                "daily_dm_limit": getattr(config, 'daily_dm_limit', None) or self.default_daily_limit,
                "cooldown_seconds": getattr(config, 'cooldown_seconds', None) or self.default_cooldown_seconds,
            }
        
        return None
    
    def _should_trigger(self, comment_text: str, trigger_keyword: str) -> bool:
        """
        Determine if comment should trigger DM based on trigger logic.
        
        Args:
            comment_text: The comment text
            trigger_keyword: Trigger keyword or "AUTO" or empty for any comment
            
        Returns:
            True if should trigger, False otherwise
        """
        # If empty or "AUTO", trigger on any comment
        if not trigger_keyword or trigger_keyword.strip().upper() == "AUTO":
            return True
        
        # Keyword mode: trigger only if keyword is present (case-insensitive)
        comment_lower = comment_text.strip().lower()
        keyword_lower = trigger_keyword.strip().lower()
        
        return keyword_lower in comment_lower
    
    def _is_public_link(self, link: Optional[str]) -> bool:
        """Return True if link is a public HTTP/HTTPS URL that can be sent in a DM."""
        if not link or not isinstance(link, str):
            return False
        s = link.strip().lower()
        return s.startswith("http://") or s.startswith("https://")

    def _generate_dm_message(
        self,
        template: Optional[str],
        link: Optional[str],
        comment_username: Optional[str] = None,
        post_caption: Optional[str] = None,
    ) -> str:
        """
        Generate DM message from template with personalization.
        
        Args:
            template: Message template (supports {username}, {link}, {post} placeholders)
            link: Link to include (PDF, checkout, etc.) – only public HTTP/HTTPS URLs are included
            comment_username: Username of commenter for personalization
            post_caption: Post caption for context
            
        Returns:
            Formatted DM message
        """
        # file:// and non-public URLs cannot be sent in DMs; use placeholder so user knows to message for file
        link_for_message = link
        if link and not self._is_public_link(link):
            link_for_message = None
            if link.strip().lower().startswith("file://"):
                logger.warning(
                    "Link is file:// – cannot send in DM. Configure a public URL (e.g. cloud storage) in Settings → Comment-to-DM → Link to send.",
                    link_preview=link[:60] + "..." if len(link) > 60 else link,
                )
        
        if template:
            message = template
            
            # Replace {username} with commenter username
            if comment_username:
                message = message.replace("{username}", comment_username)
                message = message.replace("{@username}", f"@{comment_username}")
            
            # Replace {link} with actual link (only if public URL)
            if link_for_message:
                message = message.replace("{link}", link_for_message)
            elif "{link}" in message:
                message = message.replace(
                    "{link}",
                    "Message us to receive the file (configure a public URL in Settings for automatic link).",
                )
            
            # Replace {post} with post caption (truncated)
            if post_caption:
                post_preview = post_caption[:50] + "..." if len(post_caption) > 50 else post_caption
                message = message.replace("{post}", post_preview)
            
            return message.strip()
        
        # Default template if none provided
        if link_for_message:
            if comment_username:
                return f"Hey @{comment_username} 👋 Thanks for commenting! Here's the link you requested: {link_for_message}"
            else:
                return f"Hey 👋 Thanks for commenting! Here's the link you requested: {link_for_message}"
        else:
            if comment_username:
                return f"Hey @{comment_username} 👋 Thanks for commenting! Message us to get the link."
            else:
                return "Hey 👋 Thanks for commenting! Message us to get the link."
    
    def _check_safety_limits(self, account_id: str, config: Dict[str, Any]) -> tuple:
        """
        Check if DM can be sent based on safety limits.
        
        Args:
            account_id: Account identifier
            config: DM configuration with limits
            
        Returns:
            (can_send, reason_if_blocked)
        """
        cooldown_seconds = config.get("cooldown_seconds", self.default_cooldown_seconds)
        daily_limit = config.get("daily_dm_limit", self.default_daily_limit)
        
        # Check cooldown between DMs
        if account_id in self.last_dm_send:
            time_since_last = time.time() - self.last_dm_send[account_id]
            if time_since_last < cooldown_seconds:
                wait_time = cooldown_seconds - time_since_last
                return False, f"cooldown_active_{wait_time:.1f}s"
        
        # Check daily limit
        today = datetime.utcnow().date().isoformat()
        daily_count = self.daily_dm_counts[account_id].get(today, 0)
        
        if daily_count >= daily_limit:
            return False, f"daily_limit_reached_{daily_count}/{daily_limit}"
        
        return True, None
    
    def _is_user_already_dm_today(self, account_id: str, user_id: str, media_id: str) -> bool:
        """
        Check if we've already sent DM to this user for this post today.
        
        Args:
            account_id: Account identifier
            user_id: User identifier (username)
            media_id: Media/post ID
            date: Date string (YYYY-MM-DD)
            
        Returns:
            True if already sent today, False otherwise
        """
        today = datetime.utcnow().date().isoformat()
        key = (user_id, media_id, today)
        return key in self.users_dm_today[account_id]
    
    def _record_user_dm_today(self, account_id: str, user_id: str, media_id: str):
        """Record that we sent DM to this user for this post today"""
        today = datetime.utcnow().date().isoformat()
        key = (user_id, media_id, today)
        self.users_dm_today[account_id].add(key)
        
        # Clean old entries (keep last 7 days)
        cutoff_date = (datetime.utcnow() - timedelta(days=7)).date().isoformat()
        self.users_dm_today[account_id] = {
            k for k in self.users_dm_today[account_id]
            if k[2] >= cutoff_date  # k[2] is the date string
        }
    
    def _record_dm_sent(self, account_id: str):
        """Record that a DM was sent (for tracking and limits)"""
        self.last_dm_send[account_id] = time.time()
        
        today = datetime.utcnow().date().isoformat()
        if today not in self.daily_dm_counts[account_id]:
            self.daily_dm_counts[account_id][today] = 0
        self.daily_dm_counts[account_id][today] += 1
        
        # Clean old daily counts (keep last 7 days)
        cutoff_date = (datetime.utcnow() - timedelta(days=7)).date().isoformat()
        self.daily_dm_counts[account_id] = {
            k: v for k, v in self.daily_dm_counts[account_id].items()
            if k >= cutoff_date
        }
    
    def _should_retry(self, account_id: str, comment_id: str) -> bool:
        """Check if we should retry sending DM for this comment"""
        if comment_id not in self.failed_attempts[account_id]:
            return True
        
        attempt_count, last_attempt_time = self.failed_attempts[account_id][comment_id]
        
        # Don't retry if max attempts reached
        if attempt_count >= self.max_retry_attempts:
            return False
        
        # Exponential backoff: wait 2^attempt_count seconds
        wait_time = 2 ** attempt_count
        time_since_last = time.time() - last_attempt_time
        
        if time_since_last < wait_time:
            return False  # Still in backoff period
        
        return True
    
    def _record_failed_attempt(self, account_id: str, comment_id: str):
        """Record a failed attempt for retry logic"""
        if comment_id not in self.failed_attempts[account_id]:
            self.failed_attempts[account_id][comment_id] = (0, time.time())
        
        attempt_count, _ = self.failed_attempts[account_id][comment_id]
        self.failed_attempts[account_id][comment_id] = (attempt_count + 1, time.time())
    
    def _record_successful_comment(self, account_id: str, comment_id: str, media_id: str):
        """Record successful processing of a comment (update last processed ID)"""
        if media_id not in self.last_processed_comment_id[account_id]:
            self.last_processed_comment_id[account_id][media_id] = comment_id
        else:
            # Update only if this comment ID is newer (for timestamp-based ordering)
            current_last = self.last_processed_comment_id[account_id][media_id]
            if comment_id > current_last:  # Simple comparison (works for sequential IDs)
                self.last_processed_comment_id[account_id][media_id] = comment_id
        
        # Remove from failed attempts if present
        if comment_id in self.failed_attempts[account_id]:
            del self.failed_attempts[account_id][comment_id]

    def _reply_to_comment_with_link_fallback(
        self,
        client: Any,
        account_id: str,
        comment_id: str,
        link_to_send: Optional[str],
        comment_username: Optional[str],
        dm_message: Optional[str] = None,
    ) -> bool:
        """
        When DM fails due to 24h window (code 10), reply to the comment so the user
        still receives a response. Uses dm_message (AI or template) when provided;
        otherwise uses link-based fallback text.
        """
        msg = (dm_message or "").strip()
        if not msg:
            link = (link_to_send or "").strip()
            is_public_url = link and (link.startswith("http://") or link.startswith("https://"))
            # Mention user with @username so they get notified and see the link
            mention = f"@{comment_username}" if comment_username else "there"
            if is_public_url:
                msg = f"Hey {mention}! 👋 Instagram doesn't allow DMs unless you've messaged us first. Here's your link: {link}"
            else:
                msg = f"Hey {mention}! 👋 Message us first (DM) so we can send you the link – Instagram restricts automated DMs."
        try:
            # Instagram Graph API: POST replies with message in request body (data)
            client._make_request("POST", f"{comment_id}/replies", data={"message": msg})
            logger.info(
                "Fallback reply posted (DM blocked by 24h window)",
                account_id=account_id,
                comment_id=comment_id,
                used_dm_message=bool(dm_message and dm_message.strip()),
            )
            return True
        except Exception as e:
            logger.warning(
                "Fallback reply failed",
                account_id=account_id,
                comment_id=comment_id,
                error=str(e),
            )
            return False
    
    def _reply_to_comment_with_ai(
        self,
        client: Any,
        account_id: str,
        comment_id: str,
        comment_username: str,
        ai_message: Optional[str] = None,
        comment_text: str = "",
        post_context: str = "",
        account_username: str = "we",
        link: Optional[str] = None,
    ) -> bool:
        """
        Reply to a comment with AI-generated text, mentioning the user.
        Called after successful DM to also engage in the comment thread.
        
        Args:
            client: Instagram client instance
            account_id: Account identifier
            comment_id: Comment ID to reply to
            comment_username: Username to mention in reply
            ai_message: Pre-generated AI message (if available, will use this)
            comment_text: Original comment text (for AI generation if needed)
            post_context: Post caption/context (for AI generation if needed)
            account_username: Account username replying
            link: Optional link to include
            
        Returns:
            True if reply was posted successfully, False otherwise
        """
        try:
            # Use provided AI message, or generate a new one
            if ai_message and ai_message.strip() and ai_message.strip() != FALLBACK_REPLY:
                reply_text = ai_message.strip()
            else:
                # Generate AI reply specifically for comment (shorter, more casual)
                reply_text = self.ai_reply_service.generate_reply(
                    user_message=comment_text or "",
                    post_context=post_context or "",
                    account_username=account_username,
                    link=link,
                )
                if not reply_text or reply_text.strip() == FALLBACK_REPLY:
                    # If AI fails, use a simple friendly message
                    reply_text = "Thanks for your comment! Check your DMs for more details. 💙"
            
            # Format: @username {ai_text}
            # Only add mention if username is available and not already in the text
            if comment_username and f"@{comment_username}" not in reply_text:
                formatted_reply = f"@{comment_username} {reply_text}"
            else:
                formatted_reply = reply_text
            
            # Reply to comment using POST with data (not params) - Instagram API requirement
            try:
                result = client._make_request(
                    "POST",
                    f"{comment_id}/replies",
                    data={"message": formatted_reply},  # Use data, not params
                )
                
                logger.info(
                    "Comment reply posted with AI text",
                    account_id=account_id,
                    comment_id=comment_id,
                    mentioned_user=comment_username,
                    reply_preview=formatted_reply[:100],
                    reply_id=result.get("id") if isinstance(result, dict) else None,
                )
                return True
            except Exception as reply_err:
                logger.error(
                    "Failed to post AI comment reply - API call failed",
                    account_id=account_id,
                    comment_id=comment_id,
                    error=str(reply_err),
                    error_type=type(reply_err).__name__,
                    reply_text=formatted_reply[:100],
                )
                raise
        except Exception as e:
            logger.exception(
                "Failed to post AI comment reply",
                account_id=account_id,
                comment_id=comment_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            return False
    
    def process_new_comments_for_dm(
        self,
        account_id: str,
        media_id: str,
        comments: List[Dict[str, Any]],
        post_caption: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Process new comments for a post and send DMs.
        
        This is the main entry point called by CommentMonitor.
        Tracks last processed comment ID per post to avoid duplicates.
        
        Args:
            account_id: Account identifier
            media_id: Instagram media ID
            comments: List of comment dictionaries from API
            post_caption: Optional post caption
            
        Returns:
            Processing results summary
        """
        results = {
            "processed": 0,
            "sent": 0,
            "skipped": 0,
            "failed": 0,
            "new_comments": 0,
            "fallback_replied": 0,  # Comments that got fallback reply (DM blocked by 24h window)
        }
        
        # Check if we should process: account-level enabled OR post has a specific link
        account_enabled = self._is_automation_enabled(account_id)
        post_config = self.post_dm_config.get_post_dm_config(account_id, media_id)
        has_post_link = post_config and post_config.get("file_url")
        if not account_enabled and not has_post_link:
            logger.debug(
                "Comment-to-DM skipped: automation disabled and no post-specific link",
                account_id=account_id,
                media_id=media_id,
            )
            return results

        # Get last processed comment ID for this post
        last_processed_id = self.last_processed_comment_id[account_id].get(media_id)
        
        # Filter to only new comments (those after last processed)
        new_comments = []
        if last_processed_id:
            # Process comments that come after the last processed one
            # Note: Comments are typically returned in reverse chronological order (newest first)
            for comment in comments:
                comment_id = comment.get("id")
                # Stop if we reach the last processed comment
                if comment_id == last_processed_id:
                    break
                new_comments.append(comment)
        else:
            # First time processing this post - process all comments
            new_comments = comments
        
        results["new_comments"] = len(new_comments)
        
        logger.info(
            "Processing comments for auto-DM",
            account_id=account_id,
            media_id=media_id,
            total_comments=len(comments),
            new_comments=len(new_comments),
            last_processed_id=last_processed_id,
        )
        
        # Process each new comment
        for comment in new_comments:
            comment_id = comment.get("id")
            
            # Quick check: skip if already processed (persistent tracking prevents duplicates)
            if comment_id and self.dm_tracking.is_comment_processed(account_id, comment_id):
                logger.debug(
                    "Skipping already processed comment (persistent tracking)",
                    account_id=account_id,
                    comment_id=comment_id,
                    media_id=media_id,
                )
                results["skipped"] += 1
                continue
            
            result = self.process_comment_for_dm(
                account_id=account_id,
                comment=comment,
                media_id=media_id,
                media_caption=post_caption,
            )
            
            results["processed"] += 1
            
            if result["status"] == "success":
                results["sent"] += 1
                # Record successful processing
                self._record_successful_comment(account_id, comment.get("id"), media_id)
            elif result["status"] == "failed":
                results["failed"] += 1
            elif result.get("reason") == "instagram_24h_messaging_window":
                # Fallback reply was sent
                results["fallback_replied"] += 1
                results["skipped"] += 1  # Also count as skipped for backward compatibility
            elif result.get("reason") == "already_processed":
                # Already processed (from persistent tracking check inside process_comment_for_dm)
                results["skipped"] += 1
            else:
                results["skipped"] += 1
        
        return results
    
    def process_comment_for_dm(
        self,
        account_id: str,
        comment: Dict[str, Any],
        media_id: str,
        media_caption: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Process a single comment and send DM if conditions are met.
        
        This method handles:
        - Trigger keyword evaluation
        - Duplicate checking (one DM per user per post per day)
        - Safety limits (daily limits, cooldowns)
        - Retry logic for failures
        - Comprehensive logging
        
        Args:
            account_id: Account identifier
            comment: Comment dictionary with id, text, username, etc.
            media_id: Instagram media ID where comment was made
            media_caption: Optional post caption for context
            
        Returns:
            Result dictionary with status, reason, and details
        """
        comment_id = comment.get("id")
        comment_text = comment.get("text", "")
        from_obj = comment.get("from")
        if isinstance(from_obj, dict):
            comment_username = comment.get("username") or from_obj.get("username")
            commenter_ig_id = from_obj.get("id")
        else:
            comment_username = comment.get("username")
            commenter_ig_id = None
        user_id = comment_username or commenter_ig_id or comment_id or "unknown"
        
        result = {
            "status": "skipped",
            "reason": None,
            "comment_id": comment_id,
            "user_id": user_id,
            "media_id": media_id,
            "trigger_type": None,
        }
        
        logger.info(
            "Comment received",
            account_id=account_id,
            comment_id=comment_id,
            user_id=user_id,
            media_id=media_id,
            comment_text_preview=comment_text[:50] if comment_text else "",
        )
        
        # CRITICAL: Check if this comment was already processed (DM sent or fallback replied)
        # This prevents duplicate DMs even across app restarts
        if self.dm_tracking.is_comment_processed(account_id, comment_id):
            result["reason"] = "already_processed"
            logger.warning(
                "Comment already processed - skipping to prevent duplicate DM",
                account_id=account_id,
                comment_id=comment_id,
                media_id=media_id,
                user_id=user_id,
            )
            return result
        
        # Get post-specific configuration FIRST (post-specific overrides account defaults)
        post_config = self.post_dm_config.get_post_dm_config(account_id, media_id)
        
        # Get DM configuration (account-level defaults)
        dm_config = self._get_dm_config(account_id)
        
        # Check if automation should run:
        # 1. If post has specific config with a link, allow it (even if account-level is disabled)
        # 2. Otherwise, require account-level to be enabled
        has_post_specific_link = post_config and post_config.get("file_url")
        account_enabled = dm_config and dm_config.get("enabled")
        
        if not has_post_specific_link and not account_enabled:
            result["reason"] = "automation_disabled"
            logger.debug(
                "Automation disabled - no post-specific config and account-level disabled",
                account_id=account_id,
                comment_id=comment_id,
                has_post_config=post_config is not None,
            )
            return result
        
        logger.info(
            "Post DM config lookup",
            account_id=account_id,
            media_id=media_id,
            has_post_config=post_config is not None,
            post_file_url=post_config.get("file_url")[:50] + "..." if post_config and post_config.get("file_url") else None,
            post_trigger_mode=post_config.get("trigger_mode") if post_config else None,
            post_trigger_word=post_config.get("trigger_word") if post_config else None,
            ai_enabled=post_config.get("ai_enabled", False) if post_config else False,
            account_enabled=account_enabled,
        )
        
        # Determine link to send (Post specific > Account global)
        link_to_send = None
        if post_config and post_config.get("file_url"):
            link_to_send = post_config.get("file_url")
            logger.info(
                "Using post-specific link",
                account_id=account_id,
                media_id=media_id,
                link=link_to_send[:50] if link_to_send else None,
            )
        elif dm_config:
            link_to_send = dm_config.get("link_to_send")
            logger.info(
                "Using account-global link",
                account_id=account_id,
                media_id=media_id,
                has_link=link_to_send is not None,
            )
        
        # If no link is available, skip (or send message without link – see below)
        if not link_to_send:
            result["reason"] = "no_link_configured"
            logger.info(
                "Comment-to-DM skipped: no link configured. Set link_to_send in Settings → Comment-to-DM (or per-post link) to send links via DM.",
                account_id=account_id,
                media_id=media_id,
                has_post_config=post_config is not None,
            )
            return result
        
        # If link is file://, we still send a DM but message will not contain the raw path (handled in _generate_dm_message)
        if link_to_send.strip().lower().startswith("file://"):
            logger.info(
                "Link is file:// – DM will ask user to message for file. For automatic link, use a public URL in link_to_send.",
                account_id=account_id,
                media_id=media_id,
            )
        
        # Determine trigger logic (Post specific > Account global)
        trigger_keyword = "AUTO"
        
        if post_config and post_config.get("trigger_mode"):
            # Use post-specific trigger settings
            mode = post_config.get("trigger_mode")
            if mode == "KEYWORD":
                trigger_keyword = post_config.get("trigger_word", "") or ""
            else:
                trigger_keyword = "AUTO"
            
            logger.info(
                "Using post-specific trigger config", 
                account_id=account_id, 
                media_id=media_id,
                mode=mode, 
                keyword=trigger_keyword
            )
        elif dm_config:
            # Fallback to account global settings
            trigger_keyword = dm_config.get("trigger_keyword", "AUTO")
            logger.info(
                "Using account-global trigger config",
                account_id=account_id,
                media_id=media_id,
                keyword=trigger_keyword
            )
        
        if not self._should_trigger(comment_text, trigger_keyword):
            result["reason"] = "trigger_keyword_not_matched"
            result["trigger_type"] = "keyword_skipped"
            logger.debug(
                "Trigger decision: keyword not matched",
                account_id=account_id,
                comment_id=comment_id,
                trigger_keyword=trigger_keyword,
                comment_text=comment_text[:50],
            )
            return result
        
        # Determine trigger type
        if trigger_keyword.upper() == "AUTO" or not trigger_keyword:
            result["trigger_type"] = "auto"
        else:
            result["trigger_type"] = "keyword"
        
        logger.info(
            "Trigger decision: comment matches",
            account_id=account_id,
            comment_id=comment_id,
            trigger_type=result["trigger_type"],
            trigger_keyword=trigger_keyword,
        )
        
        # DM requires commenter username or IGSID. Skip if neither available.
        if not comment_username and not commenter_ig_id:
            result["reason"] = "comment_author_identity_unavailable"
            logger.warning(
                "DM skipped: comment author username/from.id not returned by API (Instagram Login API may omit these)",
                account_id=account_id,
                comment_id=comment_id,
                media_id=media_id,
            )
            return result
        
        # Check if already sent DM to this user for this post today
        if self._is_user_already_dm_today(account_id, user_id, media_id):
            result["reason"] = "already_dm_today"
            logger.debug(
                "DM skipped: already sent to user today",
                account_id=account_id,
                comment_id=comment_id,
                user_id=user_id,
                media_id=media_id,
            )
            return result
        
        # Check safety limits (dm_config may be None if account has no comment_to_dm in config)
        can_send, limit_reason = self._check_safety_limits(account_id, dm_config or {})
        if not can_send:
            result["reason"] = limit_reason
            logger.warning(
                "DM skipped: safety limit",
                account_id=account_id,
                comment_id=comment_id,
                user_id=user_id,
                reason=limit_reason,
            )
            return result
        
        # Check retry logic
        if not self._should_retry(account_id, comment_id):
            result["reason"] = "max_retries_exceeded"
            # Mark as processed to prevent future attempts
            self.dm_tracking.mark_comment_processed(account_id, comment_id)
            logger.warning(
                "DM skipped: max retries exceeded - marking as processed",
                account_id=account_id,
                comment_id=comment_id,
                user_id=user_id,
            )
            return result
        
        # Get client and send DM
        client = self.account_service.get_client(account_id)

        # Get account username (needed for AI replies and comment mentions)
        acc = self.account_service.get_account(account_id)
        account_username = (acc.username if acc else None) or "we"

        # Generate DM message: use AI when ai_enabled, else template/default
        ai_enabled = post_config.get("ai_enabled", False) if post_config else False
        ai_message = None
        if ai_enabled:
            ai_message = self.ai_reply_service.generate_reply(
                user_message=comment_text or "",
                post_context=media_caption or "",
                account_username=account_username,
                link=link_to_send,
            )
            if ai_message and ai_message.strip() != FALLBACK_REPLY:
                dm_message = ai_message.strip()
            else:
                dm_message = self._generate_dm_message(
                    template=(dm_config or {}).get("dm_message_template"),
                    link=link_to_send,
                    comment_username=comment_username,
                    post_caption=media_caption,
                )
        else:
            dm_message = self._generate_dm_message(
                template=(dm_config or {}).get("dm_message_template"),
                link=link_to_send,
                comment_username=comment_username,
                post_caption=media_caption,
            )

        logger.info(
            "Sending DM",
            account_id=account_id,
            comment_id=comment_id,
            user_id=user_id,
            media_id=media_id,
            trigger_type=result["trigger_type"],
            message_preview=dm_message[:50],
            ai_used=ai_enabled,
        )
        
        # Send DM with retry logic
        try:
            dm_result = client.send_direct_message(
                recipient_username=comment_username or "",
                message=dm_message,
                recipient_id=commenter_ig_id,
            )
            
            if dm_result.get("status") == "success":
                # Success! Mark as processed IMMEDIATELY to prevent duplicates
                self.dm_tracking.mark_comment_processed(account_id, comment_id)
                self._record_dm_sent(account_id)
                self._record_user_dm_today(account_id, user_id, media_id)
                
                result["status"] = "success"
                result["reason"] = None
                result["dm_id"] = dm_result.get("dm_id")
                
                logger.info(
                    "DM sent successfully",
                    account_id=account_id,
                    comment_id=comment_id,
                    user_id=user_id,
                    media_id=media_id,
                    dm_id=result.get("dm_id"),
                    trigger_type=result["trigger_type"],
                )
                
                # After successful DM, also reply to the comment with AI-generated text (mentioning the user)
                if ai_enabled and comment_username:
                    # Pass dm_message if it's AI-generated (when ai_message was used), otherwise None to generate new
                    ai_msg_for_comment = dm_message if (ai_message and ai_message.strip() != FALLBACK_REPLY and dm_message == ai_message.strip()) else None
                    self._reply_to_comment_with_ai(
                        client=client,
                        account_id=account_id,
                        comment_id=comment_id,
                        comment_username=comment_username,
                        ai_message=ai_msg_for_comment,
                        comment_text=comment_text or "",
                        post_context=media_caption or "",
                        account_username=account_username,
                        link=link_to_send,
                    )
            elif dm_result.get("error_code") == 10:
                # Instagram 24h window: user must message you first. Commenting does NOT open DMs.
                # Fallback: reply to comment with dm_message (AI/template) or link-based text.
                fallback_success = self._reply_to_comment_with_link_fallback(
                    client, account_id, comment_id, link_to_send, comment_username, dm_message=dm_message
                )
                # Mark as processed IMMEDIATELY (even if fallback failed) to prevent duplicate attempts
                self.dm_tracking.mark_comment_processed(account_id, comment_id)
                result["status"] = "skipped"
                result["reason"] = "instagram_24h_messaging_window"
                # Mark as processed so we don't retry or duplicate
                self._record_successful_comment(account_id, comment_id, media_id)
                
                logger.warning(
                    "DM skipped: Instagram 24-hour messaging window. User must message you first; "
                    "commenting on a post does not open DMs. Fallback reply sent.",
                    account_id=account_id,
                    comment_id=comment_id,
                    user_id=user_id,
                    media_id=media_id,
                    fallback_sent=fallback_success,
                )
            else:
                # Failed - record for retry, but don't mark as processed yet
                # (allow retry, but persistent tracking will prevent duplicates if app restarts)
                result["status"] = "failed"
                result["reason"] = dm_result.get("error", "unknown_error")
                self._record_failed_attempt(account_id, comment_id)
                
                logger.error(
                    "DM failed - will retry if within limits",
                    account_id=account_id,
                    comment_id=comment_id,
                    user_id=user_id,
                    error=result["reason"],
                )
        
        except Exception as e:
            # Exception - record for retry, but don't mark as processed yet
            result["status"] = "failed"
            result["reason"] = str(e)
            self._record_failed_attempt(account_id, comment_id)
            
            logger.error(
                "Exception while sending DM - will retry if within limits",
                account_id=account_id,
                comment_id=comment_id,
                user_id=user_id,
                error=str(e),
                exc_info=True,
            )
        
        return result
    
    def get_status(self, account_id: str) -> Dict[str, Any]:
        """Get current status and statistics for an account"""
        today = datetime.utcnow().date().isoformat()
        daily_count = self.daily_dm_counts[account_id].get(today, 0)
        
        config = self._get_dm_config(account_id)
        daily_limit = config.get("daily_dm_limit", self.default_daily_limit) if config else self.default_daily_limit
        
        return {
            "automation_enabled": self._is_automation_enabled(account_id),
            "config": config,
            "daily_dm_count": daily_count,
            "daily_limit": daily_limit,
            "users_dm_today_count": len([k for k in self.users_dm_today[account_id] if k[2] == today]),
            "cooldown_seconds": config.get("cooldown_seconds", self.default_cooldown_seconds) if config else self.default_cooldown_seconds,
            "monitored_posts": len(self.last_processed_comment_id[account_id]),
        }
    
    def update_config(self, account_id: str, **kwargs) -> Dict[str, Any]:
        """Update configuration for an account (via API)"""
        # This would update the config in accounts.yaml
        # Implementation depends on your config management
        return {"status": "updated", "account_id": account_id}
