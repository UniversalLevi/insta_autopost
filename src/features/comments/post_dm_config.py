"""Per-post comment-to-DM configuration storage"""

import json
from pathlib import Path
from typing import Dict, Optional, Any
from ...utils.logger import get_logger

logger = get_logger(__name__)


class PostDMConfig:
    """Manages per-post comment-to-DM file/link assignments"""
    
    def __init__(self, config_file: str = "data/post_dm_config.json"):
        self.config_file = Path(config_file)
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        self._config: Dict[str, Dict[str, Any]] = self._load_config()
    
    def _load_config(self) -> Dict[str, Dict[str, Any]]:
        """Load configuration from file"""
        if not self.config_file.exists():
            return {}
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error("Failed to load post DM config", error=str(e))
            return {}
    
    def _save_config(self):
        """Save configuration to file"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error("Failed to save post DM config", error=str(e))
    
    def set_post_dm_file(
        self,
        account_id: str,
        media_id: str,
        file_path: Optional[str] = None,
        file_url: Optional[str] = None,
    ):
        """
        Set file/link to send when someone comments on a specific post
        
        Args:
            account_id: Account identifier
            media_id: Instagram media ID (post ID)
            file_path: Local file path (will be converted to URL if needed)
            file_url: Direct URL to file/PDF
        """
        key = f"{account_id}:{media_id}"
        
        if file_path and not file_url:
            # Convert local file path to file:// URL
            file_url = f"file:///{file_path.replace(chr(92), '/')}"
        
        if not file_url:
            # Remove config if both are None
            if key in self._config:
                del self._config[key]
                self._save_config()
            return
        
        self._config[key] = {
            "account_id": account_id,
            "media_id": media_id,
            "file_url": file_url,
            "file_path": file_path,
        }
        
        self._save_config()
        
        logger.info(
            "Post DM file configured",
            account_id=account_id,
            media_id=media_id,
            file_url=file_url,
        )
    
    def get_post_dm_file(self, account_id: str, media_id: str) -> Optional[str]:
        """
        Get file/link configured for a specific post
        
        Args:
            account_id: Account identifier
            media_id: Instagram media ID
            
        Returns:
            File URL if configured, None otherwise
        """
        key = f"{account_id}:{media_id}"
        config = self._config.get(key)
        
        if config:
            return config.get("file_url")
        
        return None
    
    def remove_post_dm_file(self, account_id: str, media_id: str):
        """Remove file configuration for a post"""
        key = f"{account_id}:{media_id}"
        if key in self._config:
            del self._config[key]
            self._save_config()
            logger.info(
                "Post DM file removed",
                account_id=account_id,
                media_id=media_id,
            )
    
    def get_all_posts(self, account_id: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """Get all configured posts, optionally filtered by account"""
        if account_id:
            return {
                k: v for k, v in self._config.items()
                if v.get("account_id") == account_id
            }
        return self._config.copy()
