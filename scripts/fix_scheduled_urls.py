"""Fix old Cloudflare tunnel URLs in scheduled posts to use production domain"""

import json
import os
from pathlib import Path
from urllib.parse import urlparse, urlunparse

# Production domain
PRODUCTION_DOMAIN = "https://veilforce.com"

# Path to scheduled posts
DATA_DIR = Path("data")
SCHEDULED_FILE = DATA_DIR / "scheduled_posts.json"


def fix_url(url: str) -> str:
    """Replace Cloudflare tunnel URLs with production domain"""
    if "trycloudflare.com" not in url:
        return url
    
    # Parse the URL
    parsed = urlparse(url)
    
    # Extract the path (e.g., /batch/... or /uploads/batch/...)
    path = parsed.path
    
    # Ensure batch URLs have /uploads/ prefix
    if path.startswith("/batch/"):
        path = "/uploads" + path
    # If it already has /uploads/, keep it
    
    # Remove query parameters (they'll be stripped anyway)
    new_url = urlunparse((
        "https",
        "veilforce.com",
        path,  # Keep the path
        "",  # params
        "",  # query (remove ?t=...)
        ""   # fragment
    ))
    
    return new_url


def main():
    """Fix all scheduled posts with old Cloudflare URLs"""
    if not SCHEDULED_FILE.exists():
        print(f"File not found: {SCHEDULED_FILE}")
        return
    
    # Load scheduled posts
    with open(SCHEDULED_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    posts = data.get("posts", [])
    if not posts:
        print("No scheduled posts found")
        return
    
    fixed_count = 0
    total_posts = len(posts)
    
    # Fix URLs in each post
    for post in posts:
        urls = post.get("urls", [])
        if not urls:
            continue
        
        fixed_urls = []
        for url in urls:
            if "trycloudflare.com" in url:
                new_url = fix_url(url)
                fixed_urls.append(new_url)
                fixed_count += 1
                print(f"Fixed: {url}")
                print(f"  -> {new_url}")
            else:
                fixed_urls.append(url)
        
        post["urls"] = fixed_urls
    
    # Save back
    with open(SCHEDULED_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    
    print(f"\n[SUCCESS] Fixed {fixed_count} URLs in {total_posts} scheduled posts")
    print(f"Saved to: {SCHEDULED_FILE}")


if __name__ == "__main__":
    main()
