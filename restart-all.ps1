# FinPilot AI - Complete Restart Script
# Restarts both backend and frontend servers

Write-Host ""
Write-Host "🚀 FinPilot AI - Complete Restart" -ForegroundColor Cyan
Write-Host "=================================" -ForegroundColor Cyan
Write-Host ""

# Check if Docker containers are running
Write-Host "📦 Checking Docker services..." -ForegroundColor Yellow
$dockerStatus = docker ps --filter "name=finpilot" --format "{{.Names}}: {{.Status}}"
if ($dockerStatus) {
    foreach ($line in $dockerStatus) {
        Write-Host "   ✓ $line" -ForegroundColor Green
    }
} else {
    Write-Host "   ⚠️  Docker containers not running. Starting..." -ForegroundColor Yellow
    docker-compose up -d
    Start-Sleep -Seconds 5
}
Write-Host ""

# Stop any existing Node/Vite processes (frontend)
Write-Host "🔄 Stopping existing frontend server..." -ForegroundColor Yellow
$nodeProcesses = Get-Process -Name node -ErrorAction SilentlyContinue | Where-Object {$_.MainWindowTitle -like "*vite*" -or $_.CommandLine -like "*vite*"}
if ($nodeProcesses) {
    $nodeProcesses | Stop-Process -Force
    Write-Host "   ✓ Stopped old frontend processes" -ForegroundColor Green
} else {
    Write-Host "   ℹ️  No existing frontend processes found" -ForegroundColor Gray
}
Write-Host ""

# Check .env file for API key
Write-Host "🔑 Checking API configuration..." -ForegroundColor Yellow
$envContent = Get-Content backend\.env -Raw
if ($envContent -match "OPENAI_API_KEY=YOUR_ACTUAL_OPENAI_API_KEY_HERE" -or $envContent -match "OPENAI_API_KEY=\s*$") {
    Write-Host "   ⚠️  WARNING: OpenAI API key not configured!" -ForegroundColor Red
    Write-Host "   Edit backend\.env and add your OpenAI API key" -ForegroundColor Yellow
    Write-Host "   Get it from: https://platform.openai.com/api-keys" -ForegroundColor Yellow
} else {
    Write-Host "   ✓ OpenAI API key found" -ForegroundColor Green
}
Write-Host ""

# Prepare to start servers
Write-Host "🎬 Starting servers..." -ForegroundColor Cyan
Write-Host ""

Write-Host "1️⃣  Starting Backend (Django) on port 8000..." -ForegroundColor Yellow
Write-Host "   Command: cd backend && .\.venv\Scripts\Activate.ps1 && python manage.py runserver" -ForegroundColor Gray
Write-Host ""

Write-Host "2️⃣  Starting Frontend (Vite) on port 5173..." -ForegroundColor Yellow
Write-Host "   Command: cd frontend && npm run dev" -ForegroundColor Gray
Write-Host ""

Write-Host "=================================" -ForegroundColor Cyan
Write-Host "📝 Next Steps:" -ForegroundColor Cyan
Write-Host ""
Write-Host "   1. Open TWO separate PowerShell terminals" -ForegroundColor White
Write-Host ""
Write-Host "   Terminal 1 (Backend):" -ForegroundColor Yellow
Write-Host "   cd 'c:\Users\abhis\OneDrive\Documents\ChatGPT\FinPilot AI\backend'" -ForegroundColor Gray
Write-Host "   .\restart-server.ps1" -ForegroundColor Gray
Write-Host ""
Write-Host "   Terminal 2 (Frontend):" -ForegroundColor Yellow
Write-Host "   cd 'c:\Users\abhis\OneDrive\Documents\ChatGPT\FinPilot AI\frontend'" -ForegroundColor Gray
Write-Host "   npm run dev" -ForegroundColor Gray
Write-Host ""
Write-Host "   2. Open browser: http://localhost:5173" -ForegroundColor Yellow
Write-Host "   3. Hard refresh: Ctrl+Shift+R" -ForegroundColor Yellow
Write-Host ""
Write-Host "=================================" -ForegroundColor Cyan
Write-Host ""

# Offer to start backend automatically
$startNow = Read-Host "Do you want me to start the BACKEND server now? (Y/N)"
if ($startNow -eq "Y" -or $startNow -eq "y") {
    Write-Host ""
    Write-Host "🟢 Starting Backend Server..." -ForegroundColor Green
    Write-Host "   (Press Ctrl+C to stop when needed)" -ForegroundColor Gray
    Write-Host ""
    Set-Location backend
    & .\.venv\Scripts\Activate.ps1
    python manage.py runserver
} else {
    Write-Host ""
    Write-Host "👍 Backend not started. Run it manually when ready." -ForegroundColor Cyan
    Write-Host ""
}
