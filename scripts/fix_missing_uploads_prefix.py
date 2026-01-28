"""Fix batch URLs missing /uploads/ prefix"""

import json
from pathlib import Path

DATA_DIR = Path("data")
SCHEDULED_FILE = DATA_DIR / "scheduled_posts.json"


def main():
    """Fix batch URLs missing /uploads/ prefix"""
    if not SCHEDULED_FILE.exists():
        print(f"File not found: {SCHEDULED_FILE}")
        return
    
    with open(SCHEDULED_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    posts = data.get("posts", [])
    fixed_count = 0
    
    for post in posts:
        urls = post.get("urls", [])
        if not urls:
            continue
        
        fixed_urls = []
        for url in urls:
            # Check if URL is missing /uploads/ prefix for batch files
            if "veilforce.com/batch/" in url and "/uploads/batch/" not in url:
                new_url = url.replace("veilforce.com/batch/", "veilforce.com/uploads/batch/")
                fixed_urls.append(new_url)
                fixed_count += 1
                print(f"Fixed: {url}")
                print(f"  -> {new_url}")
            else:
                fixed_urls.append(url)
        
        post["urls"] = fixed_urls
    
    with open(SCHEDULED_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    
    print(f"\n[SUCCESS] Fixed {fixed_count} URLs missing /uploads/ prefix")


if __name__ == "__main__":
    main()
