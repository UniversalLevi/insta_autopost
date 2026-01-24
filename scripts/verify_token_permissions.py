"""Verify Instagram token permissions"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.app import InstaForgeApp
import requests

app = InstaForgeApp()
app.initialize()

account_id = "1405915827600672"
account = app.account_service.get_account(account_id)

print("=" * 60)
print("Verifying Instagram Token Permissions")
print("=" * 60)
print(f"\nAccount: {account.username}")
print(f"Token: {account.access_token[:30]}...\n")

# Check token info via Facebook Debug
print("Checking token permissions via Facebook API...\n")

try:
    # Debug the Instagram token
    debug_url = f"https://graph.facebook.com/v18.0/debug_token"
    params = {
        "input_token": account.access_token,
        "access_token": account.access_token,
    }
    
    response = requests.get(debug_url, params=params, timeout=10)
    result = response.json()
    
    if "data" in result:
        data = result["data"]
        
        print("Token Information:")
        print(f"  App ID: {data.get('app_id', 'N/A')}")
        print(f"  Type: {data.get('type', 'N/A')}")
        print(f"  Valid: {data.get('is_valid', False)}")
        print(f"  Expires At: {data.get('expires_at', 'Never' if data.get('expires_at') == 0 else data.get('expires_at'))}")
        
        # Get permissions
        scopes = data.get("scopes", [])
        print(f"\nPermissions (Scopes): {len(scopes)} found")
        print("-" * 60)
        
        required_permissions = {
            "instagram_basic": "Basic Instagram access",
            "instagram_manage_comments": "Read/manage comments (REQUIRED for reading comments)",
            "instagram_manage_messages": "Send DMs (REQUIRED for auto-DM)",
            "instagram_content_publish": "Publish posts",
        }
        
        print("\nChecking Required Permissions:\n")
        all_present = True
        for perm, desc in required_permissions.items():
            if perm in scopes:
                print(f"  [OK] {perm}")
                print(f"       {desc}")
            else:
                print(f"  [MISSING] {perm}")
                print(f"       {desc}")
                all_present = False
            print()
        
        print("\nAll Available Permissions:")
        print("-" * 60)
        for scope in sorted(scopes):
            marker = "[REQUIRED]" if scope in required_permissions else ""
            print(f"  - {scope} {marker}")
        
        print("\n" + "=" * 60)
        if all_present:
            print("\n[SUCCESS] All required permissions are present!")
            print("Your token should work for reading comments and sending DMs.")
        else:
            print("\n[WARNING] Missing required permissions!")
            print("You need to regenerate your Instagram token with missing permissions.")
            print("\nHow to fix:")
            print("1. Go to: https://developers.facebook.com/tools/explorer/")
            print("2. Select your app")
            print("3. Generate new token with ALL required permissions")
            print("4. Update config/accounts.yaml with new token")
            print("5. Restart server")
        
    else:
        print("[ERROR] Could not get token info")
        print(f"Response: {result}")
        
except Exception as e:
    print(f"[ERROR] Failed to check token: {str(e)}")
    print("\nNote: You may need to use Facebook's Graph API Explorer")
    print("directly to verify your Instagram token permissions.")

print("\n" + "=" * 60)
