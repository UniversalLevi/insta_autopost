"""
Per-user resource limits (user_limits_v2).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

DATA_DIR = Path(os.getenv("V2_DATA_DIR", "data"))
LIMITS_FILE = DATA_DIR / "user_limits_v2.json"


def _load_all() -> Dict[str, Dict[str, Any]]:
    if not LIMITS_FILE.exists():
        return {}
    try:
        return json.loads(LIMITS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_all(data: Dict[str, Dict[str, Any]]) -> None:
    LIMITS_FILE.parent.mkdir(parents=True, exist_ok=True)
    LIMITS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_limits(user_id: str) -> Dict[str, Any]:
    data = _load_all()
    return data.get(user_id, {})


def set_limits(user_id: str, limits: Dict[str, Any]) -> None:
    data = _load_all()
    data[user_id] = {**get_limits(user_id), **limits}
    _save_all(data)
