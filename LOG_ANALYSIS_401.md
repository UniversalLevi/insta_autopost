# Log Analysis: 401 Unauthorized

## Issue
```
"POST /api/posts/create HTTP/1.1" 401 Unauthorized
```

## Meaning
This is a **web dashboard login error**, not an API error.
- It means your browser session expired.
- You were logged out of the web dashboard (localhost:8000).

## Solution
1. **Go to the login page**: You were already redirected there (`GET /login 200 OK`).
2. **Log in again**:
   - Default password: `admin` (unless you changed it).
3. **Try posting again**.

## Status
- **Server**: Running perfectly ✅
- **Instagram Token**: Valid ✅
- **Rate Limit**: Cleared (after restart) ✅
- **You**: Just need to log in to the dashboard again.
