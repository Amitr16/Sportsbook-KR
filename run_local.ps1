t onA 0# PowerShell script to run local development server
not 
Write-Host "🚀 Starting local development server..." -ForegroundColor Green
Write-Host ""

# Check if virtual environment exists
if (-not (Test-Path "venv\Scripts\Activate.ps1")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv venv
}

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& "venv\Scripts\Activate.ps1"

# Install requirements
Write-Host "Installing requirements..." -ForegroundColor Yellow
pip install -r requirements.txt

# Setup local database
Write-Host "Setting up local database..." -ForegroundColor Yellow
python setup_local_db.py

# Start local server
Write-Host "Starting local server..." -ForegroundColor Yellow
python run.py

Write-Host "Press any key to continue..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
