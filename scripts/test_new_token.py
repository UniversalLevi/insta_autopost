"""Test the new Facebook token"""

import requests
import yaml

# Load config
with open("config/accounts.yaml", "r") as f:
    config = yaml.safe_load(f)

account = config["accounts"][0]
token = account["access_token"]
account_id = account["account_id"]
username = account["username"]

print("=" * 70)
print("Testing New Token")
print("=" * 70)
print(f"\nAccount: {username}")
print(f"Account ID: {account_id}")
print(f"Token: {token[:50]}...")
print(f"Token length: {len(token)}")
print(f"Token type: {'Facebook (EAA)' if token.startswith('EAA') else 'Instagram (IGAAT)'}\n")

# Test 1: Get Facebook user info
print("Test 1: Getting Facebook user info...")
print("-" * 70)
try:
    url = "https://graph.facebook.com/v18.0/me"
    params = {
        "fields": "id,name",
        "access_token": token
    }
    response = requests.get(url, params=params, timeout=10)
    result = response.json()
    
    if "error" in result:
        print(f"[FAIL] {result['error']['message']}")
        print(f"       Code: {result['error'].get('code')}")
    else:
        print(f"[OK] User: {result.get('name')} (ID: {result.get('id')})")
except Exception as e:
    print(f"[ERROR] {str(e)}")

# Test 2: Get Facebook pages
print("\nTest 2: Getting Facebook pages...")
print("-" * 70)
try:
    url = "https://graph.facebook.com/v18.0/me/accounts"
    params = {"access_token": token}
    response = requests.get(url, params=params, timeout=10)
    result = response.json()
    
    if "error" in result:
        print(f"[FAIL] {result['error']['message']}")
        print(f"       Code: {result['error'].get('code')}")
    else:
        pages = result.get("data", [])
        print(f"[OK] Found {len(pages)} Facebook pages")
        
        if len(pages) > 0:
            for i, page in enumerate(pages[:3], 1):
                page_id = page.get("id")
                page_name = page.get("name")
                page_token = page.get("access_token")
                print(f"\n   Page {i}: {page_name} (ID: {page_id})")
                
                # Check for Instagram account
                try:
                    ig_url = f"https://graph.facebook.com/v18.0/{page_id}"
                    ig_params = {
                        "fields": "instagram_business_account{id,username}",
                        "access_token": page_token
                    }
                    ig_response = requests.get(ig_url, params=ig_params, timeout=10)
                    ig_result = ig_response.json()
                    
                    if "instagram_business_account" in ig_result:
                        ig_account = ig_result["instagram_business_account"]
                        ig_id = ig_account.get("id")
                        ig_username = ig_account.get("username")
                        print(f"   [SUCCESS] Found Instagram: {ig_username} (ID: {ig_id})")
                        
                        # Test Instagram API access with page token
                        print(f"\n   Test 3: Testing Instagram API with page token...")
                        test_url = f"https://graph.facebook.com/v18.0/{ig_id}"
                        test_params = {
                            "fields": "id,username,account_type",
                            "access_token": page_token
                        }
                        test_response = requests.get(test_url, params=test_params, timeout=10)
                        test_result = test_response.json()
                        
                        if "error" in test_result:
                            print(f"   [FAIL] {test_result['error']['message']}")
                        else:
                            print(f"   [OK] Can access Instagram account!")
                            
                            # Try to get posts
                            posts_url = f"https://graph.facebook.com/v18.0/{ig_id}/media"
                            posts_params = {
                                "fields": "id,caption,comments_count",
                                "limit": 1,
                                "access_token": page_token
                            }
                            posts_response = requests.get(posts_url, params=posts_params, timeout=10)
                            posts_result = posts_response.json()
                            
                            if "error" in posts_result:
                                print(f"   [INFO] Cannot get posts: {posts_result['error']['message']}")
                            else:
                                print(f"   [OK] Can retrieve posts")
                                
                                # Try to get comments
                                if "data" in posts_result and len(posts_result["data"]) > 0:
                                    media_id = posts_result["data"][0]["id"]
                                    comments_url = f"https://graph.facebook.com/v18.0/{media_id}/comments"
                                    comments_params = {
                                        "fields": "id,text,username",
                                        "access_token": page_token
                                    }
                                    comments_response = requests.get(comments_url, params=comments_params, timeout=10)
                                    comments_result = comments_response.json()
                                    
                                    if "error" in comments_result:
                                        error = comments_result["error"]
                                        print(f"   [WARNING] Cannot get comments: {error['message']}")
                                        if error.get('code') == 10:
                                            print(f"            [CRITICAL] Missing 'instagram_manage_comments' permission!")
                                    else:
                                        comment_count = len(comments_result.get("data", []))
                                        print(f"   [OK] Can retrieve comments ({comment_count} found)")
                                        
                                        print(f"\n   [RECOMMENDATION] Use page token for Instagram access:")
                                        print(f"                   {page_token[:50]}...")
                    else:
                        print(f"   [INFO] No Instagram account linked to this page")
                except Exception as e:
                    print(f"   [ERROR] {str(e)}")
        else:
            print("[INFO] No pages found")
except Exception as e:
    print(f"[ERROR] {str(e)}")

# Test 3: Try direct Instagram access (if it's actually an Instagram token)
if token.startswith("IGAAT"):
    print("\nTest 3: Direct Instagram API access...")
    print("-" * 70)
    try:
        url = f"https://graph.facebook.com/v18.0/{account_id}"
        params = {
            "fields": "id,username",
            "access_token": token
        }
        response = requests.get(url, params=params, timeout=10)
        result = response.json()
        
        if "error" in result:
            print(f"[FAIL] {result['error']['message']}")
        else:
            print(f"[OK] Can access Instagram account directly!")
    except Exception as e:
        print(f"[ERROR] {str(e)}")

print("\n" + "=" * 70)
print("Summary")
print("=" * 70)
print("\nIf you have Facebook pages with Instagram connected:")
print("  -> Use the PAGE ACCESS TOKEN (not user token)")
print("  -> Page token can access connected Instagram account")
print("\nIf you need direct Instagram access:")
print("  -> Generate Instagram token (starts with IGAAT)")
print("  -> Requires instagram_manage_comments permission")
print("=" * 70)
