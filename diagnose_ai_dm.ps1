# Comprehensive AI DM Diagnostic Tool
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "AI DM Diagnostic Tool" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 1. Check Configuration
Write-Host "1. Checking Configuration..." -ForegroundColor Yellow
try {
    $status = Invoke-RestMethod -Uri "http://localhost:8000/api/test/ai-dm-status" -Method GET
    Write-Host "  OpenAI Configured: $($status.openai_configured)" -ForegroundColor $(if ($status.openai_configured) { "Green" } else { "Red" })
    foreach ($account in $status.accounts) {
        Write-Host "  Account: $($account.username)" -ForegroundColor Cyan
        Write-Host "    AI DM Enabled: $($account.ai_dm_enabled)" -ForegroundColor $(if ($account.ai_dm_enabled) { "Green" } else { "Red" })
        Write-Host "    Instagram Business ID: $($account.instagram_business_id)" -ForegroundColor $(if ($account.instagram_business_id) { "Green" } else { "Yellow" })
    }
} catch {
    Write-Host "  [ERROR] Could not check status: $_" -ForegroundColor Red
}
Write-Host ""

# 2. Check Logs
Write-Host "2. Checking Recent Logs..." -ForegroundColor Yellow
$logFile = "logs/instaforge.log"
if (Test-Path $logFile) {
    Write-Host "  Last 5 AI_DM_WEBHOOK entries:" -ForegroundColor Cyan
    $aiDmLogs = Get-Content $logFile -Tail 200 | Select-String "AI_DM_WEBHOOK" | Select-Object -Last 5
    if ($aiDmLogs) {
        $aiDmLogs | ForEach-Object { Write-Host "    $_" -ForegroundColor Gray }
    } else {
        Write-Host "    [WARNING] No AI_DM_WEBHOOK entries found in recent logs" -ForegroundColor Yellow
    }
    Write-Host ""
    Write-Host "  Last 5 Instagram webhook messages events:" -ForegroundColor Cyan
    $webhookLogs = Get-Content $logFile -Tail 200 | Select-String "Instagram webhook messages event" | Select-Object -Last 5
    if ($webhookLogs) {
        $webhookLogs | ForEach-Object { Write-Host "    $_" -ForegroundColor Gray }
    } else {
        Write-Host "    [WARNING] No webhook messages events found - webhook may not be receiving messages" -ForegroundColor Yellow
    }
} else {
    Write-Host "  [ERROR] Log file not found: $logFile" -ForegroundColor Red
}
Write-Host ""

# 3. Check Tracking File
Write-Host "3. Checking Rate Limit Tracking..." -ForegroundColor Yellow
$trackingFile = "data/ai_dm_tracking.json"
if (Test-Path $trackingFile) {
    Write-Host "  Tracking file exists" -ForegroundColor Green
    try {
        $tracking = Get-Content $trackingFile | ConvertFrom-Json
        Write-Host "  Accounts in tracking: $($tracking.PSObject.Properties.Count)" -ForegroundColor Cyan
    } catch {
        Write-Host "  [ERROR] Could not parse tracking file: $_" -ForegroundColor Red
    }
} else {
    Write-Host "  [INFO] Tracking file not found (normal if no replies sent yet)" -ForegroundColor Gray
}
Write-Host ""

# 4. Test AI Reply Generation
Write-Host "4. Testing AI Reply Generation..." -ForegroundColor Yellow
try {
    $body = @{
        message = "Hello"
        account_id = "1405915827600672"
    }
    $reply = Invoke-RestMethod -Uri "http://localhost:8000/api/test/ai-reply" -Method POST -Body $body -ContentType "application/x-www-form-urlencoded"
    if ($reply.status -eq "success") {
        Write-Host "  [OK] AI reply generation works" -ForegroundColor Green
        Write-Host "    Reply: $($reply.reply)" -ForegroundColor Gray
    } else {
        Write-Host "  [FAIL] AI reply generation failed: $($reply.error)" -ForegroundColor Red
    }
} catch {
    Write-Host "  [ERROR] Test failed: $_" -ForegroundColor Red
}
Write-Host ""

# 5. Recommendations
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Diagnostic Complete" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "If no webhook messages events found:" -ForegroundColor Yellow
Write-Host "  1. Check Meta App Dashboard -> Webhooks -> Instagram" -ForegroundColor White
Write-Host "  2. Verify 'messages' field is subscribed" -ForegroundColor White
Write-Host "  3. Verify webhook URL is correct: https://veilforce.com/webhooks/instagram" -ForegroundColor White
Write-Host "  4. Test webhook using Meta's 'Test' button" -ForegroundColor White
Write-Host ""
Write-Host "If webhook events found but no AI_DM_WEBHOOK entries:" -ForegroundColor Yellow
Write-Host "  1. Check account matching (instagram_business_id)" -ForegroundColor White
Write-Host "  2. Check if AI DM is enabled in accounts.yaml" -ForegroundColor White
Write-Host "  3. Check logs for 'account_not_found' or 'ai_dm_disabled' messages" -ForegroundColor White
Write-Host ""
