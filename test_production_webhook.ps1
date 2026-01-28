# Test Production Webhook Endpoint
Write-Host "Testing Production Webhook Endpoint..." -ForegroundColor Yellow
Write-Host ""

$prodUrl = "https://veilforce.com/webhooks/instagram"

# Test 1: GET request (verification)
Write-Host "1. Testing GET (Webhook Verification)..." -ForegroundColor Cyan
try {
    $testToken = "my_test_token_for_instagram_verification"
    $getUrl = "$prodUrl" + "?hub.mode=subscribe&hub.verify_token=$testToken&hub.challenge=test123"
    $response = Invoke-WebRequest -Uri $getUrl -Method GET -ErrorAction Stop
    Write-Host "  [OK] GET request successful" -ForegroundColor Green
    Write-Host "    Status: $($response.StatusCode)" -ForegroundColor Gray
    Write-Host "    Response: $($response.Content)" -ForegroundColor Gray
    if ($response.Content -eq "test123") {
        Write-Host "    [OK] Challenge echoed correctly - verification works!" -ForegroundColor Green
    }
} catch {
    $statusCode = $_.Exception.Response.StatusCode.value__
    Write-Host "  [ERROR] GET request failed: Status $statusCode" -ForegroundColor Red
    Write-Host "    Error: $_" -ForegroundColor Gray
    if ($statusCode -eq 403) {
        Write-Host "    [INFO] 403 means token doesn't match - check verify token" -ForegroundColor Yellow
    }
}
Write-Host ""

# Test 2: POST request (webhook event)
Write-Host "2. Testing POST (Webhook Event)..." -ForegroundColor Cyan
$testPayload = @{
    object = "instagram"
    entry = @(
        @{
            id = "1405915827600672"
            changes = @(
                @{
                    field = "messages"
                    value = @{
                        sender = @{
                            id = "12334"
                        }
                        recipient = @{
                            id = "1405915827600672"
                        }
                        timestamp = "1527459824"
                        message = @{
                            mid = "test_message_id"
                            text = "Hello test message"
                        }
                    }
                }
            )
        }
    )
} | ConvertTo-Json -Depth 10

try {
    $response = Invoke-RestMethod -Uri $prodUrl -Method POST -Body $testPayload -ContentType "application/json" -ErrorAction Stop
    Write-Host "  [OK] POST request successful" -ForegroundColor Green
    Write-Host "    Response: $($response | ConvertTo-Json)" -ForegroundColor Gray
} catch {
    $statusCode = $_.Exception.Response.StatusCode.value__
    Write-Host "  [ERROR] POST request failed: Status $statusCode" -ForegroundColor Red
    Write-Host "    Error: $_" -ForegroundColor Gray
    
    # Try to get error details
    if ($_.Exception.Response) {
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        $errorBody = $reader.ReadToEnd()
        Write-Host "    Error Body: $errorBody" -ForegroundColor Gray
    }
}
Write-Host ""

# Test 3: Check if server is running
Write-Host "3. Testing Server Accessibility..." -ForegroundColor Cyan
try {
    $statusUrl = "https://veilforce.com/api/status"
    $status = Invoke-RestMethod -Uri $statusUrl -Method GET -ErrorAction Stop
    Write-Host "  [OK] Server is running and accessible" -ForegroundColor Green
    Write-Host "    App Status: $($status.app_status)" -ForegroundColor Gray
} catch {
    Write-Host "  [WARNING] Could not reach server status endpoint" -ForegroundColor Yellow
    Write-Host "    This might mean server is not running or not accessible" -ForegroundColor Yellow
}
Write-Host ""

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Summary" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "If GET works but POST doesn't:" -ForegroundColor Yellow
Write-Host "  - Server is accessible but webhook processing may have issues" -ForegroundColor White
Write-Host "  - Check server logs on production server" -ForegroundColor White
Write-Host ""
Write-Host "If both fail:" -ForegroundColor Yellow
Write-Host "  - Server may not be running at https://veilforce.com" -ForegroundColor White
Write-Host "  - Check if production server is deployed and running" -ForegroundColor White
Write-Host "  - Verify DNS points to correct server" -ForegroundColor White
Write-Host ""
