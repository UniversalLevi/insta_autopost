"""Configuration loader"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, List
from dotenv import load_dotenv
from pydantic import BaseModel

from .exceptions import ConfigError
from ..models.account import Account, ProxyConfig, WarmingConfig, CommentToDMConfig


class AppSettings(BaseModel):
    """Application settings"""
    name: str
    version: str
    environment: str


class InstagramSettings(BaseModel):
    """Instagram API settings"""
    api_base_url: str
    api_version: str
    rate_limit: Dict[str, Any]
    posting: Dict[str, Any]


class LoggingSettings(BaseModel):
    """Logging settings"""
    level: str
    format: str
    file_path: str
    max_bytes: int
    backup_count: int


class WarmingSettings(BaseModel):
    """Warming up settings"""
    schedule_time: str
    randomize_delay_minutes: int
    action_spacing_seconds: int


class ProxySettings(BaseModel):
    """Proxy settings"""
    connection_timeout: int
    max_retries: int
    verify_ssl: bool


class Config(BaseModel):
    """Main configuration model"""
    app: AppSettings
    instagram: InstagramSettings
    logging: LoggingSettings
    warming: WarmingSettings
    proxies: ProxySettings


class ConfigLoader:
    """Load and parse configuration files"""
    
    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        load_dotenv()  # Load environment variables
    
    def _substitute_env_vars(self, value: Any, context: str = "") -> Any:
        """Recursively substitute environment variables in config values"""
        if isinstance(value, str):
            if value.startswith("${") and value.endswith("}"):
                # Extract variable name and default value
                var_expr = value[2:-1]
                if ":" in var_expr:
                    var_name, default = var_expr.split(":", 1)
                    return os.getenv(var_name.strip(), default.strip())
                else:
                    env_value = os.getenv(var_expr)
                    if env_value is None:
                        error_msg = f"Environment variable {var_expr} not found"
                        if context:
                            error_msg += f" (context: {context})"
                        raise ConfigError(error_msg)
                    return env_value
        elif isinstance(value, dict):
            return {
                k: self._substitute_env_vars(
                    v, 
                    context=f"{context}.{k}" if context else k
                ) 
                for k, v in value.items()
            }
        elif isinstance(value, list):
            return [
                self._substitute_env_vars(
                    item, 
                    context=f"{context}[{i}]" if context else f"[{i}]"
                ) 
                for i, item in enumerate(value)
            ]
        return value
    
    def load_settings(self) -> Config:
        """Load application settings"""
        settings_path = self.config_dir / "settings.yaml"
        if not settings_path.exists():
            raise ConfigError(f"Settings file not found: {settings_path}")
        
        with open(settings_path, "r") as f:
            raw_config = yaml.safe_load(f)
        
        # Substitute environment variables
        config = self._substitute_env_vars(raw_config)
        
        return Config(**config)
    
    def load_accounts(self) -> List[Account]:
        """Load account configurations"""
        accounts_path = self.config_dir / "accounts.yaml"
        if not accounts_path.exists():
            raise ConfigError(f"Accounts file not found: {accounts_path}")
        
        with open(accounts_path, "r") as f:
            raw_accounts = yaml.safe_load(f)
        
        # Process accounts but handle proxy separately
        raw_accounts_list = raw_accounts.get("accounts", [])
        accounts = []
        
        for raw_acc_data in raw_accounts_list:
            # Extract proxy, warming, and comment_to_dm before substitution
            proxy_data = raw_acc_data.pop("proxy", {})
            warming_data = raw_acc_data.pop("warming", {})
            comment_to_dm_data = raw_acc_data.pop("comment_to_dm", None)
            
            # Substitute env vars for non-proxy fields
            acc_data = self._substitute_env_vars(raw_acc_data)
            
            # Handle proxy separately - only substitute if enabled
            if proxy_data.get("enabled", False):
                proxy_data = self._substitute_env_vars(proxy_data)
            else:
                # Proxy disabled - just use default
                proxy_data = {"enabled": False}
            
            # Substitute env vars for warming
            warming_data = self._substitute_env_vars(warming_data)
            
            # Handle comment_to_dm configuration
            comment_to_dm_config = None
            if comment_to_dm_data:
                comment_to_dm_data = self._substitute_env_vars(comment_to_dm_data)
                comment_to_dm_config = CommentToDMConfig(**comment_to_dm_data)
            
            account = Account(
                **acc_data,
                proxy=ProxyConfig(**proxy_data),
                warming=WarmingConfig(**warming_data),
                comment_to_dm=comment_to_dm_config,
            )
            accounts.append(account)
        
        return accounts
