# Meta / Instagram App Setup – Fill-ups for InstaForge (insta_autopost)

Use this guide to fill each Meta Developer page so OAuth and webhooks work with your project.  
Your app uses **BASE_URL** (e.g. `https://veilforce.com`) from `.env`. All URLs below assume that domain; replace with your real domain if different.

---

## 1. Client OAuth settings (Valid OAuth Redirect URIs)

**What it does:** After the user logs in with Facebook/Instagram, Meta redirects the browser to one of these URIs with an authorization `code`. Your app exchanges that code for an access token at `/auth/meta/callback`.

**What to fill:**

| Field | Value to enter | Explanation |
|-------|----------------|------------|
| **Valid OAuth Redirect URIs** | `https://veilforce.com/auth/meta/callback` | Exact callback URL. Your code uses `META_REDIRECT_URI` or `BASE_URL` + `/auth/meta/callback`. Must be **HTTPS** (Enforce HTTPS is on). Add one per line if you have multiple (e.g. production + staging). |

**Rules:**

- Must match **exactly** (Strict Mode is on) – no trailing slash, same scheme and host.
- If you use another domain (e.g. `https://yourdomain.com`), add:  
  `https://yourdomain.com/auth/meta/callback`  
  and set `BASE_URL` / `META_REDIRECT_URI` in `.env` to that domain.
- For **local dev** with a tunnel (e.g. ngrok/Cloudflare), add that URL, e.g.  
  `https://xxxx.trycloudflare.com/auth/meta/callback`  
  and set `META_REDIRECT_URI` or `BASE_URL` in `.env` to that base URL.

**Check:** In your app, open:  
`https://veilforce.com/auth/me` (or your BASE_URL) and call `/auth/meta/redirect-uri` – the returned `redirect_uri` must be one of the URIs you added here.

---

## 2. Configure webhook (Instagram product)

**What it does:** Meta sends webhook events (e.g. comments, messages) to your **Callback URL** and verifies it using the **Verify token**.

**What to fill:**

| Field | Value to enter | Explanation |
|-------|----------------|------------|
| **Callback URL** | `https://veilforce.com/webhooks/instagram` | Your app serves the webhook at this path: GET for verification, POST for events. Must be **publicly reachable** (no auth, no localhost). **No trailing slash.** |
| **Verify token** | **Exactly** the same string as in your server’s `.env`: `WEBHOOK_VERIFY_TOKEN` (e.g. `my_instagram_webhook_secret_2024`) | Meta sends it in `hub.verify_token`; your app compares it and responds with `hub.challenge`. If they differ, Meta gets 403 and says “not valid callback URL”. |

**Important:**

- Do **not** use `/api/webhooks/callback-url` as the Callback URL – that’s an API helper. The real endpoint is **`/webhooks/instagram`**.
- The **Verify token** in Meta must be **character-for-character identical** to **`WEBHOOK_VERIFY_TOKEN`** on the **server that serves** `https://veilforce.com` (the same machine’s `.env`). No extra spaces, no typos.
- After saving, click **Verify and save**. Meta sends a GET to your Callback URL; your app must be running and the token must match.

**Note:** If the app is **unpublished**, only test webhooks from the dashboard are sent. For production data, the app must be **Live**.

---

## 3. App basic settings (App domains, Privacy, Terms, etc.)

**What to fill:**

| Field | Value to enter | Explanation |
|-------|----------------|------------|
| **App domains** | `veilforce.com` | Domain where your app/login is served (no `https://`, no path). Required for redirect/login validation. If you use another domain, put that (e.g. `yourdomain.com`). |
| **Privacy policy URL** | `https://veilforce.com/privacy` or a full URL to your policy | Meta requires a public URL. Host a page (e.g. `/privacy`) that describes what data you collect and how you use it. |
| **Terms of Service URL** | `https://veilforce.com/terms` or a full URL to your terms | Same idea – public page with your terms. |
| **User data deletion** | Either “Data deletion instructions URL” → e.g. `https://veilforce.com/data-deletion` or use “Data deletion callback” if you implement the callback | Tells Meta how users can request deletion of their data from your app. |
| **Category** | e.g. **Business** or **Tools** | Pick the best match for an automation/posting tool. |

