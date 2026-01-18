# PowerShell script to create .env file with Cloudinary credentials
# Run this script: .\create_env_file.ps1

Write-Host "Creating .env file with your Cloudinary credentials..." -ForegroundColor Green
Write-Host ""

# IMPORTANT: Check your Cloudinary dashboard for the ACTUAL cloud name
# Cloud names usually don't have spaces - they're like "d1234567" or "my-cloud-name"
# If your cloud name is different, edit this script before running

$cloudName = "KANISHK-KUMAWAT"
$apiKey = "858581386324189"
$apiSecret = "UlNzKD2V03qU5RykVOybOAiiOM"

# Create .env file content
$envContent = @"
# Cloudinary Configuration
# Auto-generated - edit if needed

CLOUDINARY_CLOUD_NAME=$cloudName
CLOUDINARY_API_KEY=$apiKey
CLOUDINARY_API_SECRET=$apiSecret
"@

# Write to .env file
$envContent | Out-File -FilePath ".env" -Encoding UTF8 -NoNewline

Write-Host ".env file created successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "Contents:" -ForegroundColor Yellow
Write-Host "  CLOUDINARY_CLOUD_NAME = $cloudName" -ForegroundColor Cyan
Write-Host "  CLOUDINARY_API_KEY = $apiKey" -ForegroundColor Cyan
Write-Host "  CLOUDINARY_API_SECRET = ********" -ForegroundColor Cyan
Write-Host ""
Write-Host "IMPORTANT:" -ForegroundColor Red
Write-Host "1. If your cloud name is different, edit the .env file or change the script above" -ForegroundColor Yellow
Write-Host "2. Cloud name should NOT have spaces - use hyphens instead" -ForegroundColor Yellow
Write-Host "3. Check your Cloudinary dashboard for the exact cloud name" -ForegroundColor Yellow
Write-Host ""
Write-Host "Now start your server: python web_server.py" -ForegroundColor Green
Write-Host "The .env file will be loaded automatically!" -ForegroundColor Green
