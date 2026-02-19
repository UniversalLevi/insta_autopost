"""Try to fetch Instagram Business ID for v3xxf and update accounts.yaml.
Run from project root: python scripts/fetch_ig_bid_v3xxf.py
If the API does not return an ID, use Webhook Test -> Verify config -> paste ID and click Set ID."""
import sys
from pathlib import Path

# Project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests
import yaml
from src.utils.config import config_manager
from src.models.account import Account

def main():
    accounts = config_manager.load_accounts()
    acc = next((a for a in accounts if (getattr(a, "username", None) or "").strip() == "v3xxf"), None)
    if not acc:
        print("v3xxf not found")
        return
    token = (acc.access_token or "").strip()
    user_token = (getattr(acc, "user_access_token", None) or "").strip() or None
    print("Token present:", bool(token))
    # Try graph.instagram.com/me
    try:
        r = requests.get(
            "https://graph.instagram.com/v18.0/me",
            params={"fields": "id", "access_token": token},
            timeout=15,
        )
        d = r.json()
    except Exception as e:
        print("Request failed:", e)
        return
    print("Response:", d.get("id") or d.get("error", d))
    if "id" in d and "error" not in d:
        ig_bid = str(d["id"]).strip()
        update_dict = acc.dict()
        update_dict["instagram_business_id"] = ig_bid
        updated = Account(**update_dict)
        for i, a in enumerate(accounts):
            if a.account_id == acc.account_id:
                accounts[i] = updated
                break
        config_manager.save_accounts(accounts)
        print("Updated v3xxf instagram_business_id to", ig_bid)
    else:
        print("Could not get ID. Use Webhook Test -> Verify config -> Set ID (paste from Meta).")

if __name__ == "__main__":
    main()
