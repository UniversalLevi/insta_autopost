"""AI Settings Service - High-level service for AI Brain functionality"""

from typing import Dict, Any, Optional

from .profile_manager import ProfileManager
from .memory_manager import MemoryManager
from .prompt_builder import PromptBuilder
from ...utils.logger import get_logger

logger = get_logger(__name__)


class AISettingsService:
    """High-level service for managing AI Brain settings and operations"""
    
    def __init__(self):
        self.profile_manager = ProfileManager()
        self.memory_manager = MemoryManager()
        self.prompt_builder = PromptBuilder(
            profile_manager=self.profile_manager,
            memory_manager=self.memory_manager,
        )
    
    def get_profile(self, account_id: str) -> Dict[str, Any]:
        """Get profile for an account"""
        return self.profile_manager.get_profile(account_id)
    
    def update_profile(self, account_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update profile for an account"""
        return self.profile_manager.update_profile(account_id, data)
    
    def get_memory_stats(self, account_id: str) -> Dict[str, Any]:
        """Get memory statistics for an account"""
        return self.memory_manager.get_stats(account_id)
    
    def reset_memory(self, account_id: str, user_id: Optional[str] = None) -> bool:
        """
        Reset memory for an account or specific user.
        
        Args:
            account_id: Account identifier
            user_id: Optional user identifier (if None, resets all account memory)
            
        Returns:
            True if reset, False if not found
        """
        if user_id:
            return self.memory_manager.reset_user_memory(account_id, user_id)
        else:
            return self.memory_manager.reset_account_memory(account_id)
    
    def build_prompt(self, account_id: str, user_id: str, message: str) -> str:
        """Build customized prompt for a conversation"""
        return self.prompt_builder.build_prompt(account_id, user_id, message)
    
    def store_conversation(
        self,
        account_id: str,
        user_id: str,
        user_message: str,
        ai_reply: str,
    ):
        """
        Store a conversation exchange in memory.
        
        Args:
            account_id: Account identifier
            user_id: User identifier
            user_message: User's message
            ai_reply: AI's reply
        """
        # Store user message
        self.memory_manager.store_message(
            account_id=account_id,
            user_id=user_id,
            text=user_message,
            role="user",
        )
        
        # Store AI reply
        self.memory_manager.store_message(
            account_id=account_id,
            user_id=user_id,
            text=ai_reply,
            role="assistant",
            reply=ai_reply,
        )
    
    def get_user_context(self, account_id: str, user_id: str) -> Dict[str, Any]:
        """
        Get full context for a user.
        
        Args:
            account_id: Account identifier
            user_id: User identifier
            
        Returns:
            Dictionary with user info and recent messages
        """
        user_info = self.memory_manager.get_user_info(account_id, user_id)
        context = self.memory_manager.get_context(account_id, user_id, max_messages=10)
        
        return {
            "user_info": user_info,
            "recent_messages": context,
        }
