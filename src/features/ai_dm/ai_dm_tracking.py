"""Persistent tracking of AI DM replies per user for rate limiting"""

import json
import time
from pathlib import Path
from typing import Dict, Set
from datetime import datetime, timedelta
from ...utils.logger import get_logger

logger = get_logger(__name__)


class AIDMTracking:
    """Persistent tracking of AI DM replies per user per day for rate limiting"""
    
    def __init__(self, tracking_file: str = "data/ai_dm_tracking.json"):
        self.tracking_file = Path(tracking_file)
        self.tracking_file.parent.mkdir(parents=True, exist_ok=True)
        self._tracking: Dict[str, Dict[str, Dict[str, int]]] = self._load_tracking()
        # Format: account_id -> {date -> {user_id: count}}
    
    def _load_tracking(self) -> Dict[str, Dict[str, Dict[str, int]]]:
        """Load tracking data from file"""
        if not self.tracking_file.exists():
            return {}
        
        try:
            with open(self.tracking_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data
        except Exception as e:
            logger.error("Failed to load AI DM tracking", error=str(e))
            return {}
    
    def _save_tracking(self):
        """Save tracking data to file"""
        try:
            with open(self.tracking_file, 'w', encoding='utf-8') as f:
                json.dump(self._tracking, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error("Failed to save AI DM tracking", error=str(e))
    
    def get_user_reply_count_today(self, account_id: str, user_id: str) -> int:
        """Get count of AI replies sent to this user today"""
        today = datetime.utcnow().date().isoformat()
        
        if account_id not in self._tracking:
            return 0
        
        if today not in self._tracking[account_id]:
            return 0
        
        return self._tracking[account_id][today].get(user_id, 0)
    
    def can_send_reply(self, account_id: str, user_id: str, max_per_day: int = 10) -> bool:
        """Check if we can send a reply to this user (rate limit check)"""
        count = self.get_user_reply_count_today(account_id, user_id)
        return count < max_per_day
    
    def record_reply_sent(self, account_id: str, user_id: str):
        """Record that a reply was sent to this user"""
        today = datetime.utcnow().date().isoformat()
        
        if account_id not in self._tracking:
            self._tracking[account_id] = {}
        
        if today not in self._tracking[account_id]:
            self._tracking[account_id][today] = {}
        
        if user_id not in self._tracking[account_id][today]:
            self._tracking[account_id][today][user_id] = 0
        
        self._tracking[account_id][today][user_id] += 1
        
        # Clean old entries (keep last 7 days)
        cutoff_date = (datetime.utcnow() - timedelta(days=7)).date().isoformat()
        self._tracking[account_id] = {
            date: user_counts
            for date, user_counts in self._tracking[account_id].items()
            if date >= cutoff_date
        }
        
        self._save_tracking()
        
        logger.debug(
            "AI DM reply recorded",
            account_id=account_id,
            user_id=user_id,
            date=today,
            count_today=self._tracking[account_id][today][user_id],
        )
