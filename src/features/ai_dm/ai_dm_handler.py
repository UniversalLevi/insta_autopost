"""AI DM Auto Reply Handler - Generate and send AI-powered replies to Instagram DMs"""

import os
import time
import random
from typing import Optional, Dict, Any
from datetime import datetime

from dotenv import load_dotenv
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from ...utils.logger import get_logger
from .ai_dm_tracking import AIDMTracking

load_dotenv()

logger = get_logger(__name__)

# Default timeout for OpenAI API calls (seconds)
DEFAULT_TIMEOUT = 15.0
# Fallback reply when API fails or is unavailable
FALLBACK_REPLY = "Sorry for the delay 😊 Please try again."
# Rate limit: max replies per user per day
MAX_REPLIES_PER_USER_PER_DAY = 10
# Delay range before replying (seconds)
REPLY_DELAY_MIN = 3
REPLY_DELAY_MAX = 6


class AIDMHandler:
    """
    Handler for AI-powered DM auto-reply feature.
    
    Features:
    - Generates natural, human-like replies using OpenAI
    - Rate limiting (max 10 replies per user per day)
    - Random delay (3-6 seconds) before replying
    - Comprehensive error handling with fallback
    - Persistent tracking to prevent spam
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
        model: str = "gpt-4o-mini",
    ):
        self._api_key = (api_key or os.getenv("OPENAI_API_KEY") or "").strip()
        self._timeout = max(1.0, float(timeout))
        self._model = model
        self._client = None
        self.tracking = AIDMTracking()
        
        if self._api_key:
            try:
                from openai import OpenAI, AuthenticationError
                
                self._client = OpenAI(api_key=self._api_key)
                self._AuthError = AuthenticationError
                logger.info(
                    "AI_DM_HANDLER",
                    action="initialized",
                    has_api_key=True,
                    model=self._model,
                )
            except Exception as e:
                logger.warning("OpenAI client init failed", error=str(e))
                self._AuthError = None
        else:
            logger.warning(
                "AI_DM_HANDLER",
                action="initialized",
                has_api_key=False,
                error="OPENAI_API_KEY not found in environment",
            )
    
    def is_available(self) -> bool:
        """Return True if the service is configured and ready"""
        return bool(self._api_key and self._client)
    
    def _sanitize_input(self, text: str) -> str:
        """
        Sanitize user input to prevent injection attacks.
        
        Args:
            text: Input text to sanitize
            
        Returns:
            Sanitized text
        """
        if not text or not isinstance(text, str):
            return ""
        
        # Remove null bytes and control characters (except newlines)
        sanitized = "".join(
            char for char in text
            if ord(char) >= 32 or char in "\n\r\t"
        )
        
        # Limit length to prevent abuse
        max_length = 2000
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length] + "..."
        
        return sanitized.strip()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
    )
    def get_ai_reply(
        self,
        message: str,
        account_id: str,
        user_id: str,
        account_username: Optional[str] = None,
    ) -> str:
        """
        Generate an AI-powered reply to an incoming DM.
        
        Args:
            message: The incoming DM text
            account_id: Account identifier
            user_id: User identifier (Instagram user ID or username)
            account_username: Optional account username for context
            
        Returns:
            AI-generated reply text, or fallback reply on error
        """
        # Sanitize input
        message = self._sanitize_input(message)
        
        if not message:
            logger.warning(
                "AI_DM_REPLY",
                action="skipped",
                reason="empty_message",
                account_id=account_id,
                user_id=user_id,
            )
            return FALLBACK_REPLY
        
        # Check rate limit
        if not self.tracking.can_send_reply(account_id, user_id, MAX_REPLIES_PER_USER_PER_DAY):
            logger.warning(
                "AI_DM_REPLY",
                action="rate_limited",
                account_id=account_id,
                user_id=user_id,
                count_today=self.tracking.get_user_reply_count_today(account_id, user_id),
                max_per_day=MAX_REPLIES_PER_USER_PER_DAY,
            )
            return FALLBACK_REPLY
        
        if not self.is_available():
            logger.warning(
                "AI_DM_REPLY",
                action="unavailable",
                reason="openai_not_configured",
                account_id=account_id,
                user_id=user_id,
            )
            return FALLBACK_REPLY
        
        logger.info(
            "AI_DM_REPLY",
            action="generating",
            account_id=account_id,
            user_id=user_id,
            message_preview=message[:100] + ("..." if len(message) > 100 else ""),
        )
        
        # System prompt (exactly as specified)
        system_prompt = """You are a friendly, professional Instagram DM assistant for InstaForge.

Rules:
- Sound human
- Be polite
- Be short and clear
- Never say you are AI
- Never mention OpenAI
- Never say you are a bot
- Use light emojis when appropriate

Context:
Brand: InstaForge
Location: India
Service: Instagram automation and growth tools

If user greets → greet back
If user asks price → explain briefly
If user asks location → say India, online service
If confused → help politely
If rude → stay calm

Never hallucinate.
If unsure → say you will check.

