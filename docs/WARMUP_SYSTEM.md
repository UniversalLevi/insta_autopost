# Instagram 5-Day Account Warm-Up System

## Overview

The Warm-Up System helps old or risky Instagram accounts regain trust safely before automation. It combines **manual guidance**, **light automation** (where allowed), **activity tracking**, and **safety controls** — without violating Meta policies.

## Feature Status

- **Optional per account** — does not affect accounts not in warm-up
- **Isolated module** — no changes to existing posting, scheduling, AI DM, or Comment-to-DM
- **Backward compatible** — all new code in `src/features/warmup/`, `src/middleware/`

## Architecture

```
src/features/warmup/
├── __init__.py
├── warmup_store.py           # data/warmup_plans.json, data/warmup_reports.json
├── warmup_engine.py          # WarmupEngine - day logic, tasks, progress
├── warmup_automation.py      # WarmupAutomation - runs like/comment/save via browser
├── warmup_automation_config.py  # Per-account automation settings
├── day_plans.py              # 5-day task definitions
└── risk_monitor.py           # API errors, login failures, auto-pause

web/
├── warmup_automation_scheduler.py  # Background scheduler for warm-up automation

src/middleware/
└── warmup_guard.py      # is_warmup_active(), warmup_allows_action()

web/
├── templates/warmup.html
└── api.py               # /api/warmup/* endpoints
```

## Data Model

### warmup_plans.json

```json
{
  "plans": [
    {
      "account_id": "...",
      "instagram_id": "...",
      "start_date": "2026-02-03",
      "current_day": 1,
      "status": "active|completed|paused|failed",
      "last_action_time": "2026-02-03T12:00:00",
      "risk_score": 0,
      "daily_actions_completed": {},
      "completed_tasks": [],
      "notes": "",
      "created_at": "...",
      "updated_at": "..."
    }
  ]
}
```

### warmup_reports.json

Generated when Day 5 completes. Contains engagement change, reach improvement, account health, recommendation.

## 5-Day Plan

| Day | Focus | Tasks |
|-----|-------|-------|
| 1 | Reset | Bio update, profile pic, follow 10–15, watch reels, like 10, comment 5, save 3. No post, no DM |
| 2 | Watch Training | Rewatch reels, like 15, comment 5–7, save 5, share 2 to story |
| 3 | Soft Spike | Follow 5–8, reply 2 stories, 2 story DMs, watch 30–40, comment 8, save 5 |
| 4 | Pre-Post | Post 1 story (poll/question), watch reels, comment 10, save 7 |
| 5 | Post Day | Post 1 reel (6–9 PM local), monitor engagement |

## API Endpoints

All require authentication (`require_auth`).

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/warmup/start` | Start warm-up. Body: `{account_id, instagram_id?}` |
| GET | `/api/warmup/status?account_id=` | Get plan + today's tasks |
| POST | `/api/warmup/complete-task` | Mark task done. Body: `{account_id, task_id, count?}` |
| POST | `/api/warmup/complete-day` | Advance day (or finish). Body: `{account_id}` |
| POST | `/api/warmup/pause` | Pause. Body: `{account_id, reason?}` |
| POST | `/api/warmup/resume` | Resume. Body: `{account_id}` |
| GET | `/api/warmup/automation-config?account_id=` | Get automation config |
| PUT | `/api/warmup/automation-config` | Update. Body: `{account_id, automation_enabled?, target_hashtags?, schedule_times?}` |

## UI Dashboard

- **Route:** `/warmup`
- **Features:** Account selector, Start Warm-Up, day progress bar, task checklist, Pause/Resume, Complete Day
- **Design:** White theme, green/yellow/red risk indicators

## Integration Points

### WarmupGuard Middleware

Before bulk posting, mass DM, campaigns, or broadcasts:

```python
from src.middleware.warmup_guard import is_warmup_active, warmup_allows_action

if is_warmup_active(account_id):
    allowed, reason = warmup_allows_action(account_id, "bulk_post")
    if not allowed:
        raise Error(reason)
```

**During warm-up:**
- ❌ Disabled: bulk_post, mass_dm, campaign, broadcast
- ✅ Allowed: guided actions, safe API calls, manual confirmations

### Risk Monitor

- Auto-pause on API error 429 (rate limit) or 190 (token)
- Tracks login failures, reach drops
- Risk score 0–100; pause recommended at ≥80

### Reporting

When Day 5 completes, a report is saved to `data/warmup_reports.json` with:
- engagement_change
- reach_improvement
- account_health
- recommendation

## Automation

When **automation_enabled** is true and the account has an active warm-up:

- **Discovery**: Browser navigates to hashtag Explore pages (from target_hashtags) and collects post URLs
- **Actions**: Like, comment, save run automatically via Playwright browser
- **Schedule**: Runs at configured hours (default 9, 14, 18)
- **Requirements**: Playwright (`pip install playwright && playwright install chromium`), account password for browser login

Configure in the warm-up UI: enable automation, set hashtags (e.g. `fitness, travel`), save.

## Running Tests

```bash
pytest tests/test_warmup_engine.py -v
```

## Notifications (Phase 8)

Currently via:
- **Dashboard** — warnings and status in warmup UI
- **Logs** — structured logging for warmup events

Email notifications can be added later without changing the core module.
