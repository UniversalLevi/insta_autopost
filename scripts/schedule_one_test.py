"""Upload one image, schedule it for 2 minutes from now, verify it publishes."""
import requests
from datetime import datetime, timedelta
from pathlib import Path
import time

BASE = "http://localhost:8000"
IMG = Path(
    r"C:\Users\kanis\.cursor\projects\d-InstaForge\assets\c__Users_kanis_AppData_Roaming_Cursor_User_workspaceStorage_7863cb615d6fa77a2e8b9e73301c6c04_images_pexels-2557985-19733176-08f08c3f-b28d-4ad0-aa52-64e38476484d.png"
)
CAPTION = "Dramatic silhouette. Light, shadow, feline grace. #cat #silhouette #photography #art"


def main():
    if not IMG.exists():
        print(f"Image not found: {IMG}")
        return

    # Schedule 2 minutes from now
    scheduled = datetime.now() + timedelta(minutes=2)
    scheduled_str = scheduled.strftime("%Y-%m-%dT%H:%M")

    # 1. Accounts
    r = requests.get(f"{BASE}/api/config/accounts")
    r.raise_for_status()
    accounts = r.json().get("accounts", [])
    if not accounts:
        print("No accounts configured")
        return
    acc = accounts[0]
    account_id = acc["account_id"]
    print(f"Account: {acc['username']} ({account_id})")

    # 2. Upload
    print("Uploading image...")
    with open(IMG, "rb") as f:
        files = {"files": (IMG.name, f, "image/png")}
        up = requests.post(f"{BASE}/api/upload", files=files)
    up.raise_for_status()
    url = up.json()["urls"][0]["url"]
    print(f"Uploaded: {url[:60]}...")

    # 3. Schedule
    body = {
        "account_id": account_id,
        "media_type": "image",
        "urls": [url],
        "caption": CAPTION,
        "scheduled_time": scheduled_str,
    }
    cr = requests.post(f"{BASE}/api/posts/create", json=body)
    if not cr.ok:
        print(f"Schedule failed: {cr.status_code} - {cr.text}")
        return
    out = cr.json()
    pid = out.get("post_id")
    print(f"Scheduled post {pid} for {scheduled_str}")

    # 4. Wait and verify
    print("\nWaiting 2.5 min for publisher to run...")
    time.sleep(150)

    # 5. Check published
    pr = requests.get(f"{BASE}/api/posts/published", params={"limit": 5})
    if not pr.ok:
        print(f"Failed to fetch published: {pr.status_code}")
        return
    posts = pr.json().get("posts", [])
    recent = [p for p in posts if (p.get("caption") or "").strip().startswith("Dramatic silhouette")]
    if recent:
        print(f"Verified: post is live. Instagram ID: {recent[0].get('id')}")
    else:
        print("Post not yet in published list. Check logs or History page.")


if __name__ == "__main__":
    main()
