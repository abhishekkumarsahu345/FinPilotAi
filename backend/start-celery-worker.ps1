# FinPilot AI - Celery Worker Startup Script
# This script starts the Celery worker to process background tasks (email sending, reminders, etc.)

Write-Host ""
Write-Host "🔧 FinPilot AI - Starting Celery Worker" -ForegroundColor Cyan
Write-Host "=======================================" -ForegroundColor Cyan
Write-Host ""

# Check if Redis is running
Write-Host "📡 Checking Redis connection..." -ForegroundColor Yellow
$redisRunning = docker ps --filter "name=redis" --format "{{.Names}}: {{.Status}}"
if ($redisRunning) {
    Write-Host "   ✓ Redis is running: $redisRunning" -ForegroundColor Green
} else {
    Write-Host "   ❌ Redis is not running!" -ForegroundColor Red
    Write-Host "   Please start Docker services first:" -ForegroundColor Yellow
    Write-Host "   docker-compose up -d" -ForegroundColor Gray
    Write-Host ""
    exit 1
}
Write-Host ""

# Activate virtual environment and start Celery
Write-Host "🚀 Starting Celery worker..." -ForegroundColor Green
Write-Host "   This will process background tasks for:" -ForegroundColor Gray
Write-Host "   • Email notifications" -ForegroundColor Gray
Write-Host "   • Reminder dispatch" -ForegroundColor Gray
Write-Host "   • Scheduled tasks" -ForegroundColor Gray
Write-Host ""
Write-Host "   Press Ctrl+C to stop the worker" -ForegroundColor Yellow
Write-Host ""

& .\.venv\Scripts\Activate.ps1
celery -A config worker --loglevel=info --pool=solo
