"""
Isolated AI memory store (ai_memory_v2). Keys: user_id, instagram_id.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List

DATA_DIR = Path(os.getenv("V2_DATA_DIR", "data"))
AI_MEMORY_FILE = DATA_DIR / "ai_memory_v2.json"


def _load_all() -> Dict[str, Dict[str, Any]]:
    if not AI_MEMORY_FILE.exists():
        return {}
    try:
        return json.loads(AI_MEMORY_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _key(user_id: str, instagram_id: str) -> str:
    return f"{user_id}:{instagram_id}"


def get_memory(user_id: str, instagram_id: str) -> Dict[str, Any]:
    data = _load_all()
    return data.get(_key(user_id, instagram_id), {})


def set_memory(user_id: str, instagram_id: str, memory: Dict[str, Any]) -> None:
    data = _load_all()
    data[_key(user_id, instagram_id)] = memory
    AI_MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    AI_MEMORY_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
