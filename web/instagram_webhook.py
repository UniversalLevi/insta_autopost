"""Instagram webhook parsing and forwarding. Logs all payloads, forwards comments/messages to existing services."""

from typing import Any, Dict, List, Optional

from src.utils.logger import get_logger
from src.utils.exceptions import AccountError
from src.features.ai_dm import AIDMHandler
from src.features.ai_dm.dm_inbox_store import add_message as inbox_add_message, update_suggestion as inbox_update_suggestion, mark_sent as inbox_mark_sent

logger = get_logger(__name__)


def _normalize_payload(body: Any) -> Dict[str, Any]:
    """Ensure payload is a dict. Meta may send { object, entry } or [ { object, entry } ]."""
    if isinstance(body, list) and body:
        return body[0] if isinstance(body[0], dict) else {}
    return body if isinstance(body, dict) else {}


def _account_id_for_ig_business(ig_business_id: str, app: Any) -> Optional[str]:
    """Resolve InstaForge account_id from Instagram business account ID."""
    if not app or not getattr(app, "account_service", None):
        logger.warning(
            "Webhook account resolution failed",
            reason="no_app_or_service",
            ig_business_id=ig_business_id,
        )
        return None
    
    accounts = app.account_service.list_accounts()
    logger.debug(
        "Webhook account resolution",
        ig_business_id=ig_business_id,
        total_accounts=len(accounts),
    )
    
    for acc in accounts:
        # Try matching by instagram_business_id first
        if getattr(acc, "instagram_business_id", None) == ig_business_id:
            logger.info(
                "Webhook account matched by instagram_business_id",
                ig_business_id=ig_business_id,
                account_id=acc.account_id,
                username=acc.username,
            )
            return acc.account_id
        # Fallback: try matching by account_id (in case they're the same)
        if acc.account_id == ig_business_id:
            logger.info(
                "Webhook account matched by account_id",
                ig_business_id=ig_business_id,
                account_id=acc.account_id,
                username=acc.username,
            )
            return acc.account_id
    
    # If no match found, log available accounts for debugging
    logger.warning(
        "Webhook account not found",
        ig_business_id=ig_business_id,
        available_account_ids=[acc.account_id for acc in accounts],
        available_instagram_business_ids=[
            getattr(acc, "instagram_business_id", None) for acc in accounts
        ],
    )
    
    # Last resort: if only one account exists, use it (for development/testing)
    if len(accounts) == 1:
        logger.info(
            "Webhook using single account as fallback",
            ig_business_id=ig_business_id,
            account_id=accounts[0].account_id,
            username=accounts[0].username,
        )
        return accounts[0].account_id
    
    return None


def _webhook_comment_to_service_format(value: Dict[str, Any]) -> Dict[str, Any]:
    """Map webhook comment value to shape expected by process_new_comments_for_dm (id, text, username, from)."""
    from_obj = value.get("from") or {}
    media_obj = value.get("media") or {}
    return {
        "id": value.get("id"),
        "text": value.get("text") or "",
        "username": from_obj.get("username") or "",
        "from": {"id": from_obj.get("id"), "username": from_obj.get("username")},
        "media": {"id": media_obj.get("id")},
    }


def _media_id_from_comment_value(value: Dict[str, Any]) -> Optional[str]:
    """Get media ID from a comment change value."""
    media = value.get("media")
    if isinstance(media, dict) and media.get("id"):
        return str(media["id"])
    return None


