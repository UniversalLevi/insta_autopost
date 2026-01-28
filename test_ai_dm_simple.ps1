# Simple AI DM Testing
Write-Host "Testing AI DM Status..." -ForegroundColor Yellow
$status = Invoke-RestMethod -Uri "http://localhost:8000/api/test/ai-dm-status" -Method GET
$status | ConvertTo-Json -Depth 5

Write-Host "`nTesting AI Reply..." -ForegroundColor Yellow
$body = @{
    message = "Hello! How much does your service cost?"
    account_id = "1405915827600672"
}
$reply = Invoke-RestMethod -Uri "http://localhost:8000/api/test/ai-reply" -Method POST -Body $body -ContentType "application/x-www-form-urlencoded"
$reply | ConvertTo-Json -Depth 5
