# Verify Webhook Configuration
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Webhook Configuration Verification" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Get webhook info from server
Write-Host "Server Configuration:" -ForegroundColor Yellow
try {
    $webhookInfo = Invoke-RestMethod -Uri "http://localhost:8000/api/webhooks/callback-url" -Method GET
    Write-Host "  Callback URL: $($webhookInfo.callback_url)" -ForegroundColor Cyan
    Write-Host "  Verify Token: $($webhookInfo.verify_token)" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Meta Dashboard Should Have:" -ForegroundColor Yellow
    Write-Host "  Callback URL: https://veilforce.com/webhooks/instagram" -ForegroundColor $(if ($webhookInfo.callback_url -like "*veilforce.com*") { "Green" } else { "Yellow" })
    Write-Host "  Verify Token: $($webhookInfo.verify_token)" -ForegroundColor Green
    Write-Host ""
    
    if ($webhookInfo.callback_url -notlike "*veilforce.com*") {
        Write-Host "  [WARNING] Server is using Cloudflare tunnel URL" -ForegroundColor Yellow
        Write-Host "    For production, Meta Dashboard should use: https://veilforce.com/webhooks/instagram" -ForegroundColor White
        Write-Host "    The tunnel URL is for development only" -ForegroundColor Gray
    }
} catch {
    Write-Host "  [ERROR] Could not get webhook info: $_" -ForegroundColor Red
}
Write-Host ""

# Check .env file
Write-Host "Environment Configuration:" -ForegroundColor Yellow
if (Test-Path ".env") {
    $envContent = Get-Content ".env"
    $tokenLine = $envContent | Select-String "WEBHOOK_VERIFY_TOKEN"
    if ($tokenLine) {
        Write-Host "  [OK] WEBHOOK_VERIFY_TOKEN found in .env" -ForegroundColor Green
    } else {
        Write-Host "  [INFO] WEBHOOK_VERIFY_TOKEN not in .env (using default)" -ForegroundColor Gray
    }
} else {
    Write-Host "  [WARNING] .env file not found" -ForegroundColor Yellow
}
Write-Host ""

# Test webhook verification endpoint
Write-Host "Testing Webhook Verification:" -ForegroundColor Yellow
$testToken = "my_test_token_for_instagram_verification"
$testUrl = "http://localhost:8000/webhooks/instagram?hub.mode=subscribe&hub.verify_token=$testToken&hub.challenge=test123"
try {
    $response = Invoke-WebRequest -Uri $testUrl -Method GET
    if ($response.Content -eq "test123") {
        Write-Host "  [OK] Verification endpoint works correctly" -ForegroundColor Green
        Write-Host "    Challenge was echoed: $($response.Content)" -ForegroundColor Gray
    }
} catch {
    Write-Host "  [ERROR] Verification test failed: $_" -ForegroundColor Red
}
Write-Host ""

# Summary
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Action Required:" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "In Meta App Dashboard -> Webhooks -> Instagram:" -ForegroundColor Yellow
Write-Host "1. Callback URL MUST be: https://veilforce.com/webhooks/instagram" -ForegroundColor White
Write-Host "2. Verify Token MUST be: my_test_token_for_instagram_verification" -ForegroundColor White
Write-Host ""
Write-Host "If the verify token in Meta Dashboard is different:" -ForegroundColor Yellow
Write-Host "  Option A: Update Meta Dashboard to use: my_test_token_for_instagram_verification" -ForegroundColor White
Write-Host "  Option B: Add WEBHOOK_VERIFY_TOKEN=your_token to .env file" -ForegroundColor White
Write-Host ""
Write-Host "After updating, click 'Test' button in Meta Dashboard to verify" -ForegroundColor Yellow
Write-Host ""
