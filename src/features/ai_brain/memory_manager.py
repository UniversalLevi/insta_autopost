"""Memory Manager - Manages conversation memory and context per user"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from ...utils.logger import get_logger

logger = get_logger(__name__)

# Maximum messages to store per user
MAX_MESSAGES_PER_USER = 50
# Days to keep old messages
MEMORY_RETENTION_DAYS = 30


class MemoryManager:
    """Manages conversation memory per account and user"""
    
    def __init__(self, memory_file: str = "data/ai_memory.json"):
        self.memory_file = Path(memory_file)
        self.memory_file.parent.mkdir(parents=True, exist_ok=True)
        self._memory: Dict[str, Dict[str, Dict[str, Any]]] = self._load_memory()
        # Format: account_id -> {user_id: {history: [], tags: [], last_seen: ""}}
    
    def _load_memory(self) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """Load memory from file"""
        if not self.memory_file.exists():
            return {}
        
        try:
            with open(self.memory_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data
        except Exception as e:
            logger.error("Failed to load AI memory", error=str(e))
            return {}
    
    def _save_memory(self):
        """Save memory to file"""
        try:
            with open(self.memory_file, 'w', encoding='utf-8') as f:
                json.dump(self._memory, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error("Failed to save AI memory", error=str(e))
    
    def store_message(
        self,
        account_id: str,
        user_id: str,
        text: str,
        role: str = "user",
        reply: Optional[str] = None,
    ):
        """
        Store a message in memory.
        
        Args:
            account_id: Account identifier
            user_id: User identifier
            text: Message text
            role: Message role ("user" or "assistant")
            reply: Optional reply text (for assistant messages)
        """
        if account_id not in self._memory:
            self._memory[account_id] = {}
        
        if user_id not in self._memory[account_id]:
            self._memory[account_id][user_id] = {
                "history": [],
                "tags": [],
                "last_seen": datetime.utcnow().isoformat(),
            }
        
        # Add message to history
        message_entry = {
            "text": text,
            "role": role,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        if reply:
            message_entry["reply"] = reply
        
        self._memory[account_id][user_id]["history"].append(message_entry)
        
        # Limit history size
        history = self._memory[account_id][user_id]["history"]
        if len(history) > MAX_MESSAGES_PER_USER:
            # Keep most recent messages
            self._memory[account_id][user_id]["history"] = history[-MAX_MESSAGES_PER_USER:]
        
        # Update last seen
        self._memory[account_id][user_id]["last_seen"] = datetime.utcnow().isoformat()
        
        # Auto-tag based on content (simple keyword detection)
        self._auto_tag_user(account_id, user_id, text)
        
        self._save_memory()
        
        logger.debug(
            "Message stored in memory",
            account_id=account_id,
            user_id=user_id,
            role=role,
            history_length=len(self._memory[account_id][user_id]["history"]),
        )
    
    def get_context(self, account_id: str, user_id: str, max_messages: int = 10) -> List[Dict[str, Any]]:
        """
        Get conversation context for a user.
        
        Args:
            account_id: Account identifier
            user_id: User identifier
            max_messages: Maximum number of recent messages to return
            
        Returns:
            List of recent messages (most recent first)
        """
        if account_id not in self._memory:
            return []
        
        if user_id not in self._memory[account_id]:
            return []
        
        history = self._memory[account_id][user_id].get("history", [])
        
        # Return most recent messages
        return history[-max_messages:]
    
    def get_user_info(self, account_id: str, user_id: str) -> Dict[str, Any]:
        """
        Get user information including tags and last seen.
        
        Args:
            account_id: Account identifier
            user_id: User identifier
            
        Returns:
            User info dictionary
        """
        if account_id not in self._memory:
            return {"tags": [], "last_seen": None, "message_count": 0}
        
        if user_id not in self._memory[account_id]:
            return {"tags": [], "last_seen": None, "message_count": 0}
        
        user_data = self._memory[account_id][user_id]
        return {
            "tags": user_data.get("tags", []),
            "last_seen": user_data.get("last_seen"),
            "message_count": len(user_data.get("history", [])),
        }
    
    def add_tag(self, account_id: str, user_id: str, tag: str):
        """Add a tag to a user"""
        if account_id not in self._memory:
            self._memory[account_id] = {}
        if user_id not in self._memory[account_id]:
            self._memory[account_id][user_id] = {"history": [], "tags": [], "last_seen": ""}
        
        tags = self._memory[account_id][user_id].get("tags", [])
        if tag not in tags:
            tags.append(tag)
            self._memory[account_id][user_id]["tags"] = tags
            self._save_memory()
    
    def remove_tag(self, account_id: str, user_id: str, tag: str):
        """Remove a tag from a user"""
        if account_id in self._memory and user_id in self._memory[account_id]:
            tags = self._memory[account_id][user_id].get("tags", [])
            if tag in tags:
                tags.remove(tag)
                self._memory[account_id][user_id]["tags"] = tags
                self._save_memory()
    
    def _auto_tag_user(self, account_id: str, user_id: str, text: str):
        """Automatically tag users based on message content"""
        text_lower = text.lower()
        
        # Common interest tags
        interest_keywords = {
            "pricing": ["price", "cost", "how much", "pricing", "payment"],
            "location": ["where", "location", "address", "city", "country"],
            "product": ["product", "service", "offer", "feature"],
            "support": ["help", "support", "issue", "problem", "error"],
        }
        
        for tag, keywords in interest_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                self.add_tag(account_id, user_id, tag)
    
    def cleanup_old(self, days: int = MEMORY_RETENTION_DAYS):
        """
        Clean up old messages beyond retention period.
        
        Args:
            days: Number of days to retain messages
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        cutoff_iso = cutoff_date.isoformat()
        
        cleaned = 0
        for account_id, users in self._memory.items():
            for user_id, user_data in list(users.items()):
                history = user_data.get("history", [])
                original_count = len(history)
                
                # Filter out old messages
                history = [
                    msg for msg in history
                    if msg.get("timestamp", "") >= cutoff_iso
                ]
                
                if len(history) < original_count:
                    user_data["history"] = history
                    cleaned += original_count - len(history)
                
                # Remove empty user entries
                if not history and not user_data.get("tags"):
                    del users[user_id]
        
        if cleaned > 0:
            self._save_memory()
            logger.info("Cleaned up old memory", messages_removed=cleaned)
    
    def reset_user_memory(self, account_id: str, user_id: str) -> bool:
        """
        Reset memory for a specific user.
        
        Args:
            account_id: Account identifier
            user_id: User identifier
            
        Returns:
            True if reset, False if not found
        """
        if account_id in self._memory and user_id in self._memory[account_id]:
            del self._memory[account_id][user_id]
            self._save_memory()
            logger.info("User memory reset", account_id=account_id, user_id=user_id)
            return True
        return False
    
    def reset_account_memory(self, account_id: str) -> bool:
        """
        Reset all memory for an account.
        
        Args:
            account_id: Account identifier
            
        Returns:
            True if reset, False if not found
        """
        if account_id in self._memory:
            del self._memory[account_id]
            self._save_memory()
            logger.info("Account memory reset", account_id=account_id)
            return True
        return False
    
    def get_stats(self, account_id: str) -> Dict[str, Any]:
        """
        Get memory statistics for an account.
        
        Args:
            account_id: Account identifier
            
        Returns:
            Statistics dictionary
        """
        if account_id not in self._memory:
            return {
                "total_users": 0,
                "total_messages": 0,
                "users_with_tags": 0,
            }
        
        users = self._memory[account_id]
        total_messages = sum(len(user_data.get("history", [])) for user_data in users.values())
        users_with_tags = sum(1 for user_data in users.values() if user_data.get("tags"))
        
        return {
            "total_users": len(users),
            "total_messages": total_messages,
            "users_with_tags": users_with_tags,
        }
