"""Comment automation service - Auto-reply to comments"""

import time
import random
from typing import Dict, List, Optional, Any
from datetime import datetime

from ...services.account_service import AccountService
from ...utils.logger import get_logger
from ...utils.exceptions import InstagramAPIError
from .post_dm_config import PostDMConfig

logger = get_logger(__name__)


class CommentService:
    """
    Service for automated comment management.
    
    Features:
    - Auto-reply to comments
    - Comment monitoring
    - Template-based replies (random rotation)
    - Post-specific links in replies
    """
    
    def __init__(
        self,
        account_service: AccountService,
        auto_reply_enabled: bool = True,
        reply_templates: Optional[List[str]] = None,
        reply_delay_seconds: int = 30,
        post_dm_config: Optional[PostDMConfig] = None,
    ):
        self.account_service = account_service
        self.auto_reply_enabled = auto_reply_enabled
        self.reply_templates = reply_templates or [
            "Thanks for your comment! 🙏",
            "Appreciate it! ❤️",
            "Thanks! 👍",
        ]
        self.reply_delay_seconds = reply_delay_seconds
        self.processed_comments: Dict[str, List[str]] = {}  # account_id -> [comment_ids]
        self.post_dm_config = post_dm_config or PostDMConfig()  # Access to post-specific links
    
    def get_comments(self, account_id: str, media_id: str) -> List[Dict[str, Any]]:
        """
        Get comments on a media post
        
        Args:
            account_id: Account identifier
            media_id: Instagram media ID
            
        Returns:
            List of comments
        """
        client = self.account_service.get_client(account_id)
        
        try:
            # First, try to get media details to check comment count
            try:
                media_info = client._make_request(
                    "GET",
                    f"{media_id}",
                    params={
                        "fields": "id,caption,comments_count,like_count",
                    }
                )
                comments_count_from_media = media_info.get("comments_count", 0)
                logger.debug(
                    "Media info retrieved",
                    account_id=account_id,
                    media_id=media_id,
                    comments_count_from_media=comments_count_from_media,
                )
            except Exception as media_err:
                logger.debug(
                    "Could not get media info",
                    account_id=account_id,
                    media_id=media_id,
                    error=str(media_err),
                )
                comments_count_from_media = None
            
            # Get comments from media. Include from{id,username} for commenter identity (DM recipient).
            response = client._make_request(
                "GET",
                f"{media_id}/comments",
                params={
                    "fields": "id,text,username,timestamp,like_count,replies,from{id,username}",
                    "limit": 100,
                }
            )
            
            comments = response.get("data", [])
            
            # Normalize: Graph API may return username only under "from"; ensure every comment has username and from
            for c in comments:
                if not isinstance(c, dict):
                    continue
                from_obj = c.get("from")
                if not isinstance(from_obj, dict):
                    from_obj = {}
                # Top-level "username" is deprecated; ensure we have username from from
                if not c.get("username") and from_obj.get("username"):
                    c["username"] = from_obj.get("username")
                # Ensure "from" exists for DM recipient (id + username)
                if not c.get("from") or not isinstance(c.get("from"), dict):
                    c["from"] = {"id": from_obj.get("id"), "username": from_obj.get("username") or c.get("username")}
            
            if comments_count_from_media is not None and comments_count_from_media > 0 and len(comments) == 0:
                logger.warning(
                    "API returned 0 comments but media shows comments exist",
                    account_id=account_id,
                    media_id=media_id,
                    comments_count_from_media=comments_count_from_media,
                    note="Add instagram_manage_comments (or instagram_business_manage_comments) in Meta App permissions.",
                )
            
            return comments
            
        except Exception as e:
            error_code = getattr(e, 'error_code', None)
            logger.error(
                "Failed to get comments",
                account_id=account_id,
                media_id=media_id,
                error=str(e),
                error_code=error_code,
            )
            return []
    
    def reply_to_comment(
        self,
        account_id: str,
        comment_id: str,
        reply_text: str,
        media_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Reply to a comment
        
        Args:
            account_id: Account identifier
            comment_id: Comment ID to reply to
            reply_text: Reply text
            media_id: Optional media ID for logging/verification
            
        Returns:
            Reply result
        """
        if not self.auto_reply_enabled:
            logger.debug("Auto-reply disabled, skipping", comment_id=comment_id, media_id=media_id)
            return {"status": "skipped", "reason": "auto_reply_disabled"}
        
        client = self.account_service.get_client(account_id)
        
        try:
            # Reply to comment; Instagram API expects message in data (not params)
            result = client._make_request(
                "POST",
                f"{comment_id}/replies",
                data={"message": reply_text},  # Use data, not params
            )
            
            logger.info(
                "Comment reply posted",
                account_id=account_id,
                comment_id=comment_id,
                media_id=media_id,
                reply_length=len(reply_text),
                reply_preview=reply_text[:50],
                reply_id=result.get("id") if isinstance(result, dict) else None,
            )
            
            # Track processed comment
            if account_id not in self.processed_comments:
                self.processed_comments[account_id] = []
            if comment_id not in self.processed_comments[account_id]:
                self.processed_comments[account_id].append(comment_id)
            
            return {
                "status": "success",
                "reply_id": result.get("id"),
                "comment_id": comment_id,
            }
            
        except InstagramAPIError as e:
            logger.error(
                "Failed to reply to comment",
                account_id=account_id,
                comment_id=comment_id,
                error=str(e),
                error_code=getattr(e, 'error_code', None),
            )
            return {
                "status": "failed",
                "error": str(e),
                "comment_id": comment_id,
            }
    
    def generate_reply(
        self,
        comment_text: str,
        comment_username: Optional[str] = None,
        account_id: Optional[str] = None,
        media_id: Optional[str] = None,
    ) -> str:
        """
        Generate a reply based on comment content, including post-specific link if available.
        
        Args:
            comment_text: Original comment text
            comment_username: Username of commenter (optional)
            account_id: Account identifier (for post-specific link lookup)
            media_id: Instagram media ID (for post-specific link lookup)
            
        Returns:
            Reply text with "thank u" and link if available
        """
        # Get post-specific link if available
        link_to_include = None
        if account_id and media_id:
            post_config = self.post_dm_config.get_post_dm_config(account_id, media_id)
            logger.debug(
                "Auto-reply: checking post-specific link",
                account_id=account_id,
                media_id=media_id,
                has_post_config=post_config is not None,
            )
            if post_config and post_config.get("file_url"):
                link = post_config.get("file_url", "").strip()
                # Only include if it's a public URL (not file://)
                if link and (link.startswith("http://") or link.startswith("https://")):
                    link_to_include = link
                    logger.debug(
                        "Auto-reply: including post-specific link",
                        account_id=account_id,
                        media_id=media_id,
                        link_preview=link[:50],
                    )
        
        # Build reply: "thank u" + link if available
        if link_to_include:
            if comment_username:
                return f"Thank u @{comment_username}! 🙏 Here's your link: {link_to_include}"
            else:
                return f"Thank u! 🙏 Here's your link: {link_to_include}"
        else:
            # No link for this post, use template or simple "thank u"
            if comment_username:
                return f"Thank u @{comment_username}! 🙏"
            else:
                return "Thank u! 🙏"
    
    def process_new_comments(
        self,
        account_id: str,
        media_id: str,
    ) -> Dict[str, Any]:
        """
        Process new comments on a post and auto-reply
        
        Args:
            account_id: Account identifier
            media_id: Instagram media ID
            
        Returns:
            Processing results
        """
        results = {
            "processed": 0,
            "replied": 0,
            "skipped": 0,
            "failed": 0,
        }
        
        if not self.auto_reply_enabled:
            return results
        
        # Get comments
        comments = self.get_comments(account_id, media_id)
        
        # Track processed comments for this account
        if account_id not in self.processed_comments:
            self.processed_comments[account_id] = []
        
        processed_in_batch = 0
        
        for comment in comments:
            comment_id = comment.get("id")
            comment_text = comment.get("text", "")
            comment_username = comment.get("username", "")
            
            # Skip if already processed
            if comment_id in self.processed_comments[account_id]:
                results["skipped"] += 1
                continue
            
            # Skip if it's our own comment
            account = self.account_service.get_account(account_id)
            if comment_username.lower() == account.username.lower():
                results["skipped"] += 1
                continue
            
            results["processed"] += 1
            
            # Generate and send reply (include post-specific link)
            reply_text = self.generate_reply(
                comment_text,
                comment_username,
                account_id=account_id,
                media_id=media_id,
            )
            
            # Add delay between replies
            if processed_in_batch > 0:
                time.sleep(self.reply_delay_seconds)
                
            reply_result = self.reply_to_comment(account_id, comment_id, reply_text, media_id=media_id)
            
            if reply_result.get("status") == "success":
                results["replied"] += 1
                processed_in_batch += 1
            else:
                results["failed"] += 1
        
        logger.info(
            "Processed comments",
            account_id=account_id,
            media_id=media_id,
            **results,
        )
        
        return results
