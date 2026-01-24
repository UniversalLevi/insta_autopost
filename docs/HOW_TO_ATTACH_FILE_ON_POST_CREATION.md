# How to Attach PDF/Link File When Creating a Post

## ✅ Feature Added!

You can now attach a PDF file or link **while creating a new post**. When someone comments on that post, they'll automatically receive this file via DM.

## How to Use

### Step 1: Create Your Post

1. Go to the **Post** page (http://localhost:8000)
2. Fill in your post details:
   - Select media type (Image, Video, Carousel, Reels)
   - Upload your media files
   - Add caption
   - Select account

### Step 2: Attach Auto-DM File

Scroll down to the **"Auto-DM File (Optional)"** section:

**Option A: Upload PDF File**
1. Select **"Upload PDF"** radio button
2. Click **"Choose PDF File"**
3. Select your PDF file (e.g., `2508843519.pdf`)
4. The file will be uploaded and shown

**Option B: Use File Path/URL** (Recommended for local files)
1. Select **"Use File Path/URL"** radio button (default)
2. Enter your file path: `C:/Users/kanis/Downloads/2508843519.pdf`
3. Or enter a web URL: `https://example.com/file.pdf`

### Step 3: Create Post

1. Click **"Create Post"**
2. The system will:
   - Create your Instagram post
   - Automatically attach the DM file to that post
   - Set up auto-DM so comments trigger file delivery

## What Happens Next

When someone comments on your post:
- ✅ They automatically receive the PDF/link via DM
- ✅ The file you attached is sent to them
- ✅ Works automatically (no manual action needed)

## File Path Examples

- **Local PDF**: `C:/Users/kanis/Downloads/2508843519.pdf`
- **Web URL**: `https://example.com/download/file.pdf`
- **File URL**: `file:///C:/Users/kanis/Downloads/file.pdf`

## Important Notes

1. **For Local Files**: Use the file path format (e.g., `C:/Users/kanis/Downloads/file.pdf`)
2. **For Web Files**: Use HTTPS URLs (e.g., `https://example.com/file.pdf`)
3. **Upload Option**: If you upload a PDF, it will be uploaded to your server/Cloudinary first

## Troubleshooting

### File Not Attached
- Check that you entered a valid file path or URL
- Make sure the post was created successfully (check post ID)
- The file attachment happens automatically after post creation

### DM Not Sending
- Ensure `comment_to_dm.enabled: true` in `config/accounts.yaml`
- Check Instagram API permissions (may need to fix token permissions)
- Verify file path is accessible

### Can't Upload PDF
- Make sure you selected "Upload PDF" option
- File must be a PDF (`.pdf` extension)
- Check file size limits

---

**This feature works seamlessly with the Published Posts page** - you can also attach/change files there if needed!
