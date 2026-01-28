# Comprehensive Webhook Setup Checker
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Webhook Setup Verification" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 1. Check Verify Token
Write-Host "1. Checking Verify Token Configuration..." -ForegroundColor Yellow
$envFile = ".env"
if (Test-Path $envFile) {
    $envContent = Get-Content $envFile
    $hasToken = $envContent | Select-String "WEBHOOK_VERIFY_TOKEN"
    if ($hasToken) {
        Write-Host "  [OK] WEBHOOK_VERIFY_TOKEN found in .env" -ForegroundColor Green
        $tokenLine = $hasToken.Line
        # Don't show the full token, just confirm it exists
        if ($tokenLine -match "WEBHOOK_VERIFY_TOKEN=(.+)") {
            $tokenValue = $matches[1]
            $tokenLength = $tokenValue.Length
            Write-Host "    Token length: $tokenLength characters" -ForegroundColor Gray
        }
    } else {
        Write-Host "  [WARNING] WEBHOOK_VERIFY_TOKEN not found in .env" -ForegroundColor Yellow
        Write-Host "    Using default: 'my_test_token_for_instagram_verification'" -ForegroundColor Gray
        Write-Host "    Action: Set WEBHOOK_VERIFY_TOKEN in .env to match Meta Dashboard" -ForegroundColor White
    }
} else {
    Write-Host "  [ERROR] .env file not found" -ForegroundColor Red
}
Write-Host ""

# 2. Get Current Verify Token from API
Write-Host "2. Getting Verify Token from Server..." -ForegroundColor Yellow
try {
    $webhookInfo = Invoke-RestMethod -Uri "http://localhost:8000/api/webhooks/callback-url" -Method GET
    Write-Host "  [OK] Server verify token: $($webhookInfo.verify_token)" -ForegroundColor Green
    Write-Host "  Callback URL: $($webhookInfo.callback_url)" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  IMPORTANT: In Meta Dashboard:" -ForegroundColor Yellow
    Write-Host "    - Callback URL must be: $($webhookInfo.callback_url)" -ForegroundColor White
    Write-Host "    - Verify Token must be: $($webhookInfo.verify_token)" -ForegroundColor White
    Write-Host "    - These MUST match exactly!" -ForegroundColor Red
} catch {
    Write-Host "  [ERROR] Could not get webhook info: $_" -ForegroundColor Red
}
Write-Host ""

# 3. Test Webhook Verification Endpoint
Write-Host "3. Testing Webhook Verification Endpoint..." -ForegroundColor Yellow
try {
    $testToken = "my_test_token_for_instagram_verification"
    $testUrl = "http://localhost:8000/webhooks/instagram?hub.mode=subscribe&hub.verify_token=$testToken&hub.challenge=test123"
    $response = Invoke-WebRequest -Uri $testUrl -Method GET -ErrorAction SilentlyContinue
    if ($response.StatusCode -eq 200 -and $response.Content -eq "test123") {
        Write-Host "  [OK] Webhook verification endpoint works" -ForegroundColor Green
        Write-Host "    Challenge echoed correctly" -ForegroundColor Gray
    } else {
        Write-Host "  [WARNING] Verification endpoint returned unexpected response" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  [ERROR] Verification endpoint test failed: $_" -ForegroundColor Red
}
Write-Host ""

# 4. Check Webhook URL Accessibility
Write-Host "4. Checking Production Webhook URL..." -ForegroundColor Yellow
$prodUrl = "https://veilforce.com/webhooks/instagram"
try {
    $response = Invoke-WebRequest -Uri "$prodUrl?hub.mode=subscribe&hub.verify_token=test&hub.challenge=test" -Method GET -ErrorAction SilentlyContinue
    Write-Host "  [OK] Production webhook URL is accessible" -ForegroundColor Green
    Write-Host "    Status: $($response.StatusCode)" -ForegroundColor Gray
} catch {
    $statusCode = $_.Exception.Response.StatusCode.value__
    if ($statusCode -eq 403) {
        Write-Host "  [OK] URL is accessible (403 is expected for wrong token)" -ForegroundColor Green
    } else {
        Write-Host "  [WARNING] URL may not be accessible: Status $statusCode" -ForegroundColor Yellow
        Write-Host "    Error: $_" -ForegroundColor Gray
    }
}
Write-Host ""

# 5. Summary
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Summary" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "To fix webhook issues:" -ForegroundColor Yellow
Write-Host "1. Check Meta Dashboard -> Webhooks -> Instagram" -ForegroundColor White
Write-Host "2. Verify Callback URL matches: https://veilforce.com/webhooks/instagram" -ForegroundColor White
Write-Host "3. Verify Token matches the token shown above" -ForegroundColor White
Write-Host "4. If token doesn't match, either:" -ForegroundColor White
Write-Host "   a) Add WEBHOOK_VERIFY_TOKEN=your_token to .env file" -ForegroundColor Gray
Write-Host "   b) Or update Meta Dashboard to use: my_test_token_for_instagram_verification" -ForegroundColor Gray
Write-Host "5. Click 'Test' button in Meta Dashboard to send a test webhook" -ForegroundColor White
Write-Host "6. Check logs: .\test_webhook_receiving.ps1" -ForegroundColor White
Write-Host ""
