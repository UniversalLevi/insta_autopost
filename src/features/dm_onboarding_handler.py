from typing import Any, Dict

from src.utils.logger import get_logger
from src.features.dm_onboarding_store import get_session, update_session, reset_session
from src.features.dm_onboarding_limits import can_start_onboarding, record_onboarding_start
from src.services.eazyds_client import get_eazyds_client

logger = get_logger(__name__)


TRIGGER_KEYWORDS = {"store", "start store", "start", "launch store"}
SUPPORTED_CURRENCIES = {"INR", "USD", "EUR", "GBP"}


def _is_trigger(message_text: str) -> bool:
  text = (message_text or "").strip().lower()
  return any(keyword in text for keyword in TRIGGER_KEYWORDS)


def handle_onboarding_dm(
  account_id: str,
  user_id: str,
  username: str,
  message_text: str,
) -> Dict[str, Any]:
  """
  Core state machine for DM onboarding.

  Returns:
    {
      "handled": bool,
      "replyText": Optional[str],
    }
  """
  message_text = (message_text or "").strip()
  session = get_session(account_id, user_id)
  step = session.get("step") or "idle"
  data = session.get("data") or {}

  # If user explicitly starts flow
  if step == "idle":
    if not _is_trigger(message_text):
      return {"handled": False}

    if not can_start_onboarding(account_id, user_id, max_per_day=1):
      return {
        "handled": True,
        "replyText": (
          "You’ve already used the DM onboarding today.\n"
          "If you need another store or help, please come back tomorrow or use the web app."
        ),
      }

    record_onboarding_start(account_id, user_id)

    logger.info(
      "DM_ONBOARDING",
      action="start_flow",
      account_id=account_id,
      user_id=user_id,
      username=username,
      message=message_text,
    )

    update_session(
      account_id,
      user_id,
      {
        "step": "awaiting_email_or_mobile",
        "data": {"instagramUsername": username or ""},
      },
    )
    reply = (
      "Awesome! Let's create your store on EazyDS.\n\n"
      "First, send me your **email** or **mobile number** (with country code, e.g. +91...)."
    )
    return {"handled": True, "replyText": reply}

  # From here, we assume flow is in progress
  if step == "awaiting_email_or_mobile":
    text = message_text
    email = None
    mobile = None

    if "@" in text and "." in text:
      email = text.strip()
    else:
      mobile = text.replace(" ", "")

    if not email and not mobile:
      reply = (
        "I couldn't recognize that as an email or mobile number.\n"
        "Please send a valid **email** (like name@example.com) or **mobile with country code** (e.g. +91...)."
      )
      return {"handled": True, "replyText": reply}

    update_session(
      account_id,
      user_id,
      {
        "step": "awaiting_store_name",
        "data": {
          **data,
          "email": email,
          "mobile": mobile,
        },
      },
    )
    reply = "Great. What should we name your store? (e.g. Flexify, GlowCart)"
    return {"handled": True, "replyText": reply}

  if step == "awaiting_store_name":
    store_name = message_text[:80]
    if not store_name:
      return {
        "handled": True,
        "replyText": "Please send a valid store name (it can be anything, like Flexify or TrendyHub).",
      }

    update_session(
      account_id,
      user_id,
      {
        "step": "awaiting_currency",
        "data": {
          **data,
          "storeName": store_name,
        },
      },
    )
    reply = (
      f"Nice, we'll call it **{store_name}**.\n\n"
      "Now choose your store currency: INR, USD, EUR, or GBP."
    )
    return {"handled": True, "replyText": reply}

  if step == "awaiting_currency":
    currency = message_text.upper().strip()
    if currency not in SUPPORTED_CURRENCIES:
      options = ", ".join(sorted(SUPPORTED_CURRENCIES))
      return {
        "handled": True,
        "replyText": f"Please send one of the supported currencies: {options}.",
      }

    session = update_session(
      account_id,
      user_id,
      {
        "step": "confirming",
        "data": {
          **data,
          "currency": currency,
        },
      },
    )
    info = session.get("data") or {}
    store_name = info.get("storeName") or "your store"

    # Immediately proceed to call EazyDS
    reply = (
      f"Got it. Creating your store **{store_name}** in {currency}... "
      "This usually takes a few seconds."
    )
    # We return this reply now; the actual EazyDS call + final message
    # should be handled by the caller after this function if you want
    # multi-step responses. For now, we do the full call synchronously below.

    client = get_eazyds_client()
    payload = {
      "email": info.get("email"),
      "mobile": info.get("mobile"),
      "name": info.get("instagramUsername") or username,
      "storeName": info.get("storeName") or store_name,
      "currency": info.get("currency") or currency,
      "instagramUserId": str(user_id),
      "instagramUsername": info.get("instagramUsername") or username,
    }

    result = client.create_user_and_store_for_dm(payload)

    if not result.get("success"):
      attempt_count = int(session.get("attemptCount") or 0) + 1
      # If backend complains about email/mobile, send user back to the first step
      next_step = "awaiting_email_or_mobile" if attempt_count < 3 else "failed"
      update_session(
        account_id,
        user_id,
        {
          "step": next_step,
          "attemptCount": attempt_count,
        },
      )
      error_message = result.get("message") or "Something went wrong while creating your store."
      return {
        "handled": True,
        "replyText": (
          "I hit an issue while talking to the store system.\n"
          f"Details: {error_message}\n\n"
          "Please double-check your email or mobile and try again, "
          "or create an account directly on the web app later."
        ),
      }

    update_session(
      account_id,
      user_id,
      {
        "step": "completed",
        "hasCreatedStore": True,
      },
    )

    store_url = result.get("storeUrl")
    login_identifier = result.get("loginIdentifier")
    temp_password = result.get("tempPassword")
    existing_user = bool(result.get("existingUser"))
    existing_store = bool(result.get("existingStore"))

    if not existing_user and temp_password:
      final_msg = (
        "Your store is ready! 🎉\n\n"
        f"Store: {store_url}\n"
        f"Login: {login_identifier}\n"
        f"Temporary password: {temp_password}\n\n"
        "IMPORTANT: Log in and change your password immediately from Settings.\n"
        "You can now manage products, orders, and more from the dashboard."
      )
    elif existing_user and existing_store:
      final_msg = (
        "You already have a store connected to this account.\n\n"
        f"Store: {store_url}\n"
        f"Login: {login_identifier}\n\n"
        "Use your existing password to log in. If you forgot it, use the Forgot Password option on the site."
      )
    else:
      final_msg = (
        "Your new store is ready!\n\n"
        f"Store: {store_url}\n"
        f"Login: {login_identifier}\n\n"
        "Use your existing password to log in. If you forgot it, you can reset it from the login page."
      )

    return {
      "handled": True,
      "replyText": final_msg,
    }

  if step in {"completed", "failed"}:
    # For now, let AI DM handle future messages after completion/failure
    return {"handled": False}

  # Default: do not take over
  return {"handled": False}

