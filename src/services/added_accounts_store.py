"""
Store for Instagram accounts added via OAuth (Generate access tokens flow).
Persists account details in SQLite with same structure as accounts.yaml entry:
account_id, username, access_token, basic_display_token, password, proxy, webhook_subscription.
"""

import json
import sqlite3
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

from src.utils.logger import get_logger

logger = get_logger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DB_PATH = DATA_DIR / "instagram_added_accounts.db"


def _get_conn() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _init_db() -> None:
    """Create table if not exists."""
    conn = _get_conn()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS added_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id TEXT NOT NULL UNIQUE,
                username TEXT NOT NULL,
                access_token TEXT NOT NULL,
                basic_display_token TEXT,
                password TEXT,
                proxy TEXT,
                webhook_subscription INTEGER NOT NULL DEFAULT 1,
                page_id TEXT,
                user_access_token TEXT,
                expires_at TEXT,
                instagram_business_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.commit()
    finally:
        conn.close()


def upsert_added_account(
    account_id: str,
    username: str,
    access_token: str,
    basic_display_token: Optional[str] = None,
    password: Optional[str] = None,
    proxy: Optional[Dict[str, Any]] = None,
    webhook_subscription: bool = True,
    page_id: Optional[str] = None,
    user_access_token: Optional[str] = None,
    expires_at: Optional[str] = None,
    instagram_business_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Insert or update an added Instagram account (same fields as second image).
    Called after OAuth callback or when generating token.
    """
    _init_db()
    now = datetime.utcnow().isoformat() + "Z"
    proxy_json = json.dumps(proxy) if proxy is not None else None

    conn = _get_conn()
    try:
        conn.execute(
            """
            INSERT INTO added_accounts (
                account_id, username, access_token, basic_display_token, password,
                proxy, webhook_subscription, page_id, user_access_token, expires_at,
                instagram_business_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(account_id) DO UPDATE SET
                username = excluded.username,
                access_token = excluded.access_token,
                basic_display_token = excluded.basic_display_token,
                password = excluded.password,
                proxy = excluded.proxy,
                page_id = excluded.page_id,
                user_access_token = excluded.user_access_token,
                expires_at = excluded.expires_at,
                instagram_business_id = excluded.instagram_business_id,
                updated_at = excluded.updated_at
            """,
            (
                account_id,
                username,
                access_token,
                basic_display_token,
                password,
                proxy_json,
                1 if webhook_subscription else 0,
                page_id,
                user_access_token,
                expires_at,
                instagram_business_id,
                now,
                now,
            ),
        )
        conn.commit()
        logger.info("Upserted added account", account_id=account_id, username=username)
        return get_added_account_by_id(account_id) or {}
    finally:
        conn.close()


def get_added_account_by_id(account_id: str) -> Optional[Dict[str, Any]]:
    """Get one added account by account_id."""
    _init_db()
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM added_accounts WHERE account_id = ?", (account_id,)
        ).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def list_added_accounts() -> List[Dict[str, Any]]:
    """List all added Instagram accounts (for Generate access tokens UI)."""
    _init_db()
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM added_accounts ORDER BY created_at DESC"
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def sync_from_config_if_empty(load_accounts_fn, save_cb=None) -> None:
    """
    If added_accounts table is empty, populate from config (accounts.yaml)
    so existing accounts appear in Generate access tokens list.
    load_accounts_fn: callable that returns list of account-like dicts (e.g. config_manager.load_accounts).
    save_cb: optional callable(account_dict) to persist (e.g. upsert_added_account).
    """
    _init_db()
    conn = _get_conn()
    try:
        count = conn.execute("SELECT COUNT(*) FROM added_accounts").fetchone()[0]
        if count > 0:
            return
    finally:
        conn.close()
    accounts = load_accounts_fn()
    if not accounts:
        return
    for acc in accounts:
        d = acc.dict() if hasattr(acc, "dict") else acc
        account_id = d.get("account_id")
        username = d.get("username")
        access_token = d.get("access_token")
        if not account_id or not username or not access_token:
            continue
        proxy = d.get("proxy")
        if hasattr(proxy, "dict"):
            proxy = proxy.dict()
        upsert_added_account(
            account_id=account_id,
            username=username,
            access_token=access_token,
            basic_display_token=d.get("basic_display_token"),
            password=d.get("password"),
            proxy=proxy,
            webhook_subscription=True,
            page_id=d.get("page_id"),
            user_access_token=d.get("user_access_token"),
            expires_at=d.get("expires_at"),
            instagram_business_id=d.get("instagram_business_id"),
        )
    logger.info("Synced existing accounts into added_accounts DB", count=len(accounts))


def _row_to_dict(row: Optional[sqlite3.Row]) -> Optional[Dict[str, Any]]:
    if row is None:
        return None
    d = dict(row)
    if d.get("proxy"):
        try:
            d["proxy"] = json.loads(d["proxy"])
        except (TypeError, json.JSONDecodeError):
            d["proxy"] = {"enabled": False}
    else:
        d["proxy"] = {"enabled": False}
    d["webhook_subscription"] = bool(d.get("webhook_subscription", 1))
    return d


def set_webhook_subscription(account_id: str, enabled: bool) -> bool:
    """Toggle webhook subscription for an added account."""
    _init_db()
    conn = _get_conn()
    try:
        now = datetime.utcnow().isoformat() + "Z"
        cur = conn.execute(
            "UPDATE added_accounts SET webhook_subscription = ?, updated_at = ? WHERE account_id = ?",
            (1 if enabled else 0, now, account_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def delete_added_account(account_id: str) -> bool:
    """Remove an added account from the DB (and optionally from accounts.yaml; caller can do that)."""
    _init_db()
    conn = _get_conn()
    try:
        cur = conn.execute("DELETE FROM added_accounts WHERE account_id = ?", (account_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()
