"""Comment automation service - Auto-reply to comments"""

import time
import random
from typing import Dict, List, Optional, Any
from datetime import datetime

from ...services.account_service import AccountService
from ...utils.logger import get_logger
from ...utils.exceptions import InstagramAPIError

logger = get_logger(__name__)


class CommentService:
    """
    Service for automated comment management.
    
    Features:
    - Auto-reply to comments
    - Comment monitoring
    - Template-based replies (random rotation)
    - Keyword-based routing (optional if dict provided)
    """
    
    def __init__(
        self,
        account_service: AccountService,
        auto_reply_enabled: bool = True,
        reply_templates: Optional[List[str]] = None,
        reply_delay_seconds: int = 30,
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
            
            if comments_count_from_media is not None and comments_count_from_media > 0 and len(comments) == 0:
                logger.warning(
                    "API returned 0 comments but media shows comments exist",
                    account_id=account_id,
                    media_id=media_id,
                    comments_count_from_media=comments_count_from_media,
                    note="This usually means missing 'instagram_manage_comments' permission.",
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
    ) -> Dict[str, Any]:
        """
        Reply to a comment
        
        Args:
            account_id: Account identifier
            comment_id: Comment ID to reply to
            reply_text: Reply text
            
        Returns:
            Reply result
        """
        if not self.auto_reply_enabled:
            logger.debug("Auto-reply disabled, skipping", comment_id=comment_id)
            return {"status": "skipped", "reason": "auto_reply_disabled"}
        
        client = self.account_service.get_client(account_id)
        
        try:
            # Reply to comment using Instagram Graph API
            result = client._make_request(
                "POST",
                f"{comment_id}/replies",
                data={"message": reply_text},
            )
            
            logger.info(
                "Comment reply posted",
                account_id=account_id,
                comment_id=comment_id,
                reply_length=len(reply_text),
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
    
    def generate_reply(self, comment_text: str, comment_username: Optional[str] = None) -> str:
        """
        Generate a reply based on comment content (Random rotation)
        
        Args:
            comment_text: Original comment text
            comment_username: Username of commenter (optional)
            
        Returns:
            Reply text
        """
        if not self.reply_templates:
            return "Thanks! 🙏"
            
        template = random.choice(self.reply_templates)
        
        # Personalize with username if available and template has placeholder or no mention
        # Simple logic: if username provided, maybe prepend/append?
        # For now, keep it simple.
        
        return template
    
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
            
            # Generate and send reply
            reply_text = self.generate_reply(comment_text, comment_username)
            
            # Add delay between replies
            if processed_in_batch > 0:
                time.sleep(self.reply_delay_seconds)
                
            reply_result = self.reply_to_comment(account_id, comment_id, reply_text)
            
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
