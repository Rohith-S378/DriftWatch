# Sirius Market Intelligence - Setup and Run Script
# Run this in PowerShell as Administrator

Write-Host "🚀 Sirius Market Intelligence Engine Setup" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan

# Check if Python is installed
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Python not found. Please install Python 3.9+" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Python found: $pythonVersion" -ForegroundColor Green

# Create virtual environment if it doesn't exist
if (-not Test-Path "venv") {
    Write-Host "📦 Creating virtual environment..." -ForegroundColor Yellow
    python -m venv venv
}

# Activate virtual environment
Write-Host "🔌 Activating virtual environment..." -ForegroundColor Yellow
.\venv\Scripts\Activate.ps1

# Upgrade pip
Write-Host "⬆️ Upgrading pip..." -ForegroundColor Yellow
python -m pip install --upgrade pip

# Install requirements
Write-Host "📥 Installing Python dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt

# Create .env if it doesn't exist
if (-not Test-Path ".env") {
    Write-Host "📝 Creating .env file from template..." -ForegroundColor Yellow
    Copy-Item .env.example .env
    Write-Host "⚠️ Please edit .env with your database credentials!" -ForegroundColor Red
}

# Check for database URL
$envContent = Get-Content .env -Raw
if ($envContent -match "DATABASE_URL=.*your.*password") {
    Write-Host "⚠️ WARNING: Database URL still has placeholder values!" -ForegroundColor Red
    Write-Host "Please edit .env and set your actual DATABASE_URL" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "✅ Backend setup complete!" -ForegroundColor Green
Write-Host ""

# Setup frontend
if (Test-Path "frontend") {
    Write-Host ""
    Write-Host "📦 Setting up Frontend..." -ForegroundColor Cyan
    Set-Location frontend
    
    # Check if node_modules exists
    if (-not Test-Path "node_modules") {
        Write-Host "📥 Installing npm dependencies..." -ForegroundColor Yellow
        npm install
    } else {
        Write-Host "✅ Node modules already installed" -ForegroundColor Green
    }
    
    Set-Location ..
}

Write-Host ""
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "🎉 Setup Complete!" -ForegroundColor Green
Write-Host ""
Write-Host "To start the application:" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. Start Backend:" -ForegroundColor Yellow
Write-Host "   .\venv\Scripts\Activate.ps1" -ForegroundColor White
Write-Host "   uvicorn app.main:app --reload --port 8000" -ForegroundColor White
Write-Host ""
Write-Host "2. Start Frontend (in a new terminal):" -ForegroundColor Yellow
Write-Host "   cd frontend" -ForegroundColor White
Write-Host "   npm run dev" -ForegroundColor White
Write-Host ""
Write-Host "3. Open browser: http://localhost:5173" -ForegroundColor Yellow
Write-Host ""
Write-Host "API Documentation: http://localhost:8000/docs" -ForegroundColor Green
Write-Host "=============================================" -ForegroundColor Cyan
