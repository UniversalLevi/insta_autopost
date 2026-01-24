# PowerShell script to stop all Python processes (frees port 8000)
# Run this script: .\stop_server.ps1

Write-Host "Stopping all Python processes..." -ForegroundColor Yellow

Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

Write-Host "Done! Port 8000 is now free." -ForegroundColor Green
Write-Host ""
Write-Host "Now you can start your server: python web_server.py" -ForegroundColor Cyan
