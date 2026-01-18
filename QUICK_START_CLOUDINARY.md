# Quick Start: Cloudinary Setup (2 minutes)

## Step 1: Sign Up (30 seconds)
1. Go to: https://cloudinary.com/users/register/free
2. Sign up with your email (free, no credit card)
3. Verify your email

## Step 2: Get Your Credentials (30 seconds)
1. After logging in, go to Dashboard
2. Find **Account Details** section
3. Copy these three values:
   - **Cloud name** (e.g., `d1234567`)
   - **API Key** (e.g., `123456789012345`)
   - **API Secret** (e.g., `abcdef...`)

## Step 3: Set Up in PowerShell (1 minute)

Open PowerShell in your InstaForge folder and run:

```powershell
$env:CLOUDINARY_CLOUD_NAME = "paste-your-cloud-name-here"
$env:CLOUDINARY_API_KEY = "paste-your-api-key-here"
$env:CLOUDINARY_API_SECRET = "paste-your-api-secret-here"
```

**Replace the values with your actual credentials!**

## Step 4: Start Your Server

```powershell
python web_server.py
```

You should see:
```
DEBUG: Using Cloudinary for file uploads
```

If you see "Cloudinary not configured", check your environment variables.

## Done! 

Now when you upload images, they'll automatically go to Cloudinary and Instagram will be able to access them without any issues.

---

**Note:** The environment variables set this way only last until you close PowerShell.

**For permanent setup**, see `CLOUDINARY_SETUP.md` for .env file or Windows System Environment Variables setup.
