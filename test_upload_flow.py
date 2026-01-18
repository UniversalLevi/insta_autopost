#!/usr/bin/env python3
"""Test script to verify upload flow and Instagram API integration"""

import requests
import sys
from pathlib import Path

def test_file_serving(url: str):
    """Test if a file URL is accessible with proper headers"""
    print(f"\n{'='*60}")
    print(f"Testing file serving: {url}")
    print(f"{'='*60}")
    
    # Test 1: HEAD request (like Instagram might do)
    print("\n1. Testing HEAD request (Instagram's initial check)...")
    try:
        headers = {
            "User-Agent": "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)",
            "Accept": "image/*,*/*",
        }
        response = requests.head(url, headers=headers, timeout=10, allow_redirects=True)
        print(f"   Status Code: {response.status_code}")
        print(f"   Content-Type: {response.headers.get('Content-Type', 'NOT SET')}")
        print(f"   Content-Length: {response.headers.get('Content-Length', 'NOT SET')}")
        print(f"   Headers: {dict(response.headers)}")
        
        if response.status_code != 200:
            print(f"   ❌ FAILED: Status code is {response.status_code}, expected 200")
            return False
        
        content_type = response.headers.get("Content-Type", "").lower()
        if not content_type.startswith(("image/", "video/")):
            print(f"   ⚠️  WARNING: Content-Type is '{content_type}', expected 'image/*' or 'video/*'")
            print(f"   This might cause Instagram to reject the media")
        
        print(f"   ✓ HEAD request successful")
    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        return False
    
    # Test 2: GET request (like Instagram fetches the actual file)
    print("\n2. Testing GET request (Instagram's file fetch)...")
    try:
        headers = {
            "User-Agent": "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)",
            "Accept": "image/*,*/*",
        }
        response = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
        print(f"   Status Code: {response.status_code}")
        print(f"   Content-Type: {response.headers.get('Content-Type', 'NOT SET')}")
        print(f"   Content-Length: {len(response.content)} bytes")
        print(f"   Actual file size: {len(response.content)} bytes")
        
        if response.status_code != 200:
            print(f"   ❌ FAILED: Status code is {response.status_code}, expected 200")
            return False
        
        # Check if we got actual image data or HTML
        content_type = response.headers.get("Content-Type", "").lower()
        if "text/html" in content_type:
            print(f"   ❌ CRITICAL: Got HTML instead of image!")
            print(f"   First 200 bytes: {response.content[:200]}")
            return False
        
        if not content_type.startswith(("image/", "video/")):
            print(f"   ⚠️  WARNING: Content-Type is '{content_type}', expected 'image/*' or 'video/*'")
        
        # Check if content looks like binary data
        if len(response.content) < 100:
            print(f"   ⚠️  WARNING: File is very small ({len(response.content)} bytes), might be an error page")
        
        print(f"   ✓ GET request successful, received {len(response.content)} bytes")
    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        return False
    
    # Test 3: Check if URL is accessible from different user agents
    print("\n3. Testing with Instagram's user agent...")
    try:
        headers = {
            "User-Agent": "facebookexternalhit/1.1",
            "Accept": "*/*",
        }
        response = requests.head(url, headers=headers, timeout=10, allow_redirects=True)
        if response.status_code == 200:
            print(f"   ✓ Accessible with Instagram's user agent")
        else:
            print(f"   ❌ Status code {response.status_code} with Instagram's user agent")
            print(f"   This might indicate Cloudflare is blocking Instagram's bot")
            return False
    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        return False
    
    print(f"\n{'='*60}")
    print("✓ All tests passed! File should be accessible to Instagram.")
    print(f"{'='*60}\n")
    return True


def main():
    """Main test function"""
    if len(sys.argv) < 2:
        print("Usage: python test_upload_flow.py <file_url>")
        print("\nExample:")
        print("  python test_upload_flow.py https://your-tunnel.trycloudflare.com/uploads/filename.png")
        sys.exit(1)
    
    url = sys.argv[1]
    
    if not url.startswith("http"):
        print(f"❌ Error: URL must start with http:// or https://")
        sys.exit(1)
    
    success = test_file_serving(url)
    
    if success:
        print("✅ File serving looks good!")
        print("\nIf Instagram still rejects it, the issue might be:")
        print("  1. Cloudflare's trycloudflare.com blocking Instagram's crawler")
        print("  2. Instagram's API rate limiting")
        print("  3. Instagram account permissions or token issues")
    else:
        print("❌ File serving has issues that need to be fixed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
