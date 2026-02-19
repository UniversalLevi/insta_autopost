"""
DM Inbox Store - Persist incoming DMs for inbox UI display.
Isolated module. No changes to existing AI DM logic.
"""

import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from ...utils.logger import get_logger

logger = get_logger(__name__)

DATA_DIR = Path("data")
INBOX_FILE = DATA_DIR / "dm_inbox.json"
RETENTION_DAYS = 30


def _ensure_dir() -> None:
    DATA_DIR.mkdir(exist_ok=True, parents=True)


def _load() -> Dict[str, Any]:
    _ensure_dir()
    if not INBOX_FILE.exists():
        return {"conversations": {}, "messages": []}
    try:
        with open(INBOX_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Failed to load DM inbox", error=str(e))
        return {"conversations": {}, "messages": []}


def _save(data: Dict[str, Any]) -> None:
    _ensure_dir()
    try:
        with open(INBOX_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error("Failed to save DM inbox", error=str(e))


def _conv_key(account_id: str, user_id: str) -> str:
    return f"{account_id}:{user_id}"


def get_inbox_stats() -> Dict[str, Any]:
    """Return basic stats for config verification (file exists, message count, conversation count)."""
    data = _load()
    messages = data.get("messages") or []
    conversations = data.get("conversations") or {}
    return {
        "file_exists": INBOX_FILE.exists(),
        "message_count": len(messages),
        "conversation_count": len(conversations),
    }


def add_message(
    account_id: str,
    user_id: str,
    username: str,
    message: str,
    message_id: Optional[str] = None,
    ai_reply_suggested: Optional[str] = None,
    sent_at: Optional[str] = None,
    status: str = "received",
) -> None:
    """
    Add an incoming DM to the inbox store.
    Call from webhook after extracting message data.
    """
    data = _load()
    now = datetime.utcnow().isoformat()
    key = _conv_key(str(account_id or ""), str(user_id or ""))

    aid, uid = str(account_id or ""), str(user_id or "")
    entry = {
        "account_id": aid,
        "user_id": uid,
        "username": username or uid,
        "message": message[:2000] if message else "",
        "timestamp": now,
        "message_id": message_id,
        "ai_reply_suggested": ai_reply_suggested,
        "sent_at": sent_at,
        "status": status,
    }
    data["messages"] = data.get("messages") or []
    data["messages"].append(entry)

    conversations = data.get("conversations") or {}
    if key not in conversations:
        conversations[key] = {
            "account_id": aid,
            "user_id": uid,
            "username": username or uid,
            "last_message": message[:200] if message else "",
            "last_timestamp": now,
            "message_count": 0,
            "ai_reply_suggested": ai_reply_suggested,
            "status": status,
        }
    conv = conversations[key]
    conv["last_message"] = (message[:200] + ("..." if len(message) > 200 else "")) if message else ""
    conv["last_timestamp"] = now
    conv["message_count"] = conv.get("message_count", 0) + 1
    if ai_reply_suggested is not None:
        conv["ai_reply_suggested"] = ai_reply_suggested
    conv["status"] = status

    data["conversations"] = conversations

    cutoff = (datetime.utcnow() - timedelta(days=RETENTION_DAYS)).isoformat()
    data["messages"] = [m for m in data["messages"] if m.get("timestamp", "") >= cutoff]
    data["updated_at"] = now

    _save(data)


def list_conversations(account_id: str) -> List[Dict[str, Any]]:
    """List conversations for an account, newest first."""
    data = _load()
    convs = data.get("conversations") or {}
    aid = str(account_id) if account_id is not None else ""
    result = []
    for k, v in convs.items():
        if str(v.get("account_id") or "") == aid:
            result.append(dict(v))
    result.sort(key=lambda x: x.get("last_timestamp", ""), reverse=True)
    return result


def get_messages(account_id: str, user_id: str) -> List[Dict[str, Any]]:
    """Get all messages for a conversation."""
    data = _load()
    msgs = data.get("messages") or []
    aid = str(account_id) if account_id is not None else ""
    uid = str(user_id) if user_id is not None else ""
    result = [
        m for m in msgs
        if str(m.get("account_id") or "") == aid and str(m.get("user_id") or "") == uid
    ]
    result.sort(key=lambda x: x.get("timestamp", ""))
    return result


def update_suggestion(account_id: str, user_id: str, ai_reply_suggested: str) -> bool:
    """Update AI suggested reply for the latest message in conversation."""
    data = _load()
    key = _conv_key(str(account_id or ""), str(user_id or ""))
    convs = data.get("conversations") or {}
    conv_updated = False
    if key in convs:
        convs[key]["ai_reply_suggested"] = ai_reply_suggested
        data["conversations"] = convs
        conv_updated = True
    aid, uid = str(account_id or ""), str(user_id or "")
    msgs = data.get("messages") or []
    msg_updated = False
    for m in reversed(msgs):
        if str(m.get("account_id") or "") == aid and str(m.get("user_id") or "") == uid:
            m["ai_reply_suggested"] = ai_reply_suggested
            msg_updated = True
            break
    if conv_updated or msg_updated:
        data["updated_at"] = datetime.utcnow().isoformat()
        _save(data)
    return conv_updated or msg_updated


def mark_sent(account_id: str, user_id: str) -> None:
    """Mark that a reply was sent to this user."""
    data = _load()
    key = _conv_key(str(account_id or ""), str(user_id or ""))
    convs = data.get("conversations") or {}
    if key in convs:
        convs[key]["status"] = "sent"
        convs[key]["ai_reply_suggested"] = None
    data["conversations"] = convs
    data["updated_at"] = datetime.utcnow().isoformat()
    _save(data)
