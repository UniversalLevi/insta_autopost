# InstaForge Docker Deployment Script
# This script helps deploy InstaForge using Docker

Write-Host "=== InstaForge Docker Deployment ===" -ForegroundColor Cyan
Write-Host ""

# Check if Docker is installed
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: Docker is not installed or not in PATH" -ForegroundColor Red
    Write-Host "Please install Docker Desktop: https://www.docker.com/products/docker-desktop" -ForegroundColor Yellow
    exit 1
}

# Check if .env file exists
if (-not (Test-Path ".env")) {
    Write-Host "WARNING: .env file not found!" -ForegroundColor Yellow
    Write-Host "Creating .env from template..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env" -ErrorAction SilentlyContinue
    if (-not (Test-Path ".env")) {
        Write-Host "ERROR: Could not create .env file. Please create it manually." -ForegroundColor Red
        exit 1
    }
    Write-Host "Please edit .env file with your credentials before continuing." -ForegroundColor Yellow
    exit 1
}

# Check if docker-compose is available
if (Get-Command docker-compose -ErrorAction SilentlyContinue) {
    Write-Host "Using docker-compose..." -ForegroundColor Green
    Write-Host ""
    Write-Host "Building and starting containers..." -ForegroundColor Cyan
    docker-compose up -d --build
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "✓ Deployment successful!" -ForegroundColor Green
        Write-Host ""
        Write-Host "Application is running at: http://localhost:8000" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "To view logs:" -ForegroundColor Yellow
        Write-Host "  docker-compose logs -f" -ForegroundColor White
        Write-Host ""
        Write-Host "To stop:" -ForegroundColor Yellow
        Write-Host "  docker-compose down" -ForegroundColor White
    } else {
        Write-Host ""
        Write-Host "✗ Deployment failed. Check errors above." -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "docker-compose not found, using docker build/run..." -ForegroundColor Yellow
    Write-Host ""
    
    Write-Host "Building Docker image..." -ForegroundColor Cyan
    docker build -t instaforge .
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "✗ Build failed!" -ForegroundColor Red
        exit 1
    }
    
    Write-Host ""
    Write-Host "Starting container..." -ForegroundColor Cyan
    docker run -d `
        --name instaforge `
        -p 8000:8000 `
        --env-file .env `
        -v "${PWD}/data:/app/data" `
        -v "${PWD}/logs:/app/logs" `
        -v "${PWD}/config:/app/config" `
        --restart unless-stopped `
        instaforge
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "✓ Deployment successful!" -ForegroundColor Green
        Write-Host ""
        Write-Host "Application is running at: http://localhost:8000" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "To view logs:" -ForegroundColor Yellow
        Write-Host "  docker logs -f instaforge" -ForegroundColor White
        Write-Host ""
        Write-Host "To stop:" -ForegroundColor Yellow
        Write-Host "  docker stop instaforge && docker rm instaforge" -ForegroundColor White
    } else {
        Write-Host ""
        Write-Host "✗ Deployment failed. Check errors above." -ForegroundColor Red
        exit 1
    }
}
