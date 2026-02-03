"""
Warm-Up Automation - Executes automatable warm-up tasks via browser.
"""

import random
import time
from typing import Dict, List, Any, Optional

from ...utils.logger import get_logger
from .warmup_store import get_warmup_plan
from .warmup_engine import WarmupEngine
from .warmup_automation_config import get_config
from .day_plans import WARMUP_DAY_PLANS, MAX_ACTIONS_PER_HOUR

logger = get_logger(__name__)

WARM_COMMENTS = [
    "Nice!", "Love this", "Great post", "Amazing", "So good",
    "Love it", "Beautiful", "Cool", "Interesting", "Wow",
]


class WarmupAutomation:
    """Runs automated warm-up actions for accounts in active warm-up."""

    def __init__(self, account_service, browser_wrapper=None):
        self.account_service = account_service
        self.browser_wrapper = browser_wrapper
        self.engine = WarmupEngine()

    def run_for_account(self, account_id: str) -> Dict[str, Any]:
        """Run one automation cycle for an account. Returns summary with optional message."""
        result = {"account_id": account_id, "actions": 0, "errors": 0, "tasks_done": [], "message": None}
        try:
            return self._run_for_account_impl(account_id, result)
        except Exception as e:
            logger.exception("Warmup automation failed", account_id=account_id, error=str(e))
            result["message"] = f"Error: {e!s}"
            return result

    def _run_for_account_impl(self, account_id: str, result: Dict[str, Any]) -> Dict[str, Any]:
        plan = get_warmup_plan(account_id)
        if not plan or plan.get("status") != "active":
            result["message"] = "No active warm-up plan. Start warm-up first."
            return result
        cfg = get_config(account_id)
        if not cfg.get("automation_enabled"):
            result["message"] = "Automation is disabled. Enable it in Warm-up automation settings."
            return result
        if not self.browser_wrapper:
            logger.warning("Warmup automation skipped: no browser", account_id=account_id)
            result["message"] = "Browser automation is not available. Start the app with browser enabled."
            return result
        try:
            account = self.account_service.get_account(account_id)
        except Exception:
            result["message"] = "Account not found."
            return result
        username = account.username or ""
        password = getattr(account, "password", None) or ""
        proxy_url = None
        if account.proxy and account.proxy.enabled:
            proxy_url = account.proxy.proxy_url
        day = plan.get("current_day", 1)
        tasks = WARMUP_DAY_PLANS.get(day, [])
        today = self.engine.get_today_plan(account_id)
        if not today:
            result["message"] = "Could not load today's plan."
            return result
        completed_map = {t["id"]: t.get("done_count", 0) for t in today.get("tasks", [])}
        hashtags = cfg.get("target_hashtags") or ["explore"]
        post_urls = []
        try:
            post_urls = self.browser_wrapper.discover_post_urls_sync(
                account_id, hashtags, limit_per_hashtag=5,
                username=username, password=password, proxy_url=proxy_url,
            )
        except Exception as e:
            logger.warning("Warmup discovery failed", account_id=account_id, error=str(e))
            result["message"] = f"Discovery failed: {e}. Check login and hashtags."
            return result
        if not post_urls:
            result["message"] = "No posts found for target hashtags. Try different hashtags or try again later."
            return result
        random.shuffle(post_urls)
        for task_def in tasks:
            tid = task_def.get("id", "")
            target = task_def.get("target", 1)
            manual = task_def.get("manual", True)
            if manual:
                continue
            done = completed_map.get(tid, 0)
            needed = max(0, target - done)
            if needed <= 0:
                continue
            to_do = min(needed, 3)  # Max 3 per run to avoid rate limits
            for i in range(to_do):
                if i >= len(post_urls):
                    break
                url = post_urls[i]
                try:
                    if "like" in tid.lower():
                        r = self.browser_wrapper.like_post_sync(
                            account_id, url, username, password, proxy_url
                        )
                    elif "save" in tid.lower():
                        r = self.browser_wrapper.save_post_sync(
                            account_id, url, username, password, proxy_url
                        )
                    elif "comment" in tid.lower():
                        text = random.choice(WARM_COMMENTS)
                        r = self.browser_wrapper.comment_on_post_sync(
                            account_id, url, text, username, password, proxy_url
                        )
                    else:
                        continue
                    if r.get("status") in ("completed", "already_liked", "already_saved", "already_following"):
                        self.engine.mark_task_done(account_id, tid, count=1)
                        result["actions"] += 1
                        result["tasks_done"].append(tid)
                        time.sleep(random.uniform(2, 5))
                    else:
                        result["errors"] += 1
                except Exception as e:
                    logger.warning("Warmup action failed", task=tid, error=str(e))
                    result["errors"] += 1
        if result["actions"] > 0:
            logger.info("Warmup automation ran", account_id=account_id, actions=result["actions"])
        elif result["actions"] == 0 and result["errors"] == 0:
            result["message"] = "Today's automatable tasks are already done (like/comment/save). Complete manual tasks or run again tomorrow."
        elif result["actions"] == 0 and result["errors"] > 0:
            result["message"] = f"Ran but all {result['errors']} action(s) failed. Check login and Instagram limits."
        return result