def _process_incoming_dm_for_ai_reply(account_id: str, value: Dict[str, Any], app: Any) -> None:
    """
    Process incoming DM and send AI-generated reply if enabled.
    
    Args:
        account_id: Account identifier
        value: Webhook message value payload
        app: InstaForge app instance
    """
    logger.info(
        "AI_DM_WEBHOOK",
        action="processing_start",
        account_id=account_id,
        value_structure=list(value.keys()) if isinstance(value, dict) else "not_dict",
    )
    
    # Validate app instance and services
    if not app:
        logger.error(
            "AI_DM_WEBHOOK",
            action="error",
            reason="app_not_provided",
            account_id=account_id,
        )
        return
    
    if not hasattr(app, 'account_service') or not app.account_service:
        logger.error(
            "AI_DM_WEBHOOK",
            action="error",
            reason="account_service_not_initialized",
            account_id=account_id,
        )
        return
    
    # Check if AI DM is enabled for this account
    try:
        account = app.account_service.get_account(account_id)
    except Exception as e:
        logger.warning(
            "AI_DM_WEBHOOK",
            action="skipped",
            reason="account_not_found",
            account_id=account_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        return
    if not account:
        logger.warning(
            "AI_DM_WEBHOOK",
            action="skipped",
            reason="account_not_found",
            account_id=account_id,
        )
        return
    
    # Extract message data from webhook payload (before ai_dm check - needed for inbox store)
    # Instagram webhook structure can vary:
    # Option 1: value contains "from" and "message" directly
    # Option 2: value contains "messaging" -> "sender" and "message"
    # Option 3: value contains items array with messages
    # Option 4: value is the message itself with nested structure
    
    logger.debug(
        "AI_DM_WEBHOOK",
        action="parsing_payload",
        account_id=account_id,
        value_type=type(value).__name__,
        value_keys=list(value.keys()) if isinstance(value, dict) else None,
        value_preview=str(value)[:500] if isinstance(value, dict) else str(value)[:200],
    )
    
    # Instagram sends: "sender" (not "from") and "message" - support both
    from_obj = value.get("from") or value.get("sender") or {}
    message_obj = value.get("message") or {}
    
    # Try alternative structure (messaging array wrapper - value is { messaging: [ {...} ] })
    if not from_obj or not message_obj:
        messaging = value.get("messaging") or {}
        if isinstance(messaging, list) and messaging:
            messaging = messaging[0]
        if isinstance(messaging, dict):
            from_obj = messaging.get("sender") or messaging.get("from") or from_obj or {}
            message_obj = messaging.get("message") or message_obj or {}
    
    # Try items array structure (Instagram Direct Messages)
    if not from_obj or not message_obj:
        items = value.get("items") or []
        if items and isinstance(items, list) and len(items) > 0:
            item = items[0]
            if isinstance(item, dict):
                from_obj = item.get("from") or from_obj or {}
                message_obj = item.get("message") or message_obj or {}
    
    # Try direct message structure (some webhook formats)
    if not message_obj:
        # Sometimes message data is directly in value
        if value.get("text"):
            message_obj = value
        # Or in a "data" field
        elif value.get("data") and isinstance(value.get("data"), dict):
            message_obj = value.get("data")
    
    # Extract user_id - try multiple locations
    user_id = None
    if from_obj and isinstance(from_obj, dict):
        user_id = from_obj.get("id") or from_obj.get("user_id")
    # Fallback: try direct in value
    if not user_id:
        user_id = value.get("sender_id") or value.get("from_id") or value.get("user_id")
    
    # Extract message text - try multiple locations
    message_text = ""
    if message_obj and isinstance(message_obj, dict):
        message_text = (message_obj.get("text") or message_obj.get("message") or "").strip()
    # Fallback: try direct in value
    if not message_text:
        message_text = (value.get("text") or value.get("message") or "").strip()
    
    # Extract message_id
    message_id = None
    if message_obj and isinstance(message_obj, dict):
        message_id = message_obj.get("id") or message_obj.get("message_id") or message_obj.get("mid")
    if not message_id:
        message_id = value.get("id") or value.get("message_id") or value.get("mid")
    
    # Extract username (optional, for logging)
    username = ""
    if from_obj and isinstance(from_obj, dict):
        username = from_obj.get("username") or from_obj.get("name") or ""
    
    # Check if this is an outgoing/echo message (sent by us) - skip those
    # Instagram webhooks can include both incoming and outgoing messages
    is_outgoing = False
    if value.get("is_echo") is True:
        is_outgoing = True  # Message sent by our business account
    if value.get("direction") == "outgoing":
        is_outgoing = True
    # Also check if there's a "sent_by" field indicating we sent it
    if value.get("sent_by") and isinstance(value.get("sent_by"), dict):
        sent_by_id = value.get("sent_by").get("id")
        if sent_by_id == getattr(account, "instagram_business_id", None) or sent_by_id == account.account_id:
            is_outgoing = True
    
    logger.info(
        "AI_DM_WEBHOOK",
        action="extracted_data",
        account_id=account_id,
        has_user_id=bool(user_id),
        has_message_text=bool(message_text),
        has_username=bool(username),
        is_outgoing=is_outgoing,
        message_text_preview=message_text[:50] if message_text else None,
        user_id=user_id,
        username=username,
        message_id=message_id,
        value_keys=list(value.keys()) if isinstance(value, dict) else None,
        from_obj_keys=list(from_obj.keys()) if isinstance(from_obj, dict) else None,
        message_obj_keys=list(message_obj.keys()) if isinstance(message_obj, dict) else None,
    )
    
    # Skip outgoing messages (messages we sent)
    if is_outgoing:
        logger.info(
            "AI_DM_WEBHOOK",
            action="skipped",
            reason="outgoing_message",
            account_id=account_id,
            user_id=user_id,
            message_id=message_id,
        )
        return
    
    if not user_id:
        logger.warning(
            "AI_DM_WEBHOOK",
            action="skipped",
            reason="missing_user_id",
            account_id=account_id,
            value=value,
            value_keys=list(value.keys()) if isinstance(value, dict) else None,
        )
        return
    
    if not message_text:
        logger.info(
            "AI_DM_WEBHOOK",
            action="skipped",
            reason="empty_message",
            account_id=account_id,
            user_id=user_id,
            message_obj=message_obj,
        )
        return

    # Always store incoming DM for inbox UI
    try:
        inbox_add_message(
            account_id=account_id,
            user_id=str(user_id),
            username=username or "",
            message=message_text,
            message_id=str(message_id) if message_id else None,
        )
    except Exception as e:
        logger.warning("DM inbox store failed", error=str(e), account_id=account_id, user_id=user_id)

    # Check if AI DM is enabled
    ai_dm_enabled = False
    auto_send = True
    if hasattr(account, "ai_dm") and account.ai_dm:
        ai_dm_enabled = account.ai_dm.enabled
        auto_send = getattr(account.ai_dm, "auto_send", True)

    if not ai_dm_enabled:
        logger.info(
            "AI_DM_WEBHOOK",
            action="skipped",
            reason="ai_dm_disabled",
            account_id=account_id,
        )
        return

    logger.info(
        "AI_DM_WEBHOOK",
        action="processing",
        account_id=account_id,
        user_id=user_id,
        message_id=message_id,
        message_preview=message_text[:100],
        auto_send=auto_send,
    )

    # Initialize AI DM handler
    try:
        ai_handler = AIDMHandler()
        
        # Check if AI handler is available (has OpenAI API key)
        if not ai_handler.is_available():
            logger.warning(
                "AI_DM_WEBHOOK",
                action="skipped",
                reason="openai_not_configured",
                account_id=account_id,
                user_id=user_id,
                message_id=message_id,
                error="OPENAI_API_KEY not set or invalid",
            )
            return
        
        if not auto_send:
            # Review mode: generate AI reply, store for inbox, don't send
            reply_text = ai_handler.get_ai_reply(
                message=message_text,
                account_id=account_id,
                user_id=str(user_id),
                account_username=account.username,
            )
            if reply_text:
                try:
                    inbox_update_suggestion(account_id, str(user_id), reply_text)
                except Exception as e:
                    logger.warning("Inbox update suggestion failed", error=str(e))
            logger.info(
                "AI_DM_WEBHOOK",
                action="suggestion_stored",
                account_id=account_id,
                user_id=user_id,
                auto_send=False,
            )
            return

        # Auto-send mode: process and send
        result = ai_handler.process_incoming_dm(
            account_id=account_id,
            user_id=str(user_id),
            message_text=message_text,
            message_id=str(message_id) if message_id else None,
            account_username=account.username,
        )
    except Exception as e:
        logger.exception(
            "AI_DM_WEBHOOK",
            action="handler_error",
            account_id=account_id,
            user_id=user_id,
            message_id=message_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        return

    # Send reply if generated
    # Note: We send even if status is "fallback" - that's the fallback message
    reply_text = result.get("reply_text")
    if reply_text:
        try:
            # Validate we have required data
            if not user_id:
                logger.error(
                    "AI_DM_WEBHOOK",
                    action="send_failed",
                    reason="missing_user_id",
                    account_id=account_id,
                    message_id=message_id,
                )
                return
            
            try:
                client = app.account_service.get_client(account_id)
            except AccountError as e:
                logger.warning(
                    "AI_DM_WEBHOOK",
                    action="send_failed",
                    reason="client_not_found",
                    account_id=account_id,
                    user_id=user_id,
                    error=str(e),
                )
                return
            # Username is optional - send_direct_message can work with just recipient_id
            recipient_username = username or (from_obj.get("username") if isinstance(from_obj, dict) else "") or ""
            
            logger.info(
                "AI_DM_WEBHOOK",
                action="sending_reply",
                account_id=account_id,
                user_id=user_id,
                recipient_username=recipient_username or "N/A",
                has_recipient_id=bool(user_id),
                reply_length=len(reply_text),
                reply_preview=reply_text[:100],
                status=result.get("status"),
            )
            
            dm_result = client.send_direct_message(
                recipient_username=recipient_username,
                message=reply_text,
                recipient_id=str(user_id) if user_id else None,
            )
            
            if dm_result.get("status") == "success":
                try:
                    inbox_mark_sent(account_id, str(user_id))
                except Exception as e:
                    logger.warning("Inbox mark_sent failed", error=str(e))
                logger.info(
                    "AI_DM_WEBHOOK",
                    action="reply_sent",
                    account_id=account_id,
                    user_id=user_id,
                    message_id=message_id,
                    dm_id=dm_result.get("dm_id"),
                    reply_preview=reply_text[:100],
                )
            else:
                error_code = dm_result.get("error_code")
                error_msg = dm_result.get("error", "Unknown error")
                
                # Log specific error codes with helpful messages
                if error_code == 10:
                    logger.warning(
                        "AI_DM_WEBHOOK",
                        action="reply_failed",
                        reason="24_hour_window",
                        account_id=account_id,
                        user_id=user_id,
                        message_id=message_id,
                        error_code=error_code,
                        error=error_msg,
                        note="User must have messaged you first within 24 hours",
                    )
                elif error_code in [100, 200]:
                    logger.warning(
                        "AI_DM_WEBHOOK",
                        action="reply_failed",
                        reason="permission_or_user_not_found",
                        account_id=account_id,
                        user_id=user_id,
                        message_id=message_id,
                        error_code=error_code,
                        error=error_msg,
                        note="May need instagram_manage_messages permission or user not found",
                    )
                else:
                    logger.warning(
                        "AI_DM_WEBHOOK",
                        action="reply_failed",
                        account_id=account_id,
                        user_id=user_id,
                        message_id=message_id,
                        error=error_msg,
                        error_code=error_code,
                    )
        except Exception as e:
            logger.exception(
                "AI_DM_WEBHOOK",
                action="send_exception",
                account_id=account_id,
                user_id=user_id,
                message_id=message_id,
                error=str(e),
                error_type=type(e).__name__,
            )
    else:
        logger.warning(
            "AI_DM_WEBHOOK",
            action="no_reply",
            account_id=account_id,
            user_id=user_id,
            message_id=message_id,
            status=result.get("status"),
            reason=result.get("reason"),
            has_reply_text=bool(result.get("reply_text")),
            result_keys=list(result.keys()) if isinstance(result, dict) else None,
        )


def process_webhook_payload(body: Any, app: Any) -> None:
    """
    Parse Instagram webhook payload, log it, forward comments to comment-to-DM service
    and messages to logging. Does not modify comment logic.
    """
    payload = _normalize_payload(body)
    entries = payload.get("entry") or []
    # Log which format we received (messaging vs changes) for debugging
    first_entry = entries[0] if entries else {}
    has_messaging = bool(first_entry.get("messaging"))
    has_changes = bool(first_entry.get("changes"))
    logger.info(
        "Instagram webhook payload received",
        payload_type=type(body).__name__,
        object_type=payload.get("object"),
        entry_count=len(entries),
        has_messaging=has_messaging,
        has_changes=has_changes,
    )

    obj = payload.get("object")
    if obj != "instagram":
        logger.debug("Instagram webhook ignored: object is not instagram", object=obj)
        return

    for entry in entries:
        ig_id = entry.get("id")
        if not ig_id:
            continue
        account_id = _account_id_for_ig_business(str(ig_id), app)

        # Format 1: Instagram Messaging (Messenger Platform) - entry.messaging[] (no "changes")
        messaging_list = entry.get("messaging") or []
        if isinstance(messaging_list, list):
            for messaging_item in messaging_list:
                if not isinstance(messaging_item, dict):
                    continue
                if account_id and app:
                    try:
                        _process_incoming_dm_for_ai_reply(
                            account_id=account_id,
                            value=messaging_item,
                            app=app,
                        )
                    except Exception as e:
                        logger.exception(
                            "AI DM auto-reply failed (messaging format)",
                            account_id=account_id,
                            error=str(e),
                            value=messaging_item,
                        )

        # Format 2: Instagram Graph API - entry.changes[] with field "messages"
        for change in entry.get("changes") or []:
            field = change.get("field")
            value = change.get("value")
            if not isinstance(value, dict):
                continue

            if field in ("comments", "live_comments"):
                comment = _webhook_comment_to_service_format(value)
                media_id = _media_id_from_comment_value(value)
                if not media_id:
                    logger.warning(
                        "Instagram webhook comment missing media id",
                        entry_id=ig_id,
                        comment_id=comment.get("id"),
                    )
                    continue
                comments = [comment]
                
                # Try to get post caption for better AI context (optional, don't fail if unavailable)
                post_caption = None
                if account_id and app and getattr(app, "account_service", None):
                    try:
                        client = app.account_service.get_client(account_id)
                        media_info = client._make_request(
                            "GET",
                            media_id,
                            params={"fields": "caption"}
                        )
                        post_caption = media_info.get("caption", "")
                    except Exception as e:
                        logger.debug(
                            "Could not fetch post caption for webhook comment",
                            account_id=account_id,
                            media_id=media_id,
                            error=str(e),
                        )
                        # Continue without caption - not critical
                
                if account_id and app and getattr(app, "comment_to_dm_service", None):
                    try:
                        app.comment_to_dm_service.process_new_comments_for_dm(
                            account_id=account_id,
                            media_id=media_id,
                            comments=comments,
                            post_caption=post_caption,
                        )
                        logger.info(
                            "Instagram webhook comment forwarded to comment-to-DM",
                            account_id=account_id,
                            media_id=media_id,
                            comment_id=comment.get("id"),
                        )
                    except Exception as e:
                        logger.exception(
                            "Instagram webhook comment forward failed",
                            account_id=account_id,
                            media_id=media_id,
                            error=str(e),
                        )
                else:
                    logger.debug(
                        "Instagram webhook comment not forwarded (no account or service)",
                        ig_id=ig_id,
                        account_id=account_id,
                    )

            elif field == "messages":
                logger.info(
                    "Instagram webhook messages event",
                    entry_id=ig_id,
                    account_id=account_id,
                    has_account_id=bool(account_id),
                    has_app=bool(app),
                    value_type=type(value).__name__,
                    value_keys=list(value.keys()) if isinstance(value, dict) else None,
                    value_preview=str(value)[:500] if isinstance(value, dict) else str(value)[:200],
                )
                
                # Process incoming DM for AI auto-reply
                if account_id and app:
                    try:
                        _process_incoming_dm_for_ai_reply(
                            account_id=account_id,
                            value=value,
                            app=app,
                        )
                    except Exception as e:
                        logger.exception(
                            "AI DM auto-reply processing failed",
                            account_id=account_id,
                            error=str(e),
                            value=value,
                        )
                else:
                    logger.warning(
                        "AI DM webhook skipped - missing account_id or app",
                        entry_id=ig_id,
                        account_id=account_id,
                        has_app=bool(app),
                    )
