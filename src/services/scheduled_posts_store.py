"""Persist and process scheduled posts for web scheduling."""

import json
import uuid
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

from ..utils.logger import get_logger

logger = get_logger(__name__)

DATA_DIR = Path("data")
SCHEDULED_FILE = DATA_DIR / "scheduled_posts.json"


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(exist_ok=True, parents=True)


def load_scheduled() -> List[Dict[str, Any]]:
    """Load all scheduled posts from disk."""
    _ensure_data_dir()
    if not SCHEDULED_FILE.exists():
        return []
    try:
        with open(SCHEDULED_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("posts", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
    except Exception as e:
        logger.warning("Failed to load scheduled posts", error=str(e))
        return []


def save_scheduled(posts: List[Dict[str, Any]]) -> None:
    """Overwrite scheduled posts on disk."""
    _ensure_data_dir()
    with open(SCHEDULED_FILE, "w", encoding="utf-8") as f:
        json.dump({"posts": posts}, f, indent=2)


def add_scheduled(
    account_id: str,
    media_type: str,
    urls: List[str],
    caption: str,
    scheduled_time: datetime,
    hashtags: Optional[List[str]] = None,
) -> str:
    """Append a scheduled post and return its id."""
    posts = load_scheduled()
    post_id = str(uuid.uuid4())
    post = {
        "id": post_id,
        "account_id": account_id,
        "media_type": media_type,
        "urls": urls,
        "caption": caption or "",
        "hashtags": hashtags or [],
        "scheduled_time": scheduled_time.isoformat(),
        "status": "scheduled",
        "created_at": datetime.utcnow().isoformat(),
    }
    posts.append(post)
    save_scheduled(posts)
    logger.info("Scheduled post added", post_id=post_id, scheduled_time=scheduled_time.isoformat())
    return post_id


def get_due_posts() -> List[Dict[str, Any]]:
    """Return scheduled posts with scheduled_time <= now and status scheduled.
    Stored times are treated as server-local naive datetimes."""
    now = datetime.now()
    posts = load_scheduled()
    due = []
    for p in posts:
        if p.get("status") != "scheduled":
            continue
        try:
            raw = p["scheduled_time"].replace("Z", "").split("+")[0].strip()
            st = datetime.fromisoformat(raw)
            if st.tzinfo:
                st = st.replace(tzinfo=None)
            if st <= now:
                due.append(p)
        except Exception:
            continue
    return due


def mark_published(post_id: str) -> None:
    """Mark a scheduled post as published (remove from store)."""
    posts = [p for p in load_scheduled() if p.get("id") != post_id]
    save_scheduled(posts)


def mark_failed(post_id: str, error: str) -> None:
    """Mark a scheduled post as failed (remove from store, optionally log)."""
    posts = [p for p in load_scheduled() if p.get("id") != post_id]
    save_scheduled(posts)
    logger.warning("Scheduled post failed", post_id=post_id, error=error)
