# Cloudinary Setup Guide for InstaForge

Cloudinary is a cloud-based media management service that works perfectly with Instagram. It's free to use for small projects and Instagram can access the files without any issues.

## Why Cloudinary?

- ✅ **Free tier**: 25GB storage, 25GB bandwidth per month
- ✅ **Works with Instagram**: No bot blocking issues
- ✅ **Easy setup**: Just 3 environment variables
- ✅ **Fast CDN**: Files are served from a global CDN
- ✅ **Automatic optimization**: Images and videos are optimized automatically

## Step 1: Create a Free Cloudinary Account

1. Go to [https://cloudinary.com/users/register/free](https://cloudinary.com/users/register/free)
2. Sign up with your email (it's free, no credit card required)
3. Verify your email address

## Step 2: Get Your Cloudinary Credentials

1. After logging in, you'll see your **Dashboard**
2. Look for the **Account Details** section
3. You'll see three important values:
   - **Cloud name** (e.g., `d1234567`)
   - **API Key** (e.g., `123456789012345`)
   - **API Secret** (e.g., `abcdefghijklmnopqrstuvwxyz123456`)

## Step 3: Set Environment Variables

### Option A: Using Windows PowerShell (Temporary)

Open PowerShell and run:
```powershell
$env:CLOUDINARY_CLOUD_NAME = "your-cloud-name"
$env:CLOUDINARY_API_KEY = "your-api-key"
$env:CLOUDINARY_API_SECRET = "your-api-secret"
```

Then start your server:
```powershell
python web_server.py
```

**Note:** These will be lost when you close PowerShell.

### Option B: Using .env File (Recommended)

1. Create a file named `.env` in your project root (`D:\InstaForge\.env`)
2. Add these lines (replace with your actual values):
```
CLOUDINARY_CLOUD_NAME=your-cloud-name
CLOUDINARY_API_KEY=your-api-key
CLOUDINARY_API_SECRET=your-api-secret
```

3. The app will automatically load these when starting

**Important:** Add `.env` to `.gitignore` to keep your secrets safe!

### Option C: Windows System Environment Variables (Permanent)

1. Press `Win + R`, type `sysdm.cpl`, press Enter
2. Click **Advanced** tab → **Environment Variables**
3. Under **User variables**, click **New**
4. Add three variables:
   - Variable: `CLOUDINARY_CLOUD_NAME`, Value: `your-cloud-name`
   - Variable: `CLOUDINARY_API_KEY`, Value: `your-api-key`
   - Variable: `CLOUDINARY_API_SECRET`, Value: `your-api-secret`
5. Click **OK** on all dialogs
6. Restart your terminal/server

## Step 4: Install Cloudinary Package

```powershell
pip install cloudinary
```

Or if you're using requirements.txt:
```powershell
pip install -r requirements.txt
```

## Step 5: Test It

1. Start your web server:
   ```powershell
   python web_server.py
   ```

2. Look for this message in the console:
   ```
   DEBUG: Using Cloudinary for file uploads
   ```
   
   If you see "Cloudinary not configured, using local server", check your environment variables.

3. Try uploading an image through the web interface

4. Check the upload URL - it should look like:
   ```
   https://res.cloudinary.com/your-cloud-name/image/upload/v1234567/instaforge/filename.jpg
   ```

## Troubleshooting

### "Cloudinary not configured" message
- Make sure all three environment variables are set
- Check for typos in variable names (they must be exact)
- Restart your server after setting variables

### Upload fails
- Check your Cloudinary credentials are correct
- Verify you're connected to the internet
- Check Cloudinary dashboard for usage limits

### Still using local server URLs
- Verify environment variables are loaded: `echo $env:CLOUDINARY_CLOUD_NAME` (PowerShell)
- Make sure you restarted the server after setting variables

## Free Tier Limits

- **Storage**: 25GB
- **Bandwidth**: 25GB/month
- **Transformations**: Unlimited
- **Concurrent uploads**: Unlimited

For most Instagram posting use cases, this is more than enough!

## Security Notes

- **Never commit your `.env` file to git**
- **Never share your API Secret publicly**
- If you accidentally share it, regenerate it in Cloudinary dashboard: Settings → Security → API Keys → Regenerate Secret

## Need Help?

- Cloudinary Docs: [https://cloudinary.com/documentation](https://cloudinary.com/documentation)
- Cloudinary Support: [https://support.cloudinary.com](https://support.cloudinary.com)
