"""
Configuration management with schema validation and atomic writes.
Single source of truth for InstaForge configuration.
"""

import os
import yaml
import shutil
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from .exceptions import ConfigError
from .logger import get_logger
from ..models.account import Account, ProxyConfig, WarmingConfig, CommentToDMConfig

logger = get_logger(__name__)

# Load environment variables
load_dotenv()

DATA_DIR = Path("data")
ACCOUNTS_FILE = DATA_DIR / "accounts.yaml"
SETTINGS_FILE = DATA_DIR / "settings.yaml"

class AppSettings(BaseModel):
    name: str = "InstaForge"
    version: str = "1.0.0"
    environment: str = "production"

class InstagramSettings(BaseModel):
    api_base_url: str = "https://graph.facebook.com"
    api_version: str = "v18.0"
    rate_limit: Dict[str, Any] = Field(default_factory=dict)
    posting: Dict[str, Any] = Field(default_factory=dict)

class LoggingSettings(BaseModel):
    level: str = "INFO"
    format: str = "json"
    file_path: str = "logs/instaforge.log"
    max_bytes: int = 10485760
    backup_count: int = 5

class WarmingSettings(BaseModel):
    schedule_time: str = "09:00"
    randomize_delay_minutes: int = 30
    action_spacing_seconds: int = 60

class DefaultProxy(BaseModel):
    """Shared/default proxy for warm-up browser (and other automation)."""
    enabled: bool = False
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    protocol: str = "socks5"  # http or socks5; socks5 often works better for residential proxies

    def proxy_url(self) -> Optional[str]:
        """Build proxy URL (socks5:// or http://[user:pass@]host:port)."""
        if not self.enabled or not self.host or not self.port:
            return None
        scheme = "socks5" if self.protocol == "socks5" else "http"
        if self.username and self.password:
            return f"{scheme}://{self.username}:{self.password}@{self.host}:{self.port}"
        return f"{scheme}://{self.host}:{self.port}"


class ProxySettings(BaseModel):
    connection_timeout: int = 60
    max_retries: int = 3
    verify_ssl: bool = False
    webhooks: Optional[Dict[str, Any]] = None
    default_proxy: Optional[DefaultProxy] = None

class CommentSettings(BaseModel):
    enabled: bool = False
    templates: List[str] = Field(default_factory=list)
    delay_seconds: int = 30

class Settings(BaseModel):
    app: AppSettings
    instagram: InstagramSettings
    logging: LoggingSettings
    warming: WarmingSettings
    proxies: ProxySettings
    comments: CommentSettings = Field(default_factory=CommentSettings)

class AccountsConfig(BaseModel):
    accounts: List[Account] = Field(default_factory=list)

class ConfigManager:
    """Singleton configuration manager"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self.accounts_path = ACCOUNTS_FILE
        self.settings_path = SETTINGS_FILE
        self._settings: Optional[Settings] = None
        self._accounts: Optional[List[Account]] = None
        
        # Create data directory if it doesn't exist
        DATA_DIR.mkdir(exist_ok=True, parents=True)
        
        self._initialized = True

    def _substitute_env_vars(self, value: Any) -> Any:
        """Recursively substitute environment variables"""
        if isinstance(value, str):
            if value.startswith("${") and value.endswith("}"):
                var_expr = value[2:-1]
                if ":" in var_expr:
                    var_name, default = var_expr.split(":", 1)
                    return os.getenv(var_name.strip(), default.strip())
                else:
                    return os.getenv(var_expr, value)
        elif isinstance(value, dict):
            return {k: self._substitute_env_vars(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self._substitute_env_vars(item) for item in value]
        return value

    def load_settings(self) -> Settings:
        """Load and validate settings.yaml"""
        if not self.settings_path.exists():
            raise ConfigError(f"Settings file not found: {self.settings_path}")
            
        with open(self.settings_path, "r", encoding="utf-8") as f:
            raw_data = yaml.safe_load(f)
            
        processed_data = self._substitute_env_vars(raw_data)
        self._settings = Settings(**processed_data)
        return self._settings

    def load_accounts(self) -> List[Account]:
        """Load and validate accounts.yaml. Skips invalid entries so one bad account does not break startup."""
        if not self.accounts_path.exists():
            return []
        try:
            with open(self.accounts_path, "r", encoding="utf-8") as f:
                raw_data = yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning("Failed to read accounts file", path=str(self.accounts_path), error=str(e))
            self._accounts = getattr(self, "_accounts", None) or []
            return self._accounts
        raw_accounts = raw_data.get("accounts", [])
        if not raw_accounts:
            self._accounts = []
            return []
        processed_accounts = self._substitute_env_vars(raw_accounts)
        accounts = []
        for i, acc_data in enumerate(processed_accounts):
            try:
                accounts.append(Account(**acc_data))
            except Exception as e:
                account_id = (acc_data or {}).get("account_id") or (acc_data or {}).get("username") or f"index_{i}"
                logger.warning(
                    "Skipping invalid account in accounts.yaml",
                    account_id=account_id,
                    error=str(e),
                )
        self._accounts = accounts
        return self._accounts

    def save_accounts(self, accounts: List[Account]) -> None:
        """Atomically save accounts to YAML"""
        # Convert models to dicts
        data = {"accounts": [acc.dict(exclude_unset=True) for acc in accounts]}
        self._atomic_write(self.accounts_path, data)
        self._accounts = accounts

    def save_settings(self, settings: Settings) -> None:
        """Atomically save settings to YAML"""
        data = settings.dict(exclude_unset=True)
        self._atomic_write(self.settings_path, data)
        self._settings = settings

    def _atomic_write(self, path: Path, data: Dict[str, Any]) -> None:
        """Write YAML file atomically"""
        # Create temp file in the same directory to ensure same filesystem
        dir_path = path.parent
        with tempfile.NamedTemporaryFile(mode='w', dir=dir_path, delete=False, encoding='utf-8') as tf:
            yaml.dump(data, tf, default_flow_style=False, sort_keys=False, allow_unicode=True)
            temp_path = Path(tf.name)
        
        try:
            # Atomic move/replace
            shutil.move(str(temp_path), str(path))
        except Exception as e:
            # Clean up temp file if move failed
            if temp_path.exists():
                temp_path.unlink()
            raise ConfigError(f"Failed to save config to {path}: {str(e)}")

# Global instance
config_manager = ConfigManager()
