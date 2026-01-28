# Test if webhook is receiving messages
Write-Host "Checking if webhook is receiving messages..." -ForegroundColor Yellow
Write-Host ""

$logFile = "logs/instaforge.log"
if (Test-Path $logFile) {
    Write-Host "Checking last 50 log entries for webhook activity:" -ForegroundColor Cyan
    Write-Host "==========================================" -ForegroundColor Cyan
    
    $allLogs = Get-Content $logFile -Tail 50
    $webhookReceived = $allLogs | Select-String "Instagram webhook POST received"
    $webhookPayload = $allLogs | Select-String "Instagram webhook payload received"
    $messagesEvent = $allLogs | Select-String "Instagram webhook messages event"
    $aiDmWebhook = $allLogs | Select-String "AI_DM_WEBHOOK"
    
    if ($webhookReceived) {
        Write-Host "[OK] Webhook endpoint is being called" -ForegroundColor Green
        $webhookReceived | Select-Object -Last 3 | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
    } else {
        Write-Host "[WARNING] No webhook POST requests found - webhook may not be receiving messages" -ForegroundColor Yellow
        Write-Host "  Check:" -ForegroundColor Yellow
        Write-Host "    1. Meta App Dashboard -> Webhooks -> Instagram" -ForegroundColor White
        Write-Host "    2. Verify 'messages' field is subscribed" -ForegroundColor White
        Write-Host "    3. Verify webhook URL: https://veilforce.com/webhooks/instagram" -ForegroundColor White
    }
    Write-Host ""
    
    if ($webhookPayload) {
        Write-Host "[OK] Webhook payloads are being received" -ForegroundColor Green
        $webhookPayload | Select-Object -Last 3 | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
    } else {
        Write-Host "[INFO] No webhook payloads logged" -ForegroundColor Gray
    }
    Write-Host ""
    
    if ($messagesEvent) {
        Write-Host "[OK] Messages events are being received" -ForegroundColor Green
        $messagesEvent | Select-Object -Last 3 | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
    } else {
        Write-Host "[WARNING] No messages events found" -ForegroundColor Yellow
        Write-Host "  This means webhook is not receiving message notifications" -ForegroundColor Yellow
    }
    Write-Host ""
    
    if ($aiDmWebhook) {
        Write-Host "[OK] AI DM processing is happening" -ForegroundColor Green
        $aiDmWebhook | Select-Object -Last 5 | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
    } else {
        Write-Host "[WARNING] No AI_DM_WEBHOOK entries found" -ForegroundColor Yellow
        Write-Host "  This means messages are not being processed for AI DM" -ForegroundColor Yellow
    }
    Write-Host ""
    
    Write-Host "Full recent webhook-related logs:" -ForegroundColor Cyan
    Write-Host "==========================================" -ForegroundColor Cyan
    $allLogs | Select-String "webhook|AI_DM" | Select-Object -Last 10 | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
    
} else {
    Write-Host "[ERROR] Log file not found: $logFile" -ForegroundColor Red
    Write-Host "  The application may not be running or logs are in a different location" -ForegroundColor Yellow
}
