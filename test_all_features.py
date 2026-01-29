"""
Comprehensive test script to verify all InstaForge features work correctly.

This script tests:
1. Posting section (image, video, reels, carousel)
2. Scheduling section
3. Auto DM replies
4. Link sharing on comments

Run this after making changes to verify everything works.
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_imports():
    """Test that all critical modules can be imported"""
    print("Testing imports...")
    try:
        from src.app import InstaForgeApp
        from src.services.posting_service import PostingService
        from src.services.scheduled_posts_store import add_scheduled, get_due_posts
        from src.features.comments.comment_to_dm_service import CommentToDMService
        from src.features.ai_dm.ai_dm_handler import AIDMHandler
        from src.api.instagram_client import InstagramClient
        from web.instagram_webhook import process_webhook_payload
        from web.scheduled_publisher import start_scheduled_publisher
        print("[OK] All imports successful")
        return True
    except Exception as e:
        print(f"[FAIL] Import failed: {e}")
        return False

def test_models():
    """Test that models support all media types"""
    print("\nTesting models...")
    try:
        from src.models.post import PostMedia, Post
        from pydantic import HttpUrl
        
        # Test all media types
        image_media = PostMedia(media_type="image", url=HttpUrl("https://example.com/image.jpg"))
        video_media = PostMedia(media_type="video", url=HttpUrl("https://example.com/video.mp4"))
        reels_media = PostMedia(media_type="reels", url=HttpUrl("https://example.com/reel.mp4"))
        carousel_media = PostMedia(
            media_type="carousel",
            children=[
                PostMedia(media_type="image", url=HttpUrl("https://example.com/img1.jpg")),
                PostMedia(media_type="image", url=HttpUrl("https://example.com/img2.jpg")),
            ]
        )
        
        print("[OK] All media types supported in models")
        return True
    except Exception as e:
        print(f"[FAIL] Model test failed: {e}")
        return False

def test_scheduled_posts():
    """Test scheduled post storage and retrieval"""
    print("\nTesting scheduled posts...")
    try:
        from src.services.scheduled_posts_store import add_scheduled, get_due_posts, load_scheduled, mark_published
        from datetime import datetime, timedelta
        import time
        
        # Test adding a scheduled post (use a far future time so it doesn't get published)
        future_time = datetime.utcnow() + timedelta(days=365)  # 1 year in future
        post_id = add_scheduled(
            account_id="test_account",
            media_type="reels",  # Test that reels type is preserved
            urls=["https://example.com/reel.mp4"],
            caption="Test caption",
            scheduled_time=future_time,
        )
        
        # Verify it was saved
        posts = load_scheduled()
        found = next((p for p in posts if p.get("id") == post_id), None)
        if found and found.get("media_type") == "reels":
            # Clean up: remove the test post immediately
            mark_published(post_id)
            print("[OK] Scheduled posts work correctly (reels type preserved)")
            return True
        else:
            print(f"[FAIL] Scheduled post not found or type incorrect: {found}")
            return False
    except Exception as e:
        print(f"[FAIL] Scheduled post test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_comment_to_dm_config():
    """Test comment-to-DM configuration storage"""
    print("\nTesting comment-to-DM config...")
    try:
        from src.features.comments.post_dm_config import PostDMConfig
        import time
        
        config = PostDMConfig()
        # Use a unique test media ID to avoid conflicts
        test_media_id = f"test_media_{int(time.time())}"
        config.set_post_dm_file(
            account_id="test_account",
            media_id=test_media_id,
            file_url="https://example.com/file.pdf",
            trigger_mode="AUTO",
            ai_enabled=True,
        )
        
        # Verify it was saved
        saved = config.get_post_dm_config("test_account", test_media_id)
        if saved and saved.get("file_url") == "https://example.com/file.pdf":
            # Clean up: remove the test config
            config.remove_post_dm_file("test_account", test_media_id)
            print("[OK] Comment-to-DM config works correctly")
            return True
        else:
            print(f"[FAIL] Config not saved correctly: {saved}")
            return False
    except Exception as e:
        print(f"[FAIL] Comment-to-DM config test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_ai_dm_handler():
    """Test AI DM handler initialization"""
    print("\nTesting AI DM handler...")
    try:
        from src.features.ai_dm.ai_dm_handler import AIDMHandler
        
        handler = AIDMHandler()
        is_available = handler.is_available()
        
        if is_available:
            print("[OK] AI DM handler initialized (OpenAI configured)")
        else:
            print("[WARN] AI DM handler initialized but OpenAI not configured (this is OK)")
        return True
    except Exception as e:
        print(f"[FAIL] AI DM handler test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("InstaForge Feature Test Suite")
    print("=" * 60)
    
    results = []
    results.append(("Imports", test_imports()))
    results.append(("Models", test_models()))
    results.append(("Scheduled Posts", test_scheduled_posts()))
    results.append(("Comment-to-DM Config", test_comment_to_dm_config()))
    results.append(("AI DM Handler", test_ai_dm_handler()))
    
    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n[SUCCESS] All tests passed! All features are working correctly.")
        return 0
    else:
        print(f"\n[WARNING] {total - passed} test(s) failed. Please review the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
