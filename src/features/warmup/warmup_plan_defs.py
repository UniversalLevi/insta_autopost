"""
5-Day Warm-Up Plan Definitions - Phase 3
Exact task lists per day. All tasks are MANUAL or GUIDED except where noted.
"""

from typing import Dict, List, Any

# Day 1-5 task definitions. Each task has: id, label, manual (True=user must do), target (e.g. count)
WARMUP_DAYS: Dict[int, List[Dict[str, Any]]] = {
    1: [
        {"id": "bio_update", "label": "Update bio (manual)", "manual": True, "target": 1},
        {"id": "profile_pic", "label": "Profile pic reminder (manual)", "manual": True, "target": 1},
        {"id": "follow", "label": "Follow 10-15 accounts", "manual": True, "target": 12},
        {"id": "watch_reels", "label": "Watch 20-30 reels", "manual": True, "target": 25},
        {"id": "like", "label": "Like 10 posts", "manual": True, "target": 10},
        {"id": "comment", "label": "Comment on 5 posts", "manual": True, "target": 5},
        {"id": "save", "label": "Save 3 posts", "manual": True, "target": 3},
        # No post, no DM on Day 1
    ],
    2: [
        {"id": "rewatch_reels", "label": "Rewatch reels", "manual": True, "target": 1},
        {"id": "like", "label": "Like 15 posts", "manual": True, "target": 15},
        {"id": "comment", "label": "Comment on 5-7 posts", "manual": True, "target": 6},
        {"id": "save", "label": "Save 5 posts", "manual": True, "target": 5},
        {"id": "share_story", "label": "Share 2 posts to story", "manual": True, "target": 2},
    ],
    3: [
        {"id": "follow", "label": "Follow 5-8 accounts", "manual": True, "target": 6},
        {"id": "reply_story", "label": "Reply to 2 stories", "manual": True, "target": 2},
        {"id": "story_dm", "label": "Send 2 story DMs", "manual": True, "target": 2},
        {"id": "watch_reels", "label": "Watch 30-40 reels", "manual": True, "target": 35},
        {"id": "comment", "label": "Comment on 8 posts", "manual": True, "target": 8},
        {"id": "save", "label": "Save 5 posts", "manual": True, "target": 5},
    ],
    4: [
        {"id": "post_story", "label": "Post 1 story (poll/question)", "manual": True, "target": 1},
        {"id": "watch_reels", "label": "Watch reels (under 200k followers)", "manual": True, "target": 1},
        {"id": "comment", "label": "Comment on 10 posts", "manual": True, "target": 10},
        {"id": "save", "label": "Save 7 posts", "manual": True, "target": 7},
    ],
    5: [
        {"id": "post_reel", "label": "Post 1 reel (6-9 PM local)", "manual": True, "target": 1},
        {"id": "monitor_engagement", "label": "Monitor engagement", "manual": True, "target": 1},
    ],
}

# Safety limits
MAX_ACTIONS_PER_HOUR = 30
COOLDOWN_MINUTES = 5
AUTO_PAUSE_ERROR_CODES = {429, 190}
