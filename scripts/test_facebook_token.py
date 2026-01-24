"""Test Facebook token and get Instagram account"""

import requests
import yaml

# The Facebook token provided
fb_token = "EAAbDa5hBPloBQjYZCXbxP4MWEyDz70wVgbU4VMpCqKcmdleZCODVS4uaGgUHIZAdW8yERkvCZC2QBeaZBWuaytGZA1JBpvZCd1iQ3pZC1M5IIjBQFLBUqMzvo6dxfh5MrbCWRLIjhZAc1kvdWGb2RyIHhyz8HUcGGpbd78rvPxCeO5XBxXLra2R8T2OPb1YkXe8Ahf10fMLckn3e18eFabmRCNFHZCmLj29oUiC9hOYWwkTnLK3Dee62TseSW0eY1ZBAbsIMqxoiBlvVV1VO5JufUZAA"

print("=" * 70)
print("Facebook Token Test")
print("=" * 70)
print(f"\nToken: {fb_token[:50]}...")
print(f"Token length: {len(fb_token)}")
print(f"Type: Facebook Access Token (starts with EAA)\n")

# Step 1: Get user info
print("Step 1: Getting Facebook user info...")
print("-" * 70)
try:
    url = "https://graph.facebook.com/v18.0/me"
    params = {
        "fields": "id,name,email",
        "access_token": fb_token
    }
    response = requests.get(url, params=params, timeout=10)
    result = response.json()
    
    if "error" in result:
        print(f"[FAIL] {result['error']['message']}")
        print(f"       Code: {result['error'].get('code')}")
    else:
        print(f"[OK] User: {result.get('name')} (ID: {result.get('id')})")
        user_id = result.get('id')
except Exception as e:
    print(f"[ERROR] {str(e)}")
    user_id = None

# Step 2: Get Facebook pages
print("\nStep 2: Getting Facebook pages...")
print("-" * 70)
try:
    url = "https://graph.facebook.com/v18.0/me/accounts"
    params = {
        "access_token": fb_token
    }
    response = requests.get(url, params=params, timeout=10)
    result = response.json()
    
    if "error" in result:
        print(f"[FAIL] {result['error']['message']}")
        print(f"       Code: {result['error'].get('code')}")
        if result['error'].get('code') == 190:
            print("\n[CRITICAL] Token is invalid or expired!")
    else:
        pages = result.get("data", [])
        print(f"[OK] Found {len(pages)} Facebook pages")
        
        if len(pages) > 0:
            for i, page in enumerate(pages[:3], 1):
                page_id = page.get("id")
                page_name = page.get("name")
                page_token = page.get("access_token")
                print(f"\n   Page {i}: {page_name} (ID: {page_id})")
                
                # Step 3: Get Instagram account linked to this page
                print(f"   Step 3: Checking for Instagram account...")
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
                        print(f"   [SUCCESS] Found Instagram account!")
                        print(f"             ID: {ig_id}")
                        print(f"             Username: {ig_username}")
                        
                        # Step 4: Try to get Instagram token
                        print(f"\n   Step 4: Testing Instagram API access...")
                        try:
                            # Use page token to access Instagram
                            test_url = f"https://graph.facebook.com/v18.0/{ig_id}"
                            test_params = {
                                "fields": "id,username,account_type",
                                "access_token": page_token
                            }
                            test_response = requests.get(test_url, params=test_params, timeout=10)
                            test_result = test_response.json()
                            
                            if "error" in test_result:
                                print(f"   [INFO] Instagram API test: {test_result['error']['message']}")
                                print(f"          Code: {test_result['error'].get('code')}")
                            else:
                                print(f"   [OK] Can access Instagram account via page token")
                                print(f"        Account Type: {test_result.get('account_type')}")
                                
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
                                            
                        except Exception as e:
                            print(f"   [ERROR] {str(e)}")
                    else:
                        print(f"   [INFO] No Instagram account linked to this page")
                        print(f"          You need to connect Instagram to this Facebook page")
                        
                except Exception as e:
                    print(f"   [ERROR] {str(e)}")
        else:
            print("[INFO] No pages found. You may need to:")
            print("       1. Create a Facebook page")
            print("       2. Connect Instagram to that page")
            print("       3. Use the page's access token")
            
except Exception as e:
    print(f"[ERROR] {str(e)}")

print("\n" + "=" * 70)
print("Summary")
print("=" * 70)
print("\nFacebook tokens can access Instagram IF:")
print("1. Instagram account is connected to a Facebook page")
print("2. The page token has Instagram permissions")
print("3. The token includes instagram_manage_comments permission")
print("\nTo use this token:")
print("1. Get the page access token (from Step 2)")
print("2. Use that token to access Instagram API")
print("3. Or exchange for Instagram token")
print("=" * 70)
