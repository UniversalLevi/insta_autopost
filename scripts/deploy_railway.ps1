# InstaForge Railway Deployment Script
# This script helps deploy InstaForge to Railway

Write-Host "=== InstaForge Railway Deployment ===" -ForegroundColor Cyan
Write-Host ""

# Check if Railway CLI is installed
if (-not (Get-Command railway -ErrorAction SilentlyContinue)) {
    Write-Host "Railway CLI not found. Installing..." -ForegroundColor Yellow
    Write-Host "Please install Railway CLI first:" -ForegroundColor Yellow
    Write-Host "  npm i -g @railway/cli" -ForegroundColor White
    Write-Host ""
    Write-Host "Or visit: https://docs.railway.app/develop/cli" -ForegroundColor Cyan
    exit 1
}

# Check if logged in
Write-Host "Checking Railway login status..." -ForegroundColor Cyan
railway whoami | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Not logged in. Please login:" -ForegroundColor Yellow
    Write-Host "  railway login" -ForegroundColor White
    exit 1
}

Write-Host ""
Write-Host "Current Railway project:" -ForegroundColor Cyan
railway status

Write-Host ""
$confirm = Read-Host "Deploy to Railway? (y/n)"
if ($confirm -ne "y") {
    Write-Host "Deployment cancelled." -ForegroundColor Yellow
    exit 0
}

Write-Host ""
Write-Host "Deploying to Railway..." -ForegroundColor Cyan
railway up

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✓ Deployment successful!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Getting deployment URL..." -ForegroundColor Cyan
    $url = railway domain
    Write-Host ""
    Write-Host "Your application is available at: $url" -ForegroundColor Green
    Write-Host ""
    Write-Host "IMPORTANT: Update Meta Webhook URL to:" -ForegroundColor Yellow
    Write-Host "  $url/webhooks/instagram" -ForegroundColor White
    Write-Host ""
    Write-Host "To view logs:" -ForegroundColor Yellow
    Write-Host "  railway logs" -ForegroundColor White
} else {
    Write-Host ""
    Write-Host "✗ Deployment failed. Check errors above." -ForegroundColor Red
    exit 1
}
