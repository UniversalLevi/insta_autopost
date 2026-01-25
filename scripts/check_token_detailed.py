"""Detailed Instagram token check"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
import yaml

# Load config (config lives under data/ per config_manager)
with open("data/accounts.yaml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

account = config["accounts"][0]
token = account["access_token"]
account_id = account["account_id"]
username = account["username"]

print("=" * 70)
print("Instagram Token Detailed Check")
print("=" * 70)
print(f"\nAccount: {username}")
print(f"Account ID: {account_id}")
print(f"Token (first 40 chars): {token[:40]}...")
print(f"Token length: {len(token)} characters\n")

# Test 1: Try to get account info
print("Test 1: Getting account information...")
print("-" * 70)
try:
    url = f"https://graph.facebook.com/v18.0/{account_id}"
    params = {
        "fields": "id,username,account_type",
        "access_token": token
    }
    response = requests.get(url, params=params, timeout=10)
    result = response.json()
    
    if "error" in result:
        print(f"[FAIL] Error: {result['error']['message']}")
        print(f"       Code: {result['error'].get('code')}")
        print(f"       Type: {result['error'].get('type')}")
        if result['error'].get('error_subcode'):
            print(f"       Subcode: {result['error'].get('error_subcode')}")
    else:
        print(f"[OK] Account info retrieved successfully")
        print(f"     ID: {result.get('id')}")
        print(f"     Username: {result.get('username')}")
        print(f"     Account Type: {result.get('account_type')}")
except Exception as e:
    print(f"[ERROR] Request failed: {str(e)}")

# Test 2: Try to get media (posts)
print("\nTest 2: Getting recent posts...")
print("-" * 70)
try:
    url = f"https://graph.facebook.com/v18.0/{account_id}/media"
    params = {
        "fields": "id,caption,comments_count,like_count",
        "limit": 3,
        "access_token": token
    }
    response = requests.get(url, params=params, timeout=10)
    result = response.json()
    
    if "error" in result:
        print(f"[FAIL] Error: {result['error']['message']}")
        print(f"       Code: {result['error'].get('code')}")
    else:
        media_count = len(result.get("data", []))
        print(f"[OK] Retrieved {media_count} recent posts")
        if media_count > 0:
            for post in result.get("data", [])[:2]:
                print(f"     Post ID: {post.get('id')} - Comments: {post.get('comments_count', 0)}")
except Exception as e:
    print(f"[ERROR] Request failed: {str(e)}")

# Test 3: Try to get comments (this requires instagram_manage_comments)
print("\nTest 3: Getting comments from a post (requires instagram_manage_comments)...")
print("-" * 70)
try:
    # First get a post ID
    url = f"https://graph.facebook.com/v18.0/{account_id}/media"
    params = {
        "fields": "id",
        "limit": 1,
        "access_token": token
    }
    response = requests.get(url, params=params, timeout=10)
    media_result = response.json()
    
    if "data" in media_result and len(media_result["data"]) > 0:
        media_id = media_result["data"][0]["id"]
        print(f"     Testing with post: {media_id}")
        
        # Now try to get comments
        comments_url = f"https://graph.facebook.com/v18.0/{media_id}/comments"
        comments_params = {
            "fields": "id,text,username,timestamp",
            "access_token": token
        }
        comments_response = requests.get(comments_url, params=comments_params, timeout=10)
        comments_result = comments_response.json()
        
        if "error" in comments_result:
            error = comments_result["error"]
            print(f"[FAIL] Error: {error['message']}")
            print(f"       Code: {error.get('code')}")
            if error.get('code') == 10:  # Permission denied
                print(f"       [CRITICAL] Missing 'instagram_manage_comments' permission!")
        else:
            comment_count = len(comments_result.get("data", []))
            print(f"[OK] Retrieved {comment_count} comments")
            if comment_count > 0:
                print(f"     First comment: {comments_result['data'][0].get('text', '')[:50]}...")
except Exception as e:
    print(f"[ERROR] Request failed: {str(e)}")

# Test 4: Check token permissions via debug endpoint (using Facebook token if available)
print("\nTest 4: Checking token permissions...")
print("-" * 70)
print("Note: Instagram tokens cannot be debugged directly.")
print("You need to check permissions when generating the token.")
print("\nRequired permissions for comment-to-DM:")
print("  [REQUIRED] instagram_basic")
print("  [REQUIRED] instagram_manage_comments  <- Needed to READ comments")
print("  [REQUIRED] instagram_manage_messages  <- Needed to SEND DMs")
print("  [REQUIRED] instagram_content_publish")

print("\n" + "=" * 70)
print("Summary")
print("=" * 70)
print("\nIf Test 1 or Test 2 failed:")
print("  -> Your token may be expired or invalid")
print("  -> Regenerate token at: https://developers.facebook.com/tools/explorer/")
print("\nIf Test 3 failed with code 10:")
print("  -> Missing 'instagram_manage_comments' permission")
print("  -> This is why you see 0 comments in logs")
print("  -> Regenerate token WITH this permission")
print("\n" + "=" * 70)
