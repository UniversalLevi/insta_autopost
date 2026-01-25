"""Upload 3 cat images and schedule them for 1:15 PM via web API."""
import requests
from datetime import datetime, timedelta
from pathlib import Path

BASE = "http://localhost:8000"
IMAGES = [
    Path(r"C:\Users\kanis\.cursor\projects\d-InstaForge\assets\c__Users_kanis_AppData_Roaming_Cursor_User_workspaceStorage_7863cb615d6fa77a2e8b9e73301c6c04_images_cat1-a7ccea2b-33c4-4587-aa68-46d8093140ad.png"),
    Path(r"C:\Users\kanis\.cursor\projects\d-InstaForge\assets\c__Users_kanis_AppData_Roaming_Cursor_User_workspaceStorage_7863cb615d6fa77a2e8b9e73301c6c04_images_cat2-4b563486-b4e1-4a00-ab6a-ee1b5d4b8067.png"),
    Path(r"C:\Users\kanis\.cursor\projects\d-InstaForge\assets\c__Users_kanis_AppData_Roaming_Cursor_User_workspaceStorage_7863cb615d6fa77a2e8b9e73301c6c04_images_cat-8be3407c-8ede-4a1d-9f3f-3fa9e0c658b4.png"),
]
CAPTIONS = [
    "Fluffy ginger and white kitten with bright blue eyes. #cute #kitten #pets #adorable",
    "Tabby kitten jumping and pouncing. #kitten #tabby #playful #cute #adorable",
    "Cream kitten with big blue eyes. #kitten #cute #fluffy #adorable",
]

def main():
    now = datetime.now()
    scheduled = now.replace(hour=13, minute=15, second=0, microsecond=0)
    if scheduled <= now:
        scheduled = (now + timedelta(days=1)).replace(hour=13, minute=15, second=0, microsecond=0)
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
    print(f"Using account: {acc['username']} ({account_id})")

    # 2. Upload each image
    urls = []
    for i, path in enumerate(IMAGES):
        if not path.exists():
            print(f"Missing: {path}")
            return
        with open(path, "rb") as f:
            files = {"files": (path.name, f, "image/png")}
            up = requests.post(f"{BASE}/api/upload", files=files)
        up.raise_for_status()
        u = up.json()["urls"][0]["url"]
        urls.append(u)
        print(f"Uploaded {i+1}/3: {path.name}")

    # 3. Schedule 3 posts for 1:15 PM
    for i, (url, cap) in enumerate(zip(urls, CAPTIONS)):
        body = {
            "account_id": account_id,
            "media_type": "image",
            "urls": [url],
            "caption": cap,
            "scheduled_time": scheduled_str,
        }
        cr = requests.post(f"{BASE}/api/posts/create", json=body)
        if not cr.ok:
            print(f"Post {i+1} failed: {cr.status_code} - {cr.text}")
            continue
        out = cr.json()
        print(f"Scheduled post {i+1}: {out.get('post_id')} -> {scheduled_str}")

    print(f"\nAll 3 posts scheduled for 1:15 PM ({scheduled_str}). They will publish automatically when the time comes.")

if __name__ == "__main__":
    main()
