# Operator Wallets Updater PowerShell Script
Write-Host "🔄 Starting operator wallet updates..." -ForegroundColor Blue

# Change to script directory
Set-Location $PSScriptRoot

try {
    # Run the Python script
    python update_operator_wallets.py
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Operator wallet updates completed successfully!" -ForegroundColor Green
    } else {
        Write-Host "❌ Operator wallet updates failed with exit code: $LASTEXITCODE" -ForegroundColor Red
    }
} catch {
    Write-Host "💥 Error running wallet updates: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host "Press any key to continue..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
