# FinPilot AI Backend Server Restart Script
# Run this after updating .env file

Write-Host "🚀 Restarting FinPilot AI Backend Server..." -ForegroundColor Cyan
Write-Host ""

# Activate virtual environment
& .\.venv\Scripts\Activate.ps1

# Check if .env has valid OpenAI key
$envContent = Get-Content .env -Raw
if ($envContent -match "OPENAI_API_KEY=YOUR_ACTUAL_OPENAI_API_KEY_HERE") {
    Write-Host "⚠️  WARNING: You haven't updated your OpenAI API key yet!" -ForegroundColor Yellow
    Write-Host "   Please edit backend\.env and add your real OpenAI API key" -ForegroundColor Yellow
    Write-Host "   Get it from: https://platform.openai.com/api-keys" -ForegroundColor Yellow
    Write-Host ""
}

Write-Host "✓ Virtual environment activated" -ForegroundColor Green
Write-Host "✓ Starting Django development server..." -ForegroundColor Green
Write-Host ""

# Start Django server
python manage.py runserver
