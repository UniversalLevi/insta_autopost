# Complete AI DM Testing Script
# Tests all aspects of the AI DM auto-reply feature

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "AI DM Auto-Reply Testing Suite" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Configuration
$baseUrl = "http://localhost:8000"  # Change to "https://veilforce.com" for production
$accountId = "1405915827600672"

# Test 1: Check AI DM Status
Write-Host "Test 1: Checking AI DM Configuration..." -ForegroundColor Yellow
try {
    $status = Invoke-RestMethod -Uri "$baseUrl/api/test/ai-dm-status" -Method GET
    Write-Host "[OK] Status check successful" -ForegroundColor Green
    Write-Host "  - OpenAI Configured: $($status.openai_configured)" -ForegroundColor $(if ($status.openai_configured) { "Green" } else { "Red" })
    Write-Host "  - Accounts Found: $($status.accounts.Count)" -ForegroundColor Green
    
    foreach ($account in $status.accounts) {
        Write-Host "  Account: $($account.username)" -ForegroundColor Cyan
        Write-Host "    - AI DM Enabled: $($account.ai_dm_enabled)" -ForegroundColor $(if ($account.ai_dm_enabled) { "Green" } else { "Yellow" })
        Write-Host "    - Instagram Business ID: $($account.instagram_business_id)" -ForegroundColor $(if ($account.instagram_business_id) { "Green" } else { "Yellow" })
    }
    Write-Host ""
} catch {
    Write-Host "[FAIL] Status check failed: $_" -ForegroundColor Red
    Write-Host ""
}

# Test 2: Test AI Reply Generation
Write-Host "Test 2: Testing AI Reply Generation..." -ForegroundColor Yellow
$testMessages = @(
    "Hello! How much does your service cost?",
    "What is InstaForge?",
    "Where are you located?",
    "Hi there!"
)

foreach ($testMessage in $testMessages) {
    try {
        Write-Host "  Testing message: `"$testMessage`"" -ForegroundColor Gray
        $body = @{
            message = $testMessage
            account_id = $accountId
        }
        $reply = Invoke-RestMethod -Uri "$baseUrl/api/test/ai-reply" -Method POST -Body $body -ContentType "application/x-www-form-urlencoded"
        
        if ($reply.status -eq "success") {
            Write-Host "  [OK] Reply generated successfully" -ForegroundColor Green
            Write-Host "    Original: $testMessage" -ForegroundColor Gray
            Write-Host "    Reply: $($reply.reply)" -ForegroundColor Green
        } else {
            Write-Host "  [FAIL] Failed: $($reply.error)" -ForegroundColor Red
        }
        Write-Host ""
        Start-Sleep -Seconds 1  # Small delay between requests
    } catch {
        Write-Host "  [ERROR] Error: $_" -ForegroundColor Red
        Write-Host ""
    }
}

# Test 3: Check Rate Limiting
Write-Host "Test 3: Testing Rate Limiting..." -ForegroundColor Yellow
Write-Host "  Sending 12 messages to test rate limit (max 10 per day)..." -ForegroundColor Gray
$rateLimitTest = @()
for ($i = 1; $i -le 12; $i++) {
    try {
        $body = @{
            message = "Test message $i"
            account_id = $accountId
            user_id = "rate_test_user_$(Get-Date -Format 'yyyyMMdd')"
        }
        $reply = Invoke-RestMethod -Uri "$baseUrl/api/test/ai-reply" -Method POST -Body $body -ContentType "application/x-www-form-urlencoded"
        $rateLimitTest += [PSCustomObject]@{
            Message = $i
            Status = $reply.status
            Reply = $reply.reply
        }
        Write-Host "    Message $i : $($reply.status)" -ForegroundColor $(if ($reply.status -eq "success") { "Green" } else { "Yellow" })
    } catch {
        Write-Host "    Message $i : Error" -ForegroundColor Red
    }
}

$successCount = ($rateLimitTest | Where-Object { $_.Status -eq "success" }).Count
Write-Host "  Results: $successCount successful replies (should be max 10)" -ForegroundColor $(if ($successCount -le 10) { "Green" } else { "Red" })
Write-Host ""

# Test 4: Check Tracking File
Write-Host "Test 4: Checking Rate Limit Tracking..." -ForegroundColor Yellow
$trackingFile = "data/ai_dm_tracking.json"
if (Test-Path $trackingFile) {
    Write-Host "  [OK] Tracking file exists: $trackingFile" -ForegroundColor Green
    $trackingData = Get-Content $trackingFile | ConvertFrom-Json
    Write-Host "  Accounts tracked: $($trackingData.PSObject.Properties.Count)" -ForegroundColor Cyan
} else {
    Write-Host "  [WARN] Tracking file not found (will be created on first reply)" -ForegroundColor Yellow
}
Write-Host ""

# Test 5: Webhook Endpoint Check
Write-Host "Test 5: Checking Webhook Configuration..." -ForegroundColor Yellow
try {
    $webhookUrl = Invoke-RestMethod -Uri "$baseUrl/api/webhooks/callback-url" -Method GET
    Write-Host "  [OK] Webhook URL: $($webhookUrl.callback_url)" -ForegroundColor Green
    Write-Host "  Verify Token: $($webhookUrl.verify_token)" -ForegroundColor Cyan
} catch {
    Write-Host "  [WARN] Could not get webhook URL: $_" -ForegroundColor Yellow
}
Write-Host ""

# Summary
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Testing Complete!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "1. Send a test DM to your Instagram account (@mr_tony.87)" -ForegroundColor White
Write-Host "2. Check server logs for 'AI_DM_WEBHOOK' entries" -ForegroundColor White
Write-Host "3. Verify you receive an AI-generated reply within 3-6 seconds" -ForegroundColor White
Write-Host ""
Write-Host "To check logs:" -ForegroundColor Yellow
Write-Host "  Get-Content logs/app.log -Tail 50 | Select-String 'AI_DM'" -ForegroundColor Gray
Write-Host ""
