"""Background loop that publishes scheduled posts when due."""

import time
import threading
from datetime import datetime
from pydantic import HttpUrl

from src.models.post import PostMedia, Post, PostStatus
from src.services.scheduled_posts_store import (
    get_due_posts,
    mark_published,
    mark_failed,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)
_stop = threading.Event()
_thread: threading.Thread | None = None


def _build_post(raw: dict):
    """Build Post + PostMedia from stored scheduled post dict."""
    urls = raw["urls"]
    media_type = raw["media_type"]
    caption = raw.get("caption") or ""
    hashtags = raw.get("hashtags") or []

    if media_type == "carousel":
        children = []
        for url in urls:
            u = url.lower()
            ct = "video" if u.endswith((".mp4", ".mov", ".avi", ".mkv")) else "image"
            children.append(PostMedia(media_type=ct, url=HttpUrl(url)))
        media = PostMedia(media_type="carousel", children=children, caption=caption)
    else:
        # Infer from URL so .mp4 stored as "image" still uses video_url (fixes timeout)
        u = urls[0].lower()
        inferred = "video" if u.endswith((".mp4", ".mov", ".avi", ".mkv")) else "image"
        media = PostMedia(media_type=inferred, url=HttpUrl(urls[0]), caption=caption)

    post = Post(
        account_id=raw["account_id"],
        media=media,
        caption=caption,
        hashtags=hashtags,
        scheduled_time=None,
        status=PostStatus.PENDING,
    )
    return post


def _run_once(app):
    if not app or not getattr(app, "posting_service", None):
        return
    due = get_due_posts()
    for raw in due:
        pid = raw.get("id")
        try:
            post = _build_post(raw)
            app.posting_service.publish_post(post)
            mark_published(pid)
            logger.info("Scheduled post published", post_id=pid, account_id=raw["account_id"])
        except Exception as e:
            logger.exception("Scheduled post publish failed", post_id=pid, error=str(e))
            mark_failed(pid, str(e))


def _loop(app, interval_seconds: int = 60):
    while not _stop.is_set():
        try:
            _run_once(app)
        except Exception as e:
            logger.warning("Scheduled publisher cycle error", error=str(e))
        _stop.wait(interval_seconds)


def start_scheduled_publisher(app, interval_seconds: int = 60) -> None:
    global _thread
    if _thread is not None:
        return
    _stop.clear()
    _thread = threading.Thread(
        target=_loop,
        args=(app, interval_seconds),
        daemon=True,
        name="scheduled-publisher",
    )
    _thread.start()
    logger.info("Scheduled post publisher started", interval_seconds=interval_seconds)


def stop_scheduled_publisher() -> None:
    global _thread
    _stop.set()
    if _thread is not None:
        _thread.join(timeout=5)
        _thread = None
    logger.info("Scheduled post publisher stopped")
