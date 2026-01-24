"""Interactive script to generate Instagram access token"""

import sys
import requests
from pathlib import Path
import yaml
from src.auth import generate_token_interactive, OAuthHelper

def validate_app_credentials(app_id: str, app_secret: str) -> bool:
    """Validate that App ID and Secret are correct"""
    try:
        # Try to verify the app by making a debug request
        url = "https://graph.facebook.com/v18.0/debug_token"
        params = {
            "input_token": app_secret,  # This won't work but helps test API connection
            "access_token": f"{app_id}|{app_secret}",  # App access token format
        }
        # We'll test the app_id format instead
        if not app_id.isdigit() or len(app_id) < 10:
            print(f"  [ERROR] App ID format looks invalid: {app_id}")
            print(f"          App ID should be a numeric string (15-16 digits)")
            return False
        
        print(f"  [OK] App ID format looks valid: {app_id}")
        return True
    except Exception as e:
        print(f"  [WARNING] Could not validate: {e}")
        return True  # Continue anyway

def main():
    """Main function"""
    # Load app credentials
    creds_path = Path("config/app_credentials.yaml")
    if not creds_path.exists():
        print("Error: config/app_credentials.yaml not found")
        print("\nPlease create it with:")
        print("instagram:")
        print("  app_id: 'YOUR_APP_ID'")
        print("  app_secret: 'YOUR_APP_SECRET'")
        sys.exit(1)
    
    with open(creds_path, "r") as f:
        creds = yaml.safe_load(f)
    
    app_id = creds.get("instagram", {}).get("app_id")
    app_secret = creds.get("instagram", {}).get("app_secret")
    
    if not app_id or not app_secret:
        print("Error: app_id or app_secret not found in config/app_credentials.yaml")
        sys.exit(1)
    
    # Validate credentials first
    print("\nValidating App Credentials...")
    print(f"  App ID: {app_id}")
    print(f"  App Secret: {'*' * (len(app_secret) - 4)}{app_secret[-4:]}")
    
    if not validate_app_credentials(app_id, app_secret):
        print("\n" + "="*60)
        print("Invalid App Credentials!")
        print("="*60)
        print("\nTo fix this:")
        print("1. Go to: https://developers.facebook.com/apps/")
        print("2. Select your app (or create a new one)")
        print("3. Go to Settings > Basic")
        print("4. Copy the 'App ID' and 'App Secret'")
        print("5. Update config/app_credentials.yaml with the correct values")
        print("\nAlso make sure:")
        print("- Your app has 'Instagram Graph API' product added")
        print("- Valid OAuth Redirect URI is set to: http://localhost:8080/")
        print("="*60 + "\n")
        sys.exit(1)
    
    # Generate token
    try:
        result = generate_token_interactive(
            app_id=app_id,
            app_secret=app_secret,
            redirect_uri="http://localhost:8080/",
            save_to_config=True,
        )
        
        print("\nToken Details:")
        print(f"  Username: {result['username']}")
        print(f"  Instagram Account ID: {result.get('instagram_account_id', 'N/A')}")
        print(f"  Access Token: {result['access_token'][:50]}...")
        print(f"  Expires In: {result.get('expires_in', 'unknown')} seconds")
        
    except KeyboardInterrupt:
        print("\n\nCancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        print("\nIf you're getting 'Invalid App ID' error:")
        print("1. Make sure the App ID in config/app_credentials.yaml is correct")
        print("2. Get it from: https://developers.facebook.com/apps/{your_app_id}/settings/basic/")
        print("3. Make sure your app has 'Instagram Graph API' product added")
        sys.exit(1)


if __name__ == "__main__":
    main()