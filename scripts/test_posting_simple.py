"""Test Instagram Posting Capability"""

import sys
import os
import asyncio
from pathlib import Path
import yaml
import requests

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.api.instagram_client import InstagramClient
from src.models.post import PostMedia

async def test_posting():
    print("=" * 60)
    print("Testing Instagram Posting Capability")
    print("=" * 60)

    # Load config
    try:
        with open("config/accounts.yaml", "r") as f:
            config = yaml.safe_load(f)
            account = config["accounts"][0]
            token = account["access_token"]
            account_id = account["account_id"]
            print(f"Account ID: {account_id}")
            print(f"Token: {token[:20]}...")
    except Exception as e:
        print(f"[ERROR] Could not load config: {e}")
        return

    # Initialize client
    client = InstagramClient(access_token=token)
    
    # Test 1: Check Permissions (via debug token)
    print("\nTest 1: Checking Permissions...")
    try:
        debug_url = f"https://graph.facebook.com/v18.0/debug_token"
        params = {
            "input_token": token,
            "access_token": token
        }
        resp = requests.get(debug_url, params=params)
        data = resp.json()
        
        if "data" in data:
            scopes = data["data"].get("scopes", [])
            print(f"Scopes found: {', '.join(scopes)}")
            if "instagram_content_publish" in scopes:
                print("[OK] instagram_content_publish is PRESENT")
            else:
                print("[FAIL] instagram_content_publish is MISSING")
                print("       Posting will FAIL.")
        else:
            print(f"[WARN] Could not check permissions: {data}")
    except Exception as e:
        print(f"[WARN] Permission check skipped: {e}")

    # Test 2: Verify Media URL (Cloudinary)
    print("\nTest 2: Verifying Media URL...")
    # Use a generic placeholder image for testing
    image_url = "https://images.unsplash.com/photo-1575936123452-b67c3203c357?auto=format&fit=crop&w=1000&q=80"
    print(f"Using test image: {image_url}")

    # Test 3: Create Media Container
    print("\nTest 3: Creating Media Container...")
    try:
        container_id = client.create_media_container(
            image_url=image_url,
            caption="Test post from InstaForge diagnostic script #test"
        )
        print(f"[OK] Container created! ID: {container_id}")
    except Exception as e:
        print(f"[FAIL] Container creation FAILED: {e}")
        return

    # Test 4: Publish Media
    print("\nTest 4: Publishing Media...")
    print("[INFO] This will actually post to your account! Press Enter to continue, or Ctrl+C to cancel.")
    try:
        input()
    except KeyboardInterrupt:
        print("\nCancelled.")
        return

    try:
        media_id = client.publish_media(container_id)
        print(f"[OK] Post PUBLISHED! Media ID: {media_id}")
    except Exception as e:
        print(f"[FAIL] Publishing FAILED: {e}")

if __name__ == "__main__":
    # Run async test
    try:
        # Create a new event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(test_posting())
    except Exception as e:
        print(f"Script error: {e}")
