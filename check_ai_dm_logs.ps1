# Check AI DM Logs for Recent Activity
Write-Host "Checking AI DM Logs..." -ForegroundColor Yellow
Write-Host ""

$logFile = "logs/instaforge.log"
if (Test-Path $logFile) {
    Write-Host "Recent AI DM related logs (last 100 lines):" -ForegroundColor Cyan
    Write-Host "==========================================" -ForegroundColor Cyan
    Get-Content $logFile -Tail 100 | Select-String "AI_DM" | Select-Object -Last 20
    Write-Host ""
    Write-Host "Recent Instagram webhook logs:" -ForegroundColor Cyan
    Write-Host "==========================================" -ForegroundColor Cyan
    Get-Content $logFile -Tail 100 | Select-String "Instagram webhook" | Select-Object -Last 10
    Write-Host ""
    Write-Host "Recent messages webhook logs:" -ForegroundColor Cyan
    Write-Host "==========================================" -ForegroundColor Cyan
    Get-Content $logFile -Tail 100 | Select-String "messages event" | Select-Object -Last 10
} else {
    Write-Host "[ERROR] Log file not found: $logFile" -ForegroundColor Red
    Write-Host "Looking for log files..." -ForegroundColor Yellow
    Get-ChildItem -Path "logs" -Filter "*.log" -ErrorAction SilentlyContinue | Select-Object Name, LastWriteTime
}
