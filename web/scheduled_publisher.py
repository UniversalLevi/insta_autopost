"""Background loop that publishes scheduled posts when due."""

import time
import threading
from datetime import datetime
from urllib.parse import urlparse, urlunparse
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


def _rewrite_upload_url_to_current_base(url: str) -> str:
    """If URL is our app's /uploads/ path, rewrite to use current public base.
    Prefers BASE_URL/APP_URL (your server) so scheduling works reliably without tunnel URLs."""
    try:
        parsed = urlparse(url)
        path = parsed.path or ""
        if not path.startswith("/uploads/"):
            return url
        import os
        # Prefer your server: BASE_URL or APP_URL (no request available in background)
        base = (os.getenv("BASE_URL") or os.getenv("APP_URL") or "").strip().rstrip("/")
        if not base:
            from web.cloudflare_helper import get_current_public_base_url
            base = get_current_public_base_url()
        if not base:
            return url
        base = base.rstrip("/")
        query = f"?{parsed.query}" if parsed.query else ""
        return f"{base}{path}{query}"
    except Exception:
        return url


def _build_post(raw: dict):
    """Build Post + PostMedia from stored scheduled post dict."""
    raw_urls = raw["urls"]
    # Rewrite /uploads/ URLs to current public base so tunnel URL changes don't break scheduled posts
    urls = [_rewrite_upload_url_to_current_base(u) for u in raw_urls]
    media_type = raw["media_type"]
    caption = raw.get("caption") or ""
    hashtags = raw.get("hashtags") or []

    def _infer_media_type(url: str) -> str:
        """Infer media type from URL extension (handles query parameters)."""
        # Remove query parameters and fragment for extension check
        url_clean = url.split("?")[0].split("#")[0].lower()
        if url_clean.endswith((".mp4", ".mov", ".avi", ".mkv", ".webm")):
            return "video"
        return "image"

    if media_type == "carousel":
        children = []
        for url in urls:
            ct = _infer_media_type(url)
            children.append(PostMedia(media_type=ct, url=HttpUrl(url)))
        media = PostMedia(media_type="carousel", children=children, caption=caption)
    else:
        # Preserve video/reels type if explicitly stored
        if media_type in ("reels", "video"):
            inferred = media_type
        else:
            # Infer from URL so .mp4 stored as "image" still uses video_url (fixes timeout)
            # This handles URLs with query parameters like ?t=timestamp
            inferred = _infer_media_type(urls[0])
        
        media = PostMedia(media_type=inferred, url=HttpUrl(urls[0]), caption=caption)
        
        logger.info(
            "Scheduled post media type",
            stored_type=media_type,
            final_type=inferred,
            url_preview=urls[0][:80],
        )

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
        logger.warning("Scheduled publisher: app or posting_service not available")
        return
    due = get_due_posts()
    if not due:
        logger.debug("Scheduled publisher: No due posts found")
        return
    logger.info("Scheduled publisher: Found due posts", count=len(due))
    for raw in due:
        pid = raw.get("id")
        account_id = raw.get("account_id")
        media_type = raw.get("media_type")
        scheduled_time = raw.get("scheduled_time")
        urls = raw.get("urls", [])
        
        logger.info(
            "Processing scheduled post",
            post_id=pid,
            account_id=account_id,
            media_type=media_type,
            scheduled_time=scheduled_time,
            url_preview=urls[0][:80] if urls else "no-url",
        )

        # Verify account still exists before attempting publish
        try:
            app.account_service.get_account(account_id)
        except Exception as acc_err:
            err = "Account no longer exists or was removed"
            logger.warning("Skipping scheduled post: account not found", post_id=pid, account_id=account_id, error=str(acc_err))
            mark_failed(pid, err)
            continue

        try:
            post = _build_post(raw)
            logger.info(
                "Built post from scheduled data",
                post_id=pid,
                media_type=post.media.media_type,
                url=post.media.url if hasattr(post.media, 'url') else 'carousel',
            )
            
            app.posting_service.publish_post(post)
            
            # After successful publishing, save Auto-DM config if enabled
            if raw.get("auto_dm_enabled") and raw.get("auto_dm_link") and post.instagram_media_id:
                try:
                    if app.comment_to_dm_service:
                        app.comment_to_dm_service.post_dm_config.set_post_dm_file(
                            account_id=raw["account_id"],
                            media_id=str(post.instagram_media_id),
                            file_url=raw.get("auto_dm_link"),
                            trigger_mode=raw.get("auto_dm_mode", "AUTO"),
                            trigger_word=raw.get("auto_dm_trigger"),
                            ai_enabled=raw.get("auto_dm_ai_enabled", False),
                        )
                        logger.info(
                            "Auto-DM config saved for scheduled post",
                            post_id=pid,
                            account_id=raw["account_id"],
                            media_id=str(post.instagram_media_id),
                        )
                except Exception as dm_err:
                    logger.warning(
                        "Failed to save Auto-DM config for scheduled post",
                        post_id=pid,
                        error=str(dm_err),
                    )
            
            mark_published(pid)
            logger.info(
                "Scheduled post published successfully",
                post_id=pid,
                account_id=account_id,
                media_type=media_type,
                instagram_media_id=post.instagram_media_id,
            )
        except Exception as e:
            error_msg = str(e)
            logger.exception(
                "Scheduled post publish failed",
                post_id=pid,
                account_id=account_id,
                media_type=media_type,
                error=error_msg,
            )
            mark_failed(pid, error_msg)


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
        # Don't wait too long - daemon thread will exit with main process
        _thread.join(timeout=2)
        if _thread.is_alive():
            logger.warning("Scheduled publisher thread still alive after timeout, continuing shutdown")
        _thread = None
    logger.info("Scheduled post publisher stopped")
