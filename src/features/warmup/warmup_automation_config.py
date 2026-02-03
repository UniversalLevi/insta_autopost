"""
Warm-Up Automation Config - Per-account settings for automated warm-up actions.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional, List

from ...utils.logger import get_logger

logger = get_logger(__name__)

DATA_DIR = Path("data")
CONFIG_FILE = DATA_DIR / "warmup_automation_config.json"

DEFAULT_HASHTAGS = ["explore", "instagram"]
DEFAULT_SCHEDULE = ["09:00", "14:00", "18:00"]


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(exist_ok=True, parents=True)


def load_config() -> Dict[str, Dict[str, Any]]:
    """Load all warmup automation configs. Returns {account_id: config}."""
    _ensure_data_dir()
    if not CONFIG_FILE.exists():
        return {}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("accounts", {}) if isinstance(data, dict) else {}
    except Exception as e:
        logger.warning("Failed to load warmup automation config", error=str(e))
        return {}


def save_config(accounts: Dict[str, Dict[str, Any]]) -> None:
    """Save warmup automation configs."""
    _ensure_data_dir()
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump({"accounts": accounts}, f, indent=2)


def get_config(account_id: str) -> Dict[str, Any]:
    """Get automation config for account. Returns defaults if not set."""
    configs = load_config()
    cfg = configs.get(account_id, {})
    return {
        "automation_enabled": cfg.get("automation_enabled", False),
        "target_hashtags": cfg.get("target_hashtags") or DEFAULT_HASHTAGS.copy(),
        "schedule_times": cfg.get("schedule_times") or DEFAULT_SCHEDULE.copy(),
    }


def set_config(account_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """Update automation config for account."""
    configs = load_config()
    cfg = configs.get(account_id, get_config(account_id))
    cfg.update(updates)
    configs[account_id] = cfg
    save_config(configs)
    return cfg
