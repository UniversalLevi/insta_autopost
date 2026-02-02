"""
V2 Meta OAuth models and persistence helpers.

Data is stored in JSON files under data/ to stay consistent with the
existing project pattern, but kept fully isolated from v1.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Literal, Optional
from uuid import uuid4


DATA_DIR = Path(os.getenv("V2_DATA_DIR", "data"))
ACCOUNTS_FILE = DATA_DIR / "connected_accounts_v2.json"
LOG_FILE = DATA_DIR / "meta_oauth_logs_v2.jsonl"


StatusType = Literal["connected", "expired", "error", "disconnected"]


@dataclass
class ConnectedAccountV2:
    id: str
    user_id: str
    page_id: str
    instagram_id: str
    page_token_encrypted: str
    expires_at: Optional[datetime]
    status: StatusType
    created_at: datetime
    error_message: Optional[str] = None


def _atomic_write(path: Path, payload: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", dir=str(path.parent), delete=False, encoding="utf-8"
    ) as tf:
        json.dump(payload, tf, indent=2, ensure_ascii=False, default=str)
        temp_path = Path(tf.name)
    try:
        shutil.move(str(temp_path), str(path))
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise


def load_accounts() -> List[ConnectedAccountV2]:
    if not ACCOUNTS_FILE.exists():
        return []
    try:
        raw = json.loads(ACCOUNTS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    items = raw.get("accounts", [])
    accounts: List[ConnectedAccountV2] = []
    for item in items:
        try:
            expires = item.get("expires_at")
            expires_dt = datetime.fromisoformat(expires) if expires else None
            created = datetime.fromisoformat(item["created_at"])
            accounts.append(
                ConnectedAccountV2(
                    id=item["id"],
                    user_id=item["user_id"],
                    page_id=item["page_id"],
                    instagram_id=item["instagram_id"],
                    page_token_encrypted=item["page_token_encrypted"],
                    expires_at=expires_dt,
                    status=item.get("status", "connected"),
                    created_at=created,
                    error_message=item.get("error_message"),
                )
            )
        except Exception:
            continue
    return accounts


def save_accounts(accounts: List[ConnectedAccountV2]) -> None:
    payload = {
        "accounts": [
            {
                **asdict(a),
                "expires_at": a.expires_at.isoformat() if a.expires_at else None,
                "created_at": a.created_at.isoformat(),
            }
            for a in accounts
        ]
    }
    _atomic_write(ACCOUNTS_FILE, payload)


def upsert_account(
    user_id: str,
    page_id: str,
    instagram_id: str,
    page_token_encrypted: str,
    expires_at: Optional[datetime],
    status: StatusType,
    error_message: Optional[str] = None,
) -> ConnectedAccountV2:
    accounts = load_accounts()
    existing = None
    for a in accounts:
        if a.user_id == user_id and a.page_id == page_id and a.instagram_id == instagram_id:
            existing = a
            break
    if existing:
        existing.page_token_encrypted = page_token_encrypted
        existing.expires_at = expires_at
        existing.status = status
        existing.error_message = error_message
        account = existing
    else:
        account = ConnectedAccountV2(
            id=str(uuid4()),
            user_id=user_id,
            page_id=page_id,
            instagram_id=instagram_id,
            page_token_encrypted=page_token_encrypted,
            expires_at=expires_at,
            status=status,
            created_at=datetime.utcnow(),
            error_message=error_message,
        )
        accounts.append(account)
    save_accounts(accounts)
    return account


def list_accounts_for_user(user_id: str) -> List[ConnectedAccountV2]:
    return [a for a in load_accounts() if a.user_id == user_id]


def get_account_by_user_and_instagram(
    user_id: str, instagram_id: str
) -> Optional[ConnectedAccountV2]:
    """Resolve a single connected account by user and Instagram Business ID."""
    for a in load_accounts():
        if a.user_id == user_id and a.instagram_id == instagram_id and a.status == "connected":
            return a
    return None


def get_account_by_instagram_id(instagram_id: str) -> Optional[ConnectedAccountV2]:
    """Resolve connected account by Instagram Business ID (for webhook routing)."""
    for a in load_accounts():
        if a.instagram_id == instagram_id and a.status == "connected":
            return a
    return None


def mark_disconnected(account_id: str, error_message: Optional[str] = None) -> None:
    accounts = load_accounts()
    changed = False
    for a in accounts:
        if a.id == account_id:
            a.status = "disconnected"
            a.error_message = error_message
            changed = True
            break
    if changed:
        save_accounts(accounts)


def log_meta_oauth_event(
    user_id: str,
    action: str,
    result: str,
    error: Optional[str] = None,
    extra: Optional[Dict] = None,
) -> None:
    """
    Append a JSON log line to meta_oauth_logs_v2.
    """
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    record: Dict[str, object] = {
        "timestamp": datetime.utcnow().isoformat(),
        "user_id": user_id,
        "action": action,
        "result": result,
        "error": error,
    }
    if extra:
        record.update(extra)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

