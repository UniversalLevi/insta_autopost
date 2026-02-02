"""
Isolated posts store (posts_v2). Keys: user_id, instagram_id.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List

DATA_DIR = Path(os.getenv("V2_DATA_DIR", "data"))
POSTS_FILE = DATA_DIR / "posts_v2.json"


def _load_all() -> Dict[str, List[Dict[str, Any]]]:
    if not POSTS_FILE.exists():
        return {}
    try:
        return json.loads(POSTS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _key(user_id: str, instagram_id: str) -> str:
    return f"{user_id}:{instagram_id}"


def list_posts(user_id: str, instagram_id: str) -> List[Dict[str, Any]]:
    data = _load_all()
    return data.get(_key(user_id, instagram_id), [])


def append_post(user_id: str, instagram_id: str, post: Dict[str, Any]) -> None:
    data = _load_all()
    k = _key(user_id, instagram_id)
    data.setdefault(k, []).append(post)
    POSTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    POSTS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
