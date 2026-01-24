"""Test Instagram token - check if it's Facebook or Instagram token"""

import requests
import yaml

# Load config
with open("config/accounts.yaml", "r") as f:
    config = yaml.safe_load(f)

account = config["accounts"][0]
token = account["access_token"]
account_id = account["account_id"]

print("=" * 70)
print("Instagram Token Type Check")
print("=" * 70)
print(f"\nToken: {token[:50]}...")
print(f"Token length: {len(token)}")
print(f"Starts with: {token[:5]}\n")

# Check if it's a Facebook token (starts with EAA) or Instagram token (starts with IGAAT)
if token.startswith("EAA"):
    print("[INFO] This appears to be a FACEBOOK token (starts with EAA)")
    print("       Instagram tokens should start with 'IGAAT'")
    print("\n[ACTION] You need to:")
    print("   1. Use Facebook token to get Instagram Business Account ID")
    print("   2. Exchange it for Instagram token OR")
    print("   3. Generate Instagram token directly from Graph API Explorer")
elif token.startswith("IGAAT"):
    print("[INFO] This appears to be an INSTAGRAM token (starts with IGAAT)")
    print("       Format looks correct")
else:
    print(f"[WARNING] Token format unusual (starts with {token[:5]})")
    print("          Instagram tokens typically start with 'IGAAT'")

# Try to use Facebook token to get Instagram account
print("\n" + "=" * 70)
print("Attempting to get Instagram account info...")
print("=" * 70)

# Method 1: Direct Instagram API call
print("\nMethod 1: Direct Instagram API call...")
try:
    url = f"https://graph.facebook.com/v18.0/{account_id}"
    params = {
        "fields": "id,username,account_type",
        "access_token": token
    }
    response = requests.get(url, params=params, timeout=10)
    result = response.json()
    
    if "error" in result:
        error = result["error"]
        print(f"[FAIL] {error['message']}")
        print(f"       Code: {error.get('code')}")
        print(f"       Type: {error.get('type')}")
        
        if error.get('code') == 190:
            print("\n[DIAGNOSIS] Token is invalid or expired")
            print("           Possible reasons:")
            print("           1. Token expired (Instagram tokens expire)")
            print("           2. Token was revoked")
            print("           3. Token doesn't have required permissions")
            print("           4. Token is for wrong app/page")
    else:
        print(f"[SUCCESS] Account info retrieved!")
        print(f"          ID: {result.get('id')}")
        print(f"          Username: {result.get('username')}")
        print(f"          Type: {result.get('account_type')}")
except Exception as e:
    print(f"[ERROR] {str(e)}")

# Method 2: Try Instagram Graph API endpoint
print("\nMethod 2: Instagram Graph API endpoint...")
try:
    # First, try to get connected Instagram account from Facebook page
    # This requires a Facebook token, not Instagram token
    if token.startswith("EAA"):
        print("   [INFO] Using Facebook token to find Instagram account...")
        # Get pages
        pages_url = "https://graph.facebook.com/v18.0/me/accounts"
        pages_params = {"access_token": token}
        pages_resp = requests.get(pages_url, params=pages_params, timeout=10)
        pages_data = pages_resp.json()
        
        if "data" in pages_data and len(pages_data["data"]) > 0:
            print(f"   [OK] Found {len(pages_data['data'])} Facebook pages")
            for page in pages_data["data"][:2]:
                page_id = page.get("id")
                page_token = page.get("access_token")
                # Try to get Instagram account
                ig_url = f"https://graph.facebook.com/v18.0/{page_id}"
                ig_params = {
                    "fields": "instagram_business_account",
                    "access_token": page_token
                }
                ig_resp = requests.get(ig_url, params=ig_params, timeout=10)
                ig_data = ig_resp.json()
                if "instagram_business_account" in ig_data:
                    ig_id = ig_data["instagram_business_account"]["id"]
                    print(f"   [OK] Found Instagram account: {ig_id}")
except Exception as e:
    print(f"   [INFO] Method 2 not applicable: {str(e)}")

print("\n" + "=" * 70)
print("Next Steps")
print("=" * 70)
print("\nIf token is invalid, you need to generate a NEW token:")
print("\n1. Go to: https://developers.facebook.com/tools/explorer/")
print("2. Select your app")
print("3. Click 'Generate Access Token'")
print("4. Select these permissions:")
print("   - instagram_basic")
print("   - instagram_manage_comments")
print("   - instagram_manage_messages")
print("   - instagram_content_publish")
print("5. Copy the LONG-LIVED token (starts with IGAAT)")
print("6. Update config/accounts.yaml")
print("\nNote: Instagram tokens expire. You may need to generate a")
print("      long-lived token (60 days) or set up token refresh.")
print("=" * 70)
