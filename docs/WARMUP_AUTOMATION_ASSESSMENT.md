# Warm-Up Automation – Full Assessment

## What Works (Fully Automated)

| Task | Days | Status |
|------|------|--------|
| Like posts | 1, 2, 3, 4 | ✅ Automated via browser |
| Comment on posts | 1, 2, 3, 4 | ✅ Automated via browser |
| Save posts | 1, 2, 3, 4 | ✅ Automated via browser |

These run at scheduled hours (9, 14, 18) or via the **Run automation now** button.

---

## What Stays Manual

| Task | Reason |
|------|--------|
| Bio update, profile pic | No API; user must do it |
| Follow accounts | Browser support exists but not wired for warm-up automation |
| Watch reels | No reliable automation; must be done manually |
| Reply to stories, story DMs | Complex; no automation implemented |
| Post story / reel | Requires user decisions and content |

---

## Requirements for Automation to Work

1. **Playwright** – `pip install playwright && playwright install chromium`
2. **Account password** – Stored in account config; needed for browser login
3. **Automation enabled** – Toggle in warm-up UI + Save
4. **Target hashtags** – At least one (e.g. `explore`, `fitness`)

---

## Known Issues (Fixed)

1. **Scheduler timing** – `now.minute > 10` could skip runs; fixed by running whenever the hour matches.
2. **Run now blocking** – Long browser actions were blocking the API; fixed by using a thread pool.

---

## How to Verify

1. Start warm-up for an account.
2. Enable automation and set hashtags.
3. Add account password in config (Accounts → edit).
4. Click **Run automation now** and check logs; tasks should complete.
5. For scheduled runs, ensure the server is running during 9, 14, or 18 o’clock.
