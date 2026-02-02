"""
Isolated DM logs store (dm_logs_v2). Keys: user_id, instagram_id.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List

DATA_DIR = Path(os.getenv("V2_DATA_DIR", "data"))
DM_LOGS_FILE = DATA_DIR / "dm_logs_v2.json"


def _load_all() -> Dict[str, List[Dict[str, Any]]]:
    if not DM_LOGS_FILE.exists():
        return {}
    try:
        return json.loads(DM_LOGS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _key(user_id: str, instagram_id: str) -> str:
    return f"{user_id}:{instagram_id}"


def list_dm_logs(user_id: str, instagram_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    data = _load_all()
    entries = data.get(_key(user_id, instagram_id), [])
    return entries[-limit:]


def append_dm_log(user_id: str, instagram_id: str, entry: Dict[str, Any]) -> None:
    data = _load_all()
    k = _key(user_id, instagram_id)
    data.setdefault(k, []).append(entry)
    DM_LOGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    DM_LOGS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
