# Quick Start: Post-Specific Auto-DM Feature

## ✅ Feature Implemented!

You can now attach a PDF/file to each post. When someone comments on that post, they'll automatically receive the file link via DM.

## How to Use

1. **Go to Published Posts page** (http://localhost:8000/posts)

2. **Click "📎 Attach File" button** on any post

3. **Enter your file path**:
   - Local file: `C:/Users/kanis/Downloads/2508843519.pdf`
   - Web URL: `https://example.com/file.pdf`

4. **Click "Save"**

5. **Done!** When someone comments on that post, they'll receive the file link automatically.

## Your Specific File

To attach your PDF:
```
C:/Users/kanis/Downloads/2508843519.pdf
```

Just paste this path in the modal when you click "Attach File" on any post.

## How It Works

- ✅ **Per-Post Configuration**: Each post can have its own file
- ✅ **Auto-DM**: Comments trigger automatic DM with file link
- ✅ **Visual Indicator**: Posts with attached files show "📎 File Attached"
- ✅ **Easy Management**: Remove or change files anytime

## Requirements

1. **Enable Comment-to-DM** in `config/accounts.yaml`:
   ```yaml
   comment_to_dm:
     enabled: true
     trigger_keyword: "AUTO"  # Any comment triggers DM
   ```

2. **Restart server**: `python web_server.py`

3. **Start using**: Go to Published Posts page and attach files!

---

**Note**: The file path will be sent as-is in the DM. Make sure users can access the file (if it's a local file, they need access to that path, or use a web URL).
