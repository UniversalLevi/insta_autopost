"""Check for recent comments on posts"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.app import InstaForgeApp

app = InstaForgeApp()
app.initialize()

account_id = "1405915827600672"
account = app.account_service.get_account(account_id)

print(f"\n{'='*60}")
print(f"Checking Comments for: {account.username}")
print(f"{'='*60}\n")

# Get recent media
client = app.account_service.get_client(account_id)
try:
    media_response = client._make_request(
        "GET",
        "me/media",
        params={
            "fields": "id,caption,comments_count,like_count,timestamp",
            "limit": 5,
        }
    )
    
    recent_posts = media_response.get("data", [])
    
    print(f"Found {len(recent_posts)} recent posts:\n")
    
    for idx, post in enumerate(recent_posts, 1):
        media_id = post.get("id")
        caption = post.get("caption", "")[:50] if post.get("caption") else "No caption"
        comments_count = post.get("comments_count", 0)
        like_count = post.get("like_count", 0)
        
        print(f"{idx}. Post ID: {media_id}")
        print(f"   Caption: {caption}...")
        print(f"   Comments: {comments_count} | Likes: {like_count}")
        
        # Try to get actual comments
        try:
            comments_response = client._make_request(
                "GET",
                f"{media_id}/comments",
                params={
                    "fields": "id,text,username,timestamp",
                    "limit": 10,
                }
            )
            
            comments = comments_response.get("data", [])
            print(f"   API Returned: {len(comments)} comment(s)")
            
            if comments_count > 0 and len(comments) == 0:
                print(f"   [WARNING] Post shows {comments_count} comments but API returned 0!")
                print(f"   [WARNING] Missing 'instagram_manage_comments' permission!")
            elif len(comments) > 0:
                print(f"   [OK] Comments detected:")
                for comment in comments[:3]:  # Show first 3
                    username = comment.get("username", "Unknown")
                    text = comment.get("text", "")[:40]
                    print(f"      - @{username}: {text}...")
        
        except Exception as e:
            print(f"   [ERROR] Error getting comments: {str(e)}")
        
        print()
    
    print(f"{'='*60}")
    print("\nStatus:")
    dm_enabled = account.comment_to_dm.enabled if hasattr(account, 'comment_to_dm') and account.comment_to_dm else False
    print(f"  Comment-to-DM enabled: {dm_enabled}")
    print(f"  Auto-reply enabled: {app.comment_service.auto_reply_enabled}")
    
    if not dm_enabled:
        print("\n[ACTION NEEDED] Comment-to-DM is DISABLED!")
        print("  To enable: Set 'enabled: true' in config/accounts.yaml")
    
    print(f"\n{'='*60}\n")

except Exception as e:
    print(f"Error: {str(e)}")
    sys.exit(1)
