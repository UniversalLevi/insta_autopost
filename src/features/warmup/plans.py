"""
5-Day Warm-Up Plan Definitions - Single source of truth.
Based on INSTA WARM UP GUIDE.
"""

from typing import Dict, List
from .models import WarmupTask

# Day 1-5 task definitions
WARMUP_DAY_PLANS: Dict[int, List[WarmupTask]] = {
    1: [
        WarmupTask("day1_bio", "Update bio (manual)", manual=True, target=1, category="profile"),
        WarmupTask("day1_profile_pic", "Profile pic reminder (manual)", manual=True, target=1, category="profile"),
        WarmupTask("day1_delete_archive", "Delete/archive dead posts (manual)", manual=True, target=1, category="profile"),
        WarmupTask("day1_follow", "Follow 10–15 niche accounts", manual=True, target=12, category="engage"),
        WarmupTask("day1_watch_reels", "Watch 20–30 reels fully", manual=True, target=25, category="engage"),
        WarmupTask("day1_like", "Like 10 posts", manual=False, target=10, category="engage"),
        WarmupTask("day1_comment", "Comment on 5 posts", manual=False, target=5, category="engage"),
        WarmupTask("day1_save", "Save 3 posts", manual=False, target=3, category="engage"),
    ],
    2: [
        WarmupTask("day2_niche_search", "Search niche keyword, watch top reels", manual=True, target=1, category="engage"),
        WarmupTask("day2_rewatch", "Rewatch 3–4 reels", manual=True, target=4, category="engage"),
        WarmupTask("day2_like", "Like 15 posts", manual=False, target=15, category="engage"),
        WarmupTask("day2_comment", "Comment 5–7", manual=False, target=6, category="engage"),
        WarmupTask("day2_save", "Save 5 posts", manual=False, target=5, category="engage"),
        WarmupTask("day2_share_story", "Share 2 reels to story", manual=True, target=2, category="story"),
    ],
    3: [
        WarmupTask("day3_follow", "Follow 5–8 niche accounts", manual=True, target=6, category="engage"),
        WarmupTask("day3_reply_story", "Reply to 2–3 story polls/questions", manual=True, target=3, category="dm"),
        WarmupTask("day3_story_dm", "Send 2 genuine DMs (reply to stories)", manual=True, target=2, category="dm"),
        WarmupTask("day3_watch", "Watch 30–40 reels", manual=True, target=35, category="engage"),
        WarmupTask("day3_comment", "Comment on 8 posts", manual=False, target=8, category="engage"),
        WarmupTask("day3_save", "Save 5 posts", manual=False, target=5, category="engage"),
    ],
    4: [
        WarmupTask("day4_story", "Post 1 story (poll/question)", manual=True, target=1, category="post"),
        WarmupTask("day4_watch", "Watch reels (under 200k followers)", manual=True, target=30, category="engage"),
        WarmupTask("day4_comment", "Comment on 10 posts", manual=False, target=10, category="engage"),
        WarmupTask("day4_save", "Save 7 posts", manual=False, target=7, category="engage"),
    ],
    5: [
        WarmupTask("day5_reel", "Post 1 reel (6–9 PM local)", manual=True, target=1, category="post"),
        WarmupTask("day5_monitor", "Monitor engagement", manual=True, target=1, category="monitor"),
    ],
}


def get_tasks_for_day(day: int) -> List[WarmupTask]:
    """Get all tasks for a given day."""
    return WARMUP_DAY_PLANS.get(min(5, max(1, day)), [])


def get_automatable_tasks(day: int) -> List[WarmupTask]:
    """Get tasks that can be automated (manual=False)."""
    return [t for t in get_tasks_for_day(day) if not t.manual]
