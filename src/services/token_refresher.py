"""Automatic token refresh for OAuth-connected Instagram accounts."""

import threading
from datetime import datetime, timedelta
from typing import List, Optional, Tuple, Any

import requests

from ..models.account import Account
from ..utils.config import config_manager
from ..utils.logger import get_logger
from ..auth.meta_oauth import META_APP_ID, META_APP_SECRET, META_REDIRECT_URI
from ..auth.oauth_helper import OAuthHelper

logger = get_logger(__name__)

GRAPH_BASE = "https://graph.facebook.com/v18.0"
REFRESH_IF_EXPIRES_WITHIN_DAYS = 20  # Refresh when ≤20 days left (token "older than 40 days")


def _is_eligible_for_refresh(account: Account) -> bool:
    """True if OAuth-connected with user token and token older than 40 days (≤20 days left)."""
    if not account.expires_at or not account.page_id or not account.user_access_token:
        return False
    try:
        s = account.expires_at.replace("Z", "").strip()[:19]
        exp = datetime.strptime(s, "%Y-%m-%dT%H:%M:%S")
    except Exception as e:
        logger.warning("Token refresh: invalid expires_at", account_id=account.account_id, expires_at=account.expires_at, error=str(e))
        return False
    now = datetime.utcnow()
    delta = exp - now
    days_left = delta.total_seconds() / 86400
    return days_left <= REFRESH_IF_EXPIRES_WITHIN_DAYS


def _get_page_token_for_page_id(user_token: str, page_id: str) -> str:
    """Fetch page access_token for given page_id from /me/accounts."""
    r = requests.get(
        f"{GRAPH_BASE}/me/accounts",
        params={
            "access_token": user_token,
            "fields": "id,access_token",
        },
        timeout=30,
    )
    data = r.json()
    if "error" in data:
        err = data["error"]
        msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
        raise ValueError(f"Failed to fetch pages: {msg}")
    for p in data.get("data", []):
        if p.get("id") == page_id and p.get("access_token"):
            return p["access_token"]
    raise ValueError(f"Page {page_id} not found or missing access_token")


def _refresh_one(helper: OAuthHelper, account: Account) -> Optional[Account]:
    """Refresh a single account. Returns updated Account or None on failure."""
    try:
        logger.info("Token refresh: exchanging user token", account_id=account.account_id)
        result = helper.exchange_for_long_lived_token(account.user_access_token)
    except Exception as e:
        logger.exception(
            "Token refresh: fb_exchange_token failed",
            account_id=account.account_id,
            error=str(e),
        )
        return None

    new_user_token = result.get("access_token")
    expires_in = result.get("expires_in")
    if not new_user_token:
        logger.error("Token refresh: no access_token in response", account_id=account.account_id)
        return None

    try:
        page_token = _get_page_token_for_page_id(new_user_token, account.page_id)
    except Exception as e:
        logger.exception(
            "Token refresh: failed to get page token",
            account_id=account.account_id,
            page_id=account.page_id,
            error=str(e),
        )
        return None

    sec = int(expires_in or 0)
    expires_at = (datetime.utcnow() + timedelta(seconds=sec)).strftime("%Y-%m-%dT%H:%M:%SZ")

    d = account.dict()
    d["access_token"] = page_token
    d["expires_at"] = expires_at
    d["user_access_token"] = new_user_token
    updated = Account(**d)

    logger.info(
        "Token refresh: success",
        account_id=account.account_id,
        expires_at=expires_at,
    )
    return updated


def run_token_refresh() -> Tuple[List[str], List[Account]]:
    """
    Find OAuth accounts with tokens older than 40 days, refresh via fb_exchange_token,
    update storage. Returns (refreshed_account_ids, full_updated_accounts_list).
    """
    if not META_APP_ID or not META_APP_SECRET:
        logger.warning("Token refresh: META_APP_ID or META_APP_SECRET not set; skipping")
        return [], []

    helper = OAuthHelper(
        app_id=META_APP_ID,
        app_secret=META_APP_SECRET,
        redirect_uri=META_REDIRECT_URI or "http://localhost:8000/auth/meta/callback",
        api_version="v18.0",
    )

    accounts = config_manager.load_accounts()
    eligible = [a for a in accounts if _is_eligible_for_refresh(a)]
    if not eligible:
        logger.info("Token refresh: no eligible accounts (tokens older than 40 days)")
        return [], accounts

    logger.info("Token refresh: eligible accounts", count=len(eligible), account_ids=[a.account_id for a in eligible])
    by_id = {a.account_id: a for a in accounts}
    refreshed_ids: List[str] = []

    for acc in eligible:
        updated = _refresh_one(helper, acc)
        if updated is not None:
            by_id[acc.account_id] = updated
            refreshed_ids.append(acc.account_id)

    if not refreshed_ids:
        logger.warning("Token refresh: no accounts refreshed")
        return [], accounts

    updated_list = [by_id.get(a.account_id, a) for a in accounts]
    try:
        config_manager.save_accounts(updated_list)
        logger.info("Token refresh: storage updated", refreshed=refreshed_ids)
    except Exception as e:
        logger.exception("Token refresh: failed to save accounts", error=str(e))
        return [], accounts

    return refreshed_ids, updated_list


_refresh_stop = threading.Event()
_refresh_thread: Optional[threading.Thread] = None


def _daily_refresh_loop(app: Any, interval_seconds: int = 86400) -> None:
    """Run token refresh every interval_seconds (default 24h). First run after 60s."""
    import time
    logger.info("Token refresh daily job started", interval_seconds=interval_seconds)
    first = True
    while not _refresh_stop.is_set():
        if not first:
            try:
                _refresh_stop.wait(interval_seconds)
            except Exception as e:
                logger.warning("Token refresh wait error", error=str(e))
                time.sleep(min(3600, interval_seconds))
        first = False
        if _refresh_stop.is_set():
            break
        try:
            refreshed_ids, updated_list = run_token_refresh()
            if refreshed_ids and app and getattr(app, "account_service", None):
                app.account_service.update_accounts(updated_list)
                logger.info("Token refresh: app account_service updated", refreshed=refreshed_ids)
        except Exception as e:
            logger.exception("Token refresh daily job error", error=str(e))


def start_daily_token_refresh_job(app: Any, interval_seconds: int = 86400) -> None:
    """Start background thread that runs token refresh daily. Idempotent."""
    global _refresh_thread
    if _refresh_thread is not None:
        return
    _refresh_stop.clear()
    _refresh_thread = threading.Thread(
        target=_daily_refresh_loop,
        args=(app, interval_seconds),
        daemon=True,
        name="token-refresher",
    )
    _refresh_thread.start()
    logger.info("Daily token refresh job scheduled", interval_seconds=interval_seconds)


def stop_daily_token_refresh_job() -> None:
    """Stop the daily token refresh job."""
    global _refresh_thread
    _refresh_stop.set()
    if _refresh_thread is not None:
        # Don't wait too long - daemon thread will exit with main process
        _refresh_thread.join(timeout=2)
        if _refresh_thread.is_alive():
            logger.warning("Token refresh thread still alive after timeout, continuing shutdown")
        _refresh_thread = None
    logger.info("Daily token refresh job stopped")
