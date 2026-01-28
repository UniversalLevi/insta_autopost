# Test AI DM endpoints
Write-Host "Testing AI DM Status..." -ForegroundColor Yellow
try {
    $status = Invoke-RestMethod -Uri "https://veilforce.com/api/test/ai-dm-status" -Method GET
    $status | ConvertTo-Json -Depth 10
} catch {
    Write-Host "Error: $_" -ForegroundColor Red
    Write-Host "Status Code: $($_.Exception.Response.StatusCode.value__)" -ForegroundColor Red
}

Write-Host "`nTesting AI Reply..." -ForegroundColor Yellow
try {
    $body = @{
        message = "Hello! How much does your service cost?"
        account_id = "1405915827600672"
    }
    $reply = Invoke-RestMethod -Uri "https://veilforce.com/api/test/ai-reply" -Method POST -Body $body -ContentType "application/x-www-form-urlencoded"
    $reply | ConvertTo-Json -Depth 10
} catch {
    Write-Host "Error: $_" -ForegroundColor Red
    if ($_.Exception.Response) {
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        $responseBody = $reader.ReadToEnd()
        Write-Host "Response: $responseBody" -ForegroundColor Red
    }
}