**Contact email** is already set; **App secret** stays hidden. **Namespace** can stay empty unless you use Open Graph. **App icon** is optional but recommended.

---

## 4. Instagram app (automation-IG) – Configure webhooks

**What it does:** Same as section 2 but in the Instagram product (automation-IG). Callback and verify token must match what your app expects.

**What to fill:**

| Field | Value to enter | Explanation |
|-------|----------------|------------|
| **Callback URL** | `https://veilforce.com/webhooks/instagram` | Same as in section 2 – your single webhook endpoint for Instagram. |
| **Verify token** | Same value as in section 2 (e.g. `my_instagram_webhook_secret_2024`) | Must be identical to **`WEBHOOK_VERIFY_TOKEN`** in `.env`. |

Then click **Verify and save**. Ensure the app is running and `WEBHOOK_VERIFY_TOKEN` is set; otherwise verification will fail.

**Note:** “App mode should be set to Live to receive webhooks” – for production events, set the app to Live. In Development, only test webhooks from the dashboard may be delivered.

---

## Quick reference – URLs used by your project

| Purpose | URL | Used in |
|--------|-----|--------|
| OAuth redirect (callback) | `https://veilforce.com/auth/meta/callback` | Meta → Client OAuth → Valid OAuth Redirect URIs |
| Instagram webhook | `https://veilforce.com/webhooks/instagram` | Meta → Configure webhook (Instagram) + automation-IG webhooks |
| App domain | `veilforce.com` | App basic settings → App domains |
| Privacy / Terms / Data deletion | Your hosted pages, e.g. `https://veilforce.com/privacy`, `/terms`, `/data-deletion` | App basic settings |

---

## Env vars to set on your server

```env
# Already in your .env – keep these
BASE_URL=https://veilforce.com
APP_URL=https://veilforce.com
META_REDIRECT_URI=https://veilforce.com/auth/meta/callback

# Add this so webhook verification matches Meta
WEBHOOK_VERIFY_TOKEN=my_instagram_webhook_secret_2024
```

Use the **same** `WEBHOOK_VERIFY_TOKEN` value in Meta (sections 2 and 4) and in `.env`. After that, fill the four Meta pages as above and run “Verify and save” for webhooks; things should work without failure for OAuth and webhooks.

---

## “Not valid callback URL” – what to check

Meta says the callback URL is not valid when **Verify and save** gets a non‑200 response or the wrong body. Common causes:

1. **Verify token mismatch**  
   - In Meta you typed one string; on the **server that serves veilforce.com** the `.env` has a different `WEBHOOK_VERIFY_TOKEN`.  
   - **Fix:** On the server, open `.env` and set `WEBHOOK_VERIFY_TOKEN=...` to the **exact** string you put in Meta (e.g. `my_instagram_webhook_secret_2024`). Restart the app, then click **Verify and save** again.

2. **URL not reachable**  
   - Meta cannot reach `https://veilforce.com/webhooks/instagram` (e.g. app not running, firewall, or Apache/nginx not proxying to the app).  
   - **Check:** In a browser, open `https://veilforce.com/webhooks/instagram`. You should see a short text message (“Webhook endpoint OK...”). If you get 404/502/timeout, fix your server/proxy so this URL is served by your app.

3. **Wrong URL**  
   - Callback URL must be exactly `https://veilforce.com/webhooks/instagram` (no trailing slash in Meta, no `/api/` in the path). The app also accepts `https://veilforce.com/webhooks/instagram/` (with trailing slash) if your proxy adds it.

4. **App not restarted after changing .env**  
   - After editing `WEBHOOK_VERIFY_TOKEN` in `.env`, restart the process that runs the web app so it loads the new value.
