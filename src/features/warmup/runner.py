"""
Warm-up runner - orchestrates one automation cycle.
"""

import random
import time
from datetime import datetime
from typing import Dict, Any, Optional

from ...utils.logger import get_logger
from .store import get_plan, update_plan
from .config import get_automation_config
from .plans import get_tasks_for_day, get_automatable_tasks
from .actions import discover_post_urls, execute_task, is_success_result
from .progress import set_progress, clear_progress, request_stop, is_stop_requested, clear_stop_request

logger = get_logger(__name__)


def _get_proxy_url(account) -> Optional[str]:
    """Get proxy URL: global first, then per-account."""
    proxy_url = None
    try:
        from ...utils.config import config_manager
        settings = config_manager.load_settings()
        dproxy = getattr(settings.proxies, "default_proxy", None) if settings.proxies else None
        if dproxy and dproxy.enabled and dproxy.host and dproxy.port:
            proxy_url = dproxy.proxy_url()
    except Exception:
        pass
    if not proxy_url and account.proxy and account.proxy.enabled:
        proxy_url = account.proxy.proxy_url
    return proxy_url


def run_one_cycle(
    account_id: str,
    account_service,
    browser_wrapper,
) -> Dict[str, Any]:
    """
    Run one warm-up automation cycle. Returns {actions, errors, tasks_done, message}.
    """
    result = {"account_id": account_id, "actions": 0, "errors": 0, "tasks_done": [], "message": None}

    plan = get_plan(account_id)
    if not plan or plan.status != "active":
        result["message"] = "No active warm-up plan. Start warm-up first."
        return result

    cfg = get_automation_config(account_id)
    if not cfg.get("automation_enabled"):
        result["message"] = "Automation is disabled. Enable it in Warm-up automation settings."
        return result

    if not browser_wrapper:
        result["message"] = "Browser automation is not available. Start the app with browser enabled."
        return result

    try:
        account = account_service.get_account(account_id)
    except Exception:
        result["message"] = "Account not found."
        return result

    clear_stop_request(account_id)
    set_progress(account_id, "starting", "Starting warm-up automation...")

    username = account.username or ""
    password = getattr(account, "password", None) or ""
    proxy_url = _get_proxy_url(account)

    day = plan.current_day
    tasks = get_tasks_for_day(day)
    automatable = get_automatable_tasks(day)

    # Build completed counts
    completed = plan.completed_tasks or []
    completed_map = {}
    for c in completed:
        tid = c.get("task_id", "")
        completed_map[tid] = completed_map.get(tid, 0) + 1

    hashtags = cfg.get("target_hashtags") or ["explore"]
    if isinstance(hashtags, str):
        hashtags = [h.strip() for h in hashtags.split(",") if h.strip()]
    hashtags = [h.replace("#", "") for h in hashtags if h]

    # Discover URLs
    if is_stop_requested(account_id):
        result["message"] = "Stopped by user."
        set_progress(account_id, "done", result["message"])
        return result
    set_progress(account_id, "discovering", "Logging in and discovering posts from hashtags (this may take 1–2 min)...")
    try:
        post_urls, effective_proxy = discover_post_urls(
            browser_wrapper, account_id, hashtags, username, password, proxy_url
        )
        proxy_url = effective_proxy
    except Exception as e:
        err_str = str(e)
        logger.warning("Warm-up discovery failed", account_id=account_id, error=err_str)
        if "ERR_HTTP_RESPONSE_CODE_FAILURE" in err_str or "blocking browser" in err_str.lower() or "403" in err_str:
            result["message"] = (
                "Instagram is blocking browser access. Use a residential proxy in Settings, or run from a home network."
            )
        else:
            result["message"] = f"Discovery failed: {err_str[:200]}. Check login and hashtags."
        set_progress(account_id, "error", result["message"] or "Discovery failed")
        return result

    if not post_urls:
        result["message"] = (
            "No posts found. Ensure automation is enabled and try hashtags: love, photo, travel."
        )
        set_progress(account_id, "error", result["message"])
        return result

    set_progress(account_id, "discovering", f"Found {len(post_urls)} posts. Executing tasks...")
    random.shuffle(post_urls)

    # Execute automatable tasks
    for task in automatable:
        tid = task.id
        target = task.target
        done = completed_map.get(tid, 0)
        needed = max(0, target - done)
        if needed <= 0:
            continue

        to_do = min(needed, 3)
        task_label = task.label or tid.replace("_", " ").title()
        for i in range(to_do):
            if is_stop_requested(account_id):
                result["message"] = "Stopped by user."
                set_progress(account_id, "done", result["message"], actions=result["actions"], errors=result["errors"], tasks_done=result["tasks_done"])
                return result
            if i >= len(post_urls):
                break
            url = post_urls[i]
            set_progress(
                account_id, "executing",
                f"{task_label} ({i + 1}/{to_do})...",
                actions=result["actions"],
                errors=result["errors"],
                tasks_done=result["tasks_done"],
            )
            try:
                r = execute_task(
                    browser_wrapper, tid, account_id, url, username, password, proxy_url
                )
                if is_success_result(r):
                    completed.append({"task_id": tid, "done_at": datetime.utcnow().isoformat()})
                    update_plan(account_id, {
                        "completed_tasks": completed,
                        "last_action_time": datetime.utcnow().isoformat(),
                        "daily_actions_completed": {**(plan.daily_actions_completed or {}), f"day{day}": completed},
                    })
                    result["actions"] += 1
                    result["tasks_done"].append(tid)
                    time.sleep(random.uniform(2, 5))
                else:
                    result["errors"] += 1
            except Exception as e:
                logger.warning("Warm-up action failed", task=tid, error=str(e))
                result["errors"] += 1

    if result["actions"] > 0:
        logger.info("Warm-up automation ran", account_id=account_id, actions=result["actions"])
        msg = f"Done! {result['actions']} action(s) completed."
        set_progress(
            account_id, "done", msg,
            actions=result["actions"],
            errors=result["errors"],
            tasks_done=result["tasks_done"],
        )
    elif result["actions"] == 0 and result["errors"] == 0:
        result["message"] = "Today's automatable tasks are already done. Complete manual tasks or run again tomorrow."
        set_progress(account_id, "done", result["message"])
    elif result["actions"] == 0 and result["errors"] > 0:
        result["message"] = f"Ran but all {result['errors']} action(s) failed. Check login and Instagram limits."
        set_progress(account_id, "error", result["message"], errors=result["errors"])

    return result
