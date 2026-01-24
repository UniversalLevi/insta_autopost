# Cloudinary Setup Guide

Cloudinary provides reliable media hosting that Instagram can access. This is **highly recommended** over using Cloudflare tunnels.

## Quick Setup

1. **Get Cloudinary Account**
   - Sign up at: https://cloudinary.com
   - Free tier includes 25GB storage

2. **Get Credentials**
   - Go to: https://cloudinary.com/console → Dashboard
   - Find:
     - Cloud Name (e.g., `dtgesg0ps`)
     - API Key (e.g., `858581386324189`)
     - API Secret (click "Reveal" to show)

3. **Set Environment Variables**

   **Option A: Using PowerShell Script**
   ```powershell
   .\scripts\create_env_file.ps1
   ```

   **Option B: Manual Setup**
   - Create `.env` file in project root:
   ```
   CLOUDINARY_CLOUD_NAME=your_cloud_name
   CLOUDINARY_API_KEY=your_api_key
   CLOUDINARY_API_SECRET=your_api_secret
   ```

4. **Restart Server**
   ```bash
   python web_server.py
   ```

You should see:
```
[OK] Cloudinary is configured - using Cloudinary for media uploads
```

## Benefits

✅ **Reliable** - Instagram can always access your media  
✅ **Fast** - Global CDN  
✅ **Free** - 25GB free tier  
✅ **No Setup** - No tunnel configuration needed  

## Verification

After setup, upload an image through the web interface. Check the server logs - you should see:
```
DEBUG: Successfully uploaded to Cloudinary: https://res.cloudinary.com/...
```

If you see Cloudflare URLs instead, verify your `.env` file is correct and restart the server.

## Troubleshooting

- **Invalid Signature Error**: See `docs/TROUBLESHOOTING.md`
- **Not Using Cloudinary**: Verify `.env` file exists and credentials are correct
