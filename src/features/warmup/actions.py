"""
Warm-up browser actions - discover URLs, execute like/comment/save/follow.
"""

import random
import time
from typing import List, Optional, Dict, Any

from ...utils.logger import get_logger

logger = get_logger(__name__)

WARM_COMMENTS = [
    "Nice!", "Love this", "Great post", "Amazing", "So good",
    "Love it", "Beautiful", "Cool", "Interesting", "Wow",
]


def discover_post_urls(
    browser_wrapper,
    account_id: str,
    hashtags: List[str],
    username: str,
    password: str,
    proxy_url: Optional[str],
    limit_per_hashtag: int = 5,
) -> tuple[List[str], Optional[str]]:
    """
    Discover post/reel URLs. Returns (urls, effective_proxy_url).
    On ERR_TUNNEL_CONNECTION_FAILED, retries without proxy.
    """
    try:
        urls = browser_wrapper.discover_post_urls_sync(
            account_id=account_id,
            hashtags=hashtags,
            limit_per_hashtag=limit_per_hashtag,
            username=username,
            password=password,
            proxy_url=proxy_url,
        )
        return urls or [], proxy_url
    except Exception as e:
        err_str = str(e)
        if proxy_url and "ERR_TUNNEL_CONNECTION_FAILED" in err_str:
            logger.info("Proxy failed, retrying without proxy", account_id=account_id)
            try:
                browser_wrapper.close_account(account_id)
                urls = browser_wrapper.discover_post_urls_sync(
                    account_id=account_id,
                    hashtags=hashtags,
                    limit_per_hashtag=limit_per_hashtag,
                    username=username,
                    password=password,
                    proxy_url=None,
                )
                return urls or [], None
            except Exception as e2:
                raise e2
        raise


def execute_task(
    browser_wrapper,
    task_id: str,
    account_id: str,
    post_url: str,
    username: str,
    password: str,
    proxy_url: Optional[str],
) -> Dict[str, Any]:
    """
    Execute a single automatable task. Returns action result dict.
    """
    tid = task_id.lower()
    if "like" in tid:
        return browser_wrapper.like_post_sync(
            account_id, post_url, username, password, proxy_url
        )
    if "save" in tid:
        return browser_wrapper.save_post_sync(
            account_id, post_url, username, password, proxy_url
        )
    if "comment" in tid:
        text = random.choice(WARM_COMMENTS)
        return browser_wrapper.comment_on_post_sync(
            account_id, post_url, text, username, password, proxy_url
        )
    if "follow" in tid:
        return browser_wrapper.follow_by_post_or_reel_sync(
            account_id, post_url, username, password, proxy_url
        )
    return {"status": "skipped", "error": f"Unknown task: {task_id}"}


def is_success_result(r: Dict[str, Any]) -> bool:
    """Check if action result indicates success."""
    status = r.get("status", "")
    return status in ("completed", "already_liked", "already_saved", "already_following")
