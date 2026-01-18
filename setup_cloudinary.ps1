# PowerShell script to set Cloudinary environment variables
# Run this script: .\setup_cloudinary.ps1

Write-Host "Setting Cloudinary environment variables..." -ForegroundColor Green
Write-Host ""

# IMPORTANT: If your cloud name has spaces, you need to remove them or use hyphens
# Cloudinary cloud names are usually lowercase and don't have spaces
# Check your Cloudinary dashboard Account Details for the actual cloud name
# It might look like: "d1234567" or "my-cloud-name" (not "MY NAME")

# Set environment variables for current PowerShell session
# NOTE: Replace "KANISHK-KUMAWAT" with your ACTUAL cloud name from Cloudinary dashboard if it's different
$env:CLOUDINARY_CLOUD_NAME = "KANISHK-KUMAWAT"
$env:CLOUDINARY_API_KEY = "858581386324189"
$env:CLOUDINARY_API_SECRET = "UlNzKD2V03qU5RykVOybOAiiOM"

Write-Host "Environment variables set:" -ForegroundColor Yellow
Write-Host "  CLOUDINARY_CLOUD_NAME = $env:CLOUDINARY_CLOUD_NAME" -ForegroundColor Cyan
Write-Host "  CLOUDINARY_API_KEY = $env:CLOUDINARY_API_KEY" -ForegroundColor Cyan
Write-Host "  CLOUDINARY_API_SECRET = ********" -ForegroundColor Cyan
Write-Host ""

# Verify the variables were set
if ($env:CLOUDINARY_CLOUD_NAME -and $env:CLOUDINARY_API_KEY -and $env:CLOUDINARY_API_SECRET) {
    Write-Host "✓ All environment variables are set!" -ForegroundColor Green
    Write-Host ""
    Write-Host "IMPORTANT NOTES:" -ForegroundColor Yellow
    Write-Host "1. These variables only work in THIS PowerShell window" -ForegroundColor White
    Write-Host "2. If your cloud name is different, edit this script or use .env file" -ForegroundColor White
    Write-Host "3. Cloud name should match exactly what's in your Cloudinary dashboard" -ForegroundColor White
    Write-Host ""
    Write-Host "Now start your server: python web_server.py" -ForegroundColor Green
} else {
    Write-Host "✗ Error: Some environment variables were not set properly" -ForegroundColor Red
    Write-Host "Please check the script and try again" -ForegroundColor Yellow
}
