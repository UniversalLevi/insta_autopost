# Simple Cloudinary Setup - Two Methods

You provided these credentials:
- Cloud Name: `KANISHK KUMAWAT` (has spaces - might need to check actual cloud name)
- API Key: `858581386324189`
- API Secret: `UlNzKD2V03qU5RykVOybOAiiOM`

## ⚠️ IMPORTANT: Check Your Cloud Name First!

Your cloud name "KANISHK KUMAWAT" has spaces. Cloudinary cloud names usually:
- Are lowercase (e.g., `kanishk-kumawat`)
- Don't have spaces
- Look like `d1234567` or `my-cloud-name`

**Check your Cloudinary dashboard** → Account Details → Cloud name (it's shown there)

---

## Method 1: PowerShell Script (Easiest)

1. I've created a file called `setup_cloudinary.ps1` for you

2. **First, edit the cloud name** if needed:
   - Open `setup_cloudinary.ps1` in a text editor
   - Change `"KANISHK-KUMAWAT"` to your actual cloud name (if different)
   - Save the file

3. **Run the script in PowerShell:**
   ```powershell
   cd D:\InstaForge
   .\setup_cloudinary.ps1
   ```

4. **Then start your server:**
   ```powershell
   python web_server.py
   ```

**Note:** Variables only work in that PowerShell window. If you close it, you need to run the script again.

---

## Method 2: .env File (Recommended - Permanent)

This is better because it works every time!

1. **Create a file named `.env`** in your `D:\InstaForge` folder

2. **Add these lines** (replace the cloud name if yours is different):
   ```
   CLOUDINARY_CLOUD_NAME=KANISHK-KUMAWAT
   CLOUDINARY_API_KEY=858581386324189
   CLOUDINARY_API_SECRET=UlNzKD2V03qU5RykVOybOAiiOM
   ```

3. **Save the file**

4. **Start your server** - it will automatically load the .env file:
   ```powershell
   python web_server.py
   ```

**This works every time, even after closing PowerShell!**

---

## Fixing PowerShell Errors

If PowerShell gives you errors, try these:

### Error: "execution of scripts is disabled"
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Error: "path not found"
Make sure you're in the right folder:
```powershell
cd D:\InstaForge
```

### Error: Quotes in the values
If your values have quotes or special characters, PowerShell might have issues. Use the .env file method instead!

---

## Verify It's Working

When you start your server, look for:
```
DEBUG: Using Cloudinary for file uploads
```

If you see "Cloudinary not configured", check:
1. Are the environment variables set? (`echo $env:CLOUDINARY_CLOUD_NAME`)
2. Did you use the correct cloud name (no spaces)?
3. Did you restart the server after setting variables?

---

## Still Having Issues?

1. **Double-check your Cloudinary dashboard:**
   - Go to https://cloudinary.com/console
   - Click on your account
   - Look at "Account Details"
   - Copy the EXACT cloud name shown there

2. **Use the .env file method** - it's the most reliable

3. **Make sure cloudinary is installed:**
   ```powershell
   pip install cloudinary
   ```
