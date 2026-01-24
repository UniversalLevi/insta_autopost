"""Test Facebook token with known Instagram account ID"""

import requests
import yaml

# Load config to get Instagram account ID
with open("config/accounts.yaml", "r") as f:
    config = yaml.safe_load(f)

account = config["accounts"][0]
ig_account_id = account["account_id"]  # 1405915827600672
username = account["username"]

# The Facebook token
fb_token = "EAAbDa5hBPloBQjYZCXbxP4MWEyDz70wVgbU4VMpCqKcmdleZCODVS4uaGgUHIZAdW8yERkvCZC2QBeaZBWuaytGZA1JBpvZCd1iQ3pZC1M5IIjBQFLBUqMzvo6dxfh5MrbCWRLIjhZAc1kvdWGb2RyIHhyz8HUcGGpbd78rvPxCeO5XBxXLra2R8T2OPb1YkXe8Ahf10fMLckn3e18eFabmRCNFHZCmLj29oUiC9hOYWwkTnLK3Dee62TseSW0eY1ZBAbsIMqxoiBlvVV1VO5JufUZAA"

print("=" * 70)
print("Testing Facebook Token with Instagram Account")
print("=" * 70)
print(f"\nInstagram Account ID: {ig_account_id}")
print(f"Username: {username}")
print(f"Facebook Token: {fb_token[:50]}...\n")

# Test 1: Try to access Instagram account directly with FB token
print("Test 1: Accessing Instagram account with Facebook token...")
print("-" * 70)
try:
    url = f"https://graph.facebook.com/v18.0/{ig_account_id}"
    params = {
        "fields": "id,username,account_type",
        "access_token": fb_token
    }
    response = requests.get(url, params=params, timeout=10)
    result = response.json()
    
    if "error" in result:
        error = result["error"]
        print(f"[FAIL] {error['message']}")
        print(f"       Code: {error.get('code')}")
        print(f"       Type: {error.get('type')}")
        if error.get('error_subcode'):
            print(f"       Subcode: {error.get('error_subcode')}")
    else:
        print(f"[SUCCESS] Can access Instagram account!")
        print(f"          ID: {result.get('id')}")
        print(f"          Username: {result.get('username')}")
        print(f"          Account Type: {result.get('account_type')}")
except Exception as e:
    print(f"[ERROR] {str(e)}")

# Test 2: Try to get posts
print("\nTest 2: Getting recent posts...")
print("-" * 70)
try:
    url = f"https://graph.facebook.com/v18.0/{ig_account_id}/media"
    params = {
        "fields": "id,caption,comments_count,like_count",
        "limit": 3,
        "access_token": fb_token
    }
    response = requests.get(url, params=params, timeout=10)
    result = response.json()
    
    if "error" in result:
        error = result["error"]
        print(f"[FAIL] {error['message']}")
        print(f"       Code: {error.get('code')}")
    else:
        posts = result.get("data", [])
        print(f"[SUCCESS] Retrieved {len(posts)} posts")
        for post in posts:
            print(f"          Post: {post.get('id')} - Comments: {post.get('comments_count', 0)}")
except Exception as e:
    print(f"[ERROR] {str(e)}")

# Test 3: Try to get comments (CRITICAL TEST)
print("\nTest 3: Getting comments from a post (requires instagram_manage_comments)...")
print("-" * 70)
try:
    # First get a post
    url = f"https://graph.facebook.com/v18.0/{ig_account_id}/media"
    params = {
        "fields": "id,comments_count",
        "limit": 1,
        "access_token": fb_token
    }
    response = requests.get(url, params=params, timeout=10)
    result = response.json()
    
    if "data" in result and len(result["data"]) > 0:
        post = result["data"][0]
        media_id = post.get("id")
        comments_count = post.get("comments_count", 0)
        print(f"     Testing with post: {media_id}")
        print(f"     Post shows {comments_count} comments")
        
        # Try to get comments
        comments_url = f"https://graph.facebook.com/v18.0/{media_id}/comments"
        comments_params = {
            "fields": "id,text,username,timestamp",
            "access_token": fb_token
        }
        comments_response = requests.get(comments_url, params=comments_params, timeout=10)
        comments_result = comments_response.json()
        
        if "error" in comments_result:
            error = comments_result["error"]
            print(f"[FAIL] {error['message']}")
            print(f"       Code: {error.get('code')}")
            if error.get('code') == 10:
                print(f"\n[CRITICAL] Missing 'instagram_manage_comments' permission!")
                print(f"          This is why you can't read comments.")
                print(f"          You need to regenerate token with this permission.")
        else:
            comment_count = len(comments_result.get("data", []))
            print(f"[SUCCESS] Retrieved {comment_count} comments!")
            if comment_count > 0:
                first_comment = comments_result["data"][0]
                print(f"          First comment: {first_comment.get('text', '')[:50]}...")
                print(f"          By: {first_comment.get('username', 'unknown')}")
except Exception as e:
    print(f"[ERROR] {str(e)}")

# Test 4: Try to send a DM (requires instagram_manage_messages)
print("\nTest 4: Testing DM capability (requires instagram_manage_messages)...")
print("-" * 70)
print("[INFO] DM sending requires specific permissions and recipient ID")
print("       This test would require a valid recipient Instagram user ID")
print("       Skipping actual DM send test to avoid errors")

print("\n" + "=" * 70)
print("Conclusion")
print("=" * 70)
print("\nIf Test 1 and Test 2 passed:")
print("  -> Facebook token CAN access Instagram account")
print("  -> You can use this token instead of Instagram token")
print("\nIf Test 3 passed:")
print("  -> Token has instagram_manage_comments permission")
print("  -> Comment-to-DM will work!")
print("\nIf Test 3 failed with code 10:")
print("  -> Missing instagram_manage_comments permission")
print("  -> Regenerate token with this permission")
print("=" * 70)
