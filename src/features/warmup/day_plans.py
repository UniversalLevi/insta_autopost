"""
5-Day Warm-Up Plan Definitions - Phase 3
Each day's tasks with limits. Manual tasks require user confirmation.
"""

from typing import Dict, List, Any

# Day 1-5 task definitions. Keys: task_id, label, manual (requires user), target, category
WARMUP_DAY_PLANS: Dict[int, List[Dict[str, Any]]] = {
    1: [
        {"id": "day1_bio", "label": "Update bio (manual)", "manual": True, "target": 1, "category": "profile"},
        {"id": "day1_profile_pic", "label": "Profile pic reminder (manual)", "manual": True, "target": 1, "category": "profile"},
        {"id": "day1_follow", "label": "Follow 10–15 accounts", "manual": True, "target": 12, "category": "engage"},
        {"id": "day1_watch_reels", "label": "Watch 20–30 reels", "manual": True, "target": 25, "category": "engage"},
        {"id": "day1_like", "label": "Like 10 posts", "manual": False, "target": 10, "category": "engage"},
        {"id": "day1_comment", "label": "Comment on 5 posts", "manual": False, "target": 5, "category": "engage"},
        {"id": "day1_save", "label": "Save 3 posts", "manual": False, "target": 3, "category": "engage"},
        # No post, no DM
    ],
    2: [
        {"id": "day2_rewatch", "label": "Rewatch reels", "manual": True, "target": 20, "category": "engage"},
        {"id": "day2_like", "label": "Like 15 posts", "manual": False, "target": 15, "category": "engage"},
        {"id": "day2_comment", "label": "Comment 5–7", "manual": False, "target": 6, "category": "engage"},
        {"id": "day2_save", "label": "Save 5 posts", "manual": False, "target": 5, "category": "engage"},
        {"id": "day2_share_story", "label": "Share 2 to story", "manual": True, "target": 2, "category": "story"},
    ],
    3: [
        {"id": "day3_follow", "label": "Follow 5–8 accounts", "manual": True, "target": 6, "category": "engage"},
        {"id": "day3_reply_story", "label": "Reply to 2 stories", "manual": True, "target": 2, "category": "dm"},
        {"id": "day3_story_dm", "label": "Send 2 story DMs", "manual": True, "target": 2, "category": "dm"},
        {"id": "day3_watch", "label": "Watch 30–40 reels", "manual": True, "target": 35, "category": "engage"},
        {"id": "day3_comment", "label": "Comment on 8 posts", "manual": False, "target": 8, "category": "engage"},
        {"id": "day3_save", "label": "Save 5 posts", "manual": False, "target": 5, "category": "engage"},
    ],
    4: [
        {"id": "day4_story", "label": "Post 1 story (poll/question)", "manual": True, "target": 1, "category": "post"},
        {"id": "day4_watch", "label": "Watch reels (under 200k followers)", "manual": True, "target": 30, "category": "engage"},
        {"id": "day4_comment", "label": "Comment on 10 posts", "manual": False, "target": 10, "category": "engage"},
        {"id": "day4_save", "label": "Save 7 posts", "manual": False, "target": 7, "category": "engage"},
    ],
    5: [
        {"id": "day5_reel", "label": "Post 1 reel (6–9 PM local)", "manual": True, "target": 1, "category": "post"},
        {"id": "day5_monitor", "label": "Monitor engagement", "manual": True, "target": 1, "category": "monitor"},
    ],
}

# Safety limits per day
MAX_ACTIONS_PER_HOUR = 20
COOLDOWN_MINUTES = 5
AUTO_PAUSE_ERROR_CODES = [429, 190]  # Rate limit, token expired
