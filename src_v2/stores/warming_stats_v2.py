"""
Isolated warming stats store (warming_stats_v2). Keys: user_id, instagram_id.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

DATA_DIR = Path(os.getenv("V2_DATA_DIR", "data"))
WARMING_STATS_FILE = DATA_DIR / "warming_stats_v2.json"


def _load_all() -> Dict[str, Dict[str, Any]]:
    if not WARMING_STATS_FILE.exists():
        return {}
    try:
        return json.loads(WARMING_STATS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _key(user_id: str, instagram_id: str) -> str:
    return f"{user_id}:{instagram_id}"


def get_stats(user_id: str, instagram_id: str) -> Dict[str, Any]:
    data = _load_all()
    return data.get(_key(user_id, instagram_id), {})


def set_stats(user_id: str, instagram_id: str, stats: Dict[str, Any]) -> None:
    data = _load_all()
    data[_key(user_id, instagram_id)] = {**get_stats(user_id, instagram_id), **stats}
    WARMING_STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
    WARMING_STATS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
