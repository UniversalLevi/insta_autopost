"""Profile Manager - Manages per-account AI bot personality and business info"""

import json
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

from ...utils.logger import get_logger

logger = get_logger(__name__)


class ProfileManager:
    """Manages AI bot profiles per account"""
    
    def __init__(self, profiles_file: str = "data/ai_profiles.json"):
        self.profiles_file = Path(profiles_file)
        self.profiles_file.parent.mkdir(parents=True, exist_ok=True)
        self._profiles: Dict[str, Dict[str, Any]] = self._load_profiles()
    
    def _load_profiles(self) -> Dict[str, Dict[str, Any]]:
        """Load profiles from file"""
        if not self.profiles_file.exists():
            return {}
        
        try:
            with open(self.profiles_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data
        except Exception as e:
            logger.error("Failed to load AI profiles", error=str(e))
            return {}
    
    def _save_profiles(self):
        """Save profiles to file"""
        try:
            with open(self.profiles_file, 'w', encoding='utf-8') as f:
                json.dump(self._profiles, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error("Failed to save AI profiles", error=str(e))
    
    def get_profile(self, account_id: str) -> Dict[str, Any]:
        """
        Get profile for an account.
        
        Args:
            account_id: Account identifier
            
        Returns:
            Profile dictionary with default values if not exists
        """
        profile = self._profiles.get(account_id, {})
        
        # Return with defaults
        return {
            "brand_name": profile.get("brand_name", ""),
            "business_type": profile.get("business_type", ""),
            "tone": profile.get("tone", "friendly"),
            "language": profile.get("language", "en"),
            "pricing": profile.get("pricing", ""),
            "location": profile.get("location", ""),
            "about_business": profile.get("about_business", ""),
            "custom_rules": profile.get("custom_rules", []),
            "custom_prompt": profile.get("custom_prompt", ""),
            "enable_memory": profile.get("enable_memory", True),
            "created_at": profile.get("created_at"),
            "updated_at": profile.get("updated_at"),
        }
    
    def update_profile(self, account_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update profile for an account.
        
        Args:
            account_id: Account identifier
            data: Profile data to update
            
        Returns:
            Updated profile
        """
        # Get existing profile or create new
        profile = self._profiles.get(account_id, {})
        
        # Update fields
        allowed_fields = [
            "brand_name", "business_type", "tone", "language",
            "pricing", "location", "about_business", "custom_rules",
            "custom_prompt", "enable_memory"
        ]
        
        for field in allowed_fields:
            if field in data:
                profile[field] = data[field]
        
        # Set timestamps
        if account_id not in self._profiles:
            profile["created_at"] = datetime.utcnow().isoformat()
        profile["updated_at"] = datetime.utcnow().isoformat()
        
        # Save
        self._profiles[account_id] = profile
        self._save_profiles()
        
        logger.info(
            "AI profile updated",
            account_id=account_id,
            updated_fields=list(data.keys()),
        )
        
        return self.get_profile(account_id)
    
    def save_profile(self, account_id: str, profile: Dict[str, Any]):
        """
        Save profile directly (internal use).
        
        Args:
            account_id: Account identifier
            profile: Profile dictionary
        """
        self._profiles[account_id] = profile
        self._save_profiles()
    
    def has_profile(self, account_id: str) -> bool:
        """Check if account has a profile"""
        return account_id in self._profiles and bool(self._profiles[account_id])
    
    def delete_profile(self, account_id: str) -> bool:
        """
        Delete profile for an account.
        
        Args:
            account_id: Account identifier
            
        Returns:
            True if deleted, False if not found
        """
        if account_id in self._profiles:
            del self._profiles[account_id]
            self._save_profiles()
            logger.info("AI profile deleted", account_id=account_id)
            return True
        return False
