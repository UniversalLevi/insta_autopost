# InstaForge Deployment Checklist

Use this checklist before deploying to production. Verify each feature works for **all connected accounts** (including Meta OAuth–connected accounts).

---

## 1. Multi-Account & Posting

| Check | Status | Notes |
|-------|--------|--------|
| Multiple accounts appear in account selector on Posting page | ☐ | Settings → Accounts; add manually or via Meta |
| Posting works for each selected account | ☐ | Post Now with each account selected |
| Scheduled post can be set (date/time) and appears in queue | ☐ | Use "Schedule (Optional)" datetime picker |
| Scheduled posts publish at the correct time | ☐ | Wait for due time or use a near-future time to test |
| Batch Upload (30 Days) – select account, start/end date, upload files | ☐ | Max 31 files; distributed across date range |
| 30-day scheduling: posts scheduled up to 30+ days ahead are stored and published when due | ☐ | No backend limit; scheduler runs every 60s |

---

## 2. Meta Login & Full Instagram Access

| Check | Status | Notes |
|-------|--------|--------|
| "Connect with Meta" on Posting page opens Meta OAuth | ☐ | Link: `/auth/meta/login` → redirects to Meta |
| After Meta login, user is redirected back and account is saved | ☐ | Callback saves to `data/accounts.yaml` |
| New Meta account appears in account selector immediately (or after refresh) | ☐ | Reload uses `reload_accounts()` so new account is registered |
| New Meta account can post (now and scheduled) | ☐ | Same as manual account |
| New Meta account gets comment-to-DM, AI DM, warming | ☐ | All services use `account_service.list_accounts()` |
| All web features work on Meta-connected Instagram same as primary account | ☐ | Posting, schedule, batch, comment-to-DM, AI DM, warming |

---

## 3. Automation: Comment-to-DM & DM Reply

| Check | Status | Notes |
|-------|--------|--------|
| Comment-to-DM enabled per account (Settings → account → Enable Comment Auto-DM) | ☐ | |
| Trigger keyword works (e.g. "AUTO" or custom) | ☐ | Comment containing keyword triggers DM |
| DM with link/file is sent when trigger matches | ☐ | 24h window: user must have messaged first |
| AI DM auto-reply works when enabled per account | ☐ | Incoming DM → AI reply sent |
| AI DM respects rate limit (e.g. 10/user/day) | ☐ | Check `data/ai_dm_tracking.json` |
| Comment monitor runs for all accounts | ☐ | Each account has its own monitor thread |

---

## 4. AI Customization

| Check | Status | Notes |
|-------|--------|--------|
| AI Customization page loads (/ai-settings) | ☐ | |
| Business Info, Personality, Custom Rules, Advanced, Memory tabs work | ☐ | |
| Communication Tone: Friendly, Professional, Casual, Enthusiastic, Helpful | ☐ | |
| Communication Tone: **Custom** – option visible and usable | ☐ | Select "Custom", enter custom tone description, save |
| Custom tone description is saved and used in AI replies | ☐ | Check profile has `tone: custom` and `custom_tone: "..."` |
| Custom rules and custom prompt are applied in AI replies | ☐ | |
| Memory & Stats show (optional) | ☐ | |

---

## 5. Warming

| Check | Status | Notes |
|-------|--------|--------|
| Warming schedule time is set (Settings → Global → Warming Schedule Time) | ☐ | e.g. 09:00 |
| Warming enabled per account (account modal → Enable Warming) | ☐ | |
| Warming runs at scheduled time for **all** accounts with warming enabled | ☐ | `execute_warming_for_all_accounts()` loops every account |
| Warming actions (like, comment, etc.) execute per account without breaking others | ☐ | One account failure should not stop others |

---

## 6. Scheduling (Including 30 Days)

| Check | Status | Notes |
|-------|--------|--------|
| Single post: schedule for tomorrow → stored and published at time | ☐ | |
| Batch: start date + end date (e.g. 30 days), multiple files → all scheduled | ☐ | |
| Batch: no end date → daily from start date for each file | ☐ | |
| Scheduled publisher runs every 60s and publishes due posts | ☐ | Logs: "Scheduled post published" |
| No artificial limit on how far ahead (e.g. 30 days) scheduling is allowed | ☐ | Backend accepts any future `scheduled_time` |

---

## 7. Account Status & Health

| Check | Status | Notes |
|-------|--------|--------|
| Account Status page (/accounts) loads | ☐ | |
| Each account shows health (token, permissions, API, etc.) | ☐ | |
| "Refresh Status" updates health | ☐ | |
| "Reload Accounts" reloads from config and re-registers services | ☐ | Use after adding/editing accounts in YAML or Meta |

---

## 8. Configuration & Security

| Check | Status | Notes |
|-------|--------|--------|
| `data/accounts.yaml` – no sensitive tokens in version control | ☐ | Use env or secrets in production |
| `META_APP_ID`, `META_APP_SECRET`, `META_REDIRECT_URI` set for OAuth | ☐ | Required for "Connect with Meta" |
| `BASE_URL` set to your public domain (e.g. `https://veilforce.com`) | ☐ | Required so uploads and webhook URL work; see docs/VEILFORCE_DEPLOYMENT.md if app not running on your domain |
| `OPENAI_API_KEY` set if AI DM or AI customization is used | ☐ | |
| Webhook URL (if used) is HTTPS and reachable by Meta | ☐ | |

---

## Quick Test Flow (Single + Multi-Account)

1. **Manual account**: Add one account in Settings, post now, schedule one post, enable comment-to-DM and AI DM, run warming once from API or wait for schedule.
2. **Meta account**: Click "Connect with Meta", complete Meta login, confirm new account in selector, post and schedule from that account, confirm comment/AI DM/warming apply.
3. **AI Custom**: Set Communication Tone to Custom, enter custom tone, save, send a test DM and confirm reply matches tone.
4. **30-day**: Batch upload 3–5 files with start date today and end date 30 days ahead; confirm all scheduled and one publishes when due.

---

## When Done

- All items above checked for your deployment (single + multi-account).
- Logs and Account Status show no critical errors.
- Document any env-specific or server-specific steps for your team.

**Last updated**: Pre-deploy verification. Adjust checklist as features change.
