# Daily Revenue Calculator PowerShell Script
Write-Host "🔄 Starting daily revenue calculation..." -ForegroundColor Blue

# Change to script directory
Set-Location $PSScriptRoot

try {
    # Run the Python script
    python daily_revenue_calculator.py
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Daily revenue calculation completed successfully!" -ForegroundColor Green
    } else {
        Write-Host "❌ Daily revenue calculation failed with exit code: $LASTEXITCODE" -ForegroundColor Red
    }
} catch {
    Write-Host "💥 Error running daily revenue calculation: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host "Press any key to continue..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