Always stay in character."""
        
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message},
                ],
                max_tokens=200,
                temperature=0.7,
                timeout=self._timeout,
            )
            
            choice = response.choices[0] if response.choices else None
            if not choice or not getattr(choice.message, "content", None):
                logger.warning(
                    "AI_DM_REPLY",
                    action="empty_response",
                    account_id=account_id,
                    user_id=user_id,
                )
                return FALLBACK_REPLY
            
            reply = (choice.message.content or "").strip()
            if not reply:
                logger.warning(
                    "AI_DM_REPLY",
                    action="empty_reply",
                    account_id=account_id,
                    user_id=user_id,
                )
                return FALLBACK_REPLY
            
            # Record successful reply
            self.tracking.record_reply_sent(account_id, user_id)
            
            logger.info(
                "AI_DM_REPLY",
                action="generated",
                account_id=account_id,
                user_id=user_id,
                reply_preview=reply[:100] + ("..." if len(reply) > 100 else ""),
            )
            
            return reply
            
        except Exception as e:
            auth_fail = getattr(self, "_AuthError", None) and isinstance(e, self._AuthError)
            err_str = str(e).lower()
            quota_fail = "quota" in err_str or "429" in err_str or "insufficient_quota" in err_str
            
            if auth_fail:
                reason = "invalid_api_key"
                err_msg = f"{e}. Check OPENAI_API_KEY in .env"
            elif quota_fail:
                reason = "quota_exceeded"
                err_msg = f"{e}. Add billing at https://platform.openai.com/account/billing"
            else:
                reason = "exception"
                err_msg = str(e)
            
            logger.warning(
                "AI_DM_REPLY",
                action="failed",
                reason=reason,
                error=err_msg,
                error_type=type(e).__name__,
                account_id=account_id,
                user_id=user_id,
            )
            return FALLBACK_REPLY
    
    def process_incoming_dm(
        self,
        account_id: str,
        user_id: str,
        message_text: str,
        message_id: Optional[str] = None,
        account_username: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Process an incoming DM and generate a reply.
        
        This method:
        1. Validates input
        2. Checks rate limits
        3. Adds delay (3-6 seconds)
        4. Generates AI reply
        5. Returns result for sending
        
        Args:
            account_id: Account identifier
            user_id: User identifier (Instagram user ID)
            message_text: Incoming message text
            message_id: Optional message ID for logging
            account_username: Optional account username
            
        Returns:
            Dictionary with status, reply_text, and metadata
        """
        result = {
            "status": "skipped",
            "reply_text": None,
            "reason": None,
            "account_id": account_id,
            "user_id": user_id,
            "message_id": message_id,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        # Validate input
        message_text = self._sanitize_input(message_text)
        if not message_text:
            result["reason"] = "empty_message"
            logger.warning(
                "AI_DM_PROCESS",
                action="skipped",
                reason="empty_message",
                account_id=account_id,
                user_id=user_id,
                message_id=message_id,
            )
            return result
        
        # Check rate limit
        if not self.tracking.can_send_reply(account_id, user_id, MAX_REPLIES_PER_USER_PER_DAY):
            result["reason"] = "rate_limit_exceeded"
            result["reply_text"] = None  # Don't send anything if rate limited
            logger.warning(
                "AI_DM_PROCESS",
                action="rate_limited",
                account_id=account_id,
                user_id=user_id,
                message_id=message_id,
                count_today=self.tracking.get_user_reply_count_today(account_id, user_id),
            )
            return result
        
        # Add delay (3-6 seconds) to appear more human
        delay = random.uniform(REPLY_DELAY_MIN, REPLY_DELAY_MAX)
        logger.debug(
            "AI_DM_PROCESS",
            action="delaying",
            delay_seconds=delay,
            account_id=account_id,
            user_id=user_id,
        )
        time.sleep(delay)
        
        # Generate AI reply
        reply_text = self.get_ai_reply(
            message=message_text,
            account_id=account_id,
            user_id=user_id,
            account_username=account_username,
        )
        
        if reply_text and reply_text != FALLBACK_REPLY:
            result["status"] = "success"
            result["reply_text"] = reply_text
            result["reason"] = None
        else:
            # Fallback reply - still send it
            result["status"] = "fallback"
            result["reply_text"] = FALLBACK_REPLY
            result["reason"] = "openai_failed"
        
        logger.info(
            "AI_DM_PROCESS",
            action="completed",
            status=result["status"],
            account_id=account_id,
            user_id=user_id,
            message_id=message_id,
            has_reply=bool(result["reply_text"]),
        )
        
        return result


# Global instance for convenience
_global_handler: Optional[AIDMHandler] = None


def get_ai_reply(
    message: str,
    account_id: str,
    user_id: str,
    account_username: Optional[str] = None,
) -> str:
    """
    Convenience function to get AI reply.
    
    Args:
        message: Incoming DM text
        account_id: Account identifier
        user_id: User identifier
        account_username: Optional account username
        
    Returns:
        AI-generated reply or fallback
    """
    global _global_handler
    if _global_handler is None:
        _global_handler = AIDMHandler()
    return _global_handler.get_ai_reply(
        message=message,
        account_id=account_id,
        user_id=user_id,
        account_username=account_username,
    )
