"""
Per-account warm-up automation config.
"""

from typing import Dict, Any
from .store import get_config


def get_automation_config(account_id: str) -> Dict[str, Any]:
    """Get automation config for an account with defaults."""
    cfg = get_config(account_id)
    return cfg.to_dict()
