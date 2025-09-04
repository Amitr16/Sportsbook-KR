# GoalServe Sports Betting Platform Frontend Build Script
Write-Host "🚀 Building GoalServe Sports Betting Platform Frontend..." -ForegroundColor Green

# Create build directory
Write-Host "📁 Creating build directory..." -ForegroundColor Yellow
if (Test-Path "build") {
    Remove-Item "build" -Recurse -Force
}
New-Item -ItemType Directory -Name "build" | Out-Null

# Copy static files to build directory
Write-Host "📁 Copying static files..." -ForegroundColor Yellow
Copy-Item "..\src\static\*" -Destination "build" -Recurse -Force

# Create build manifest
Write-Host "📝 Creating build manifest..." -ForegroundColor Yellow
$buildTime = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
"Frontend build completed at $buildTime" | Out-File -FilePath "build\build-info.txt" -Encoding UTF8

Write-Host "✅ Frontend build completed successfully!" -ForegroundColor Green
Write-Host "📁 Build directory: .\build" -ForegroundColor Cyan
Write-Host "🌐 Ready for Cloudflare Pages deployment!" -ForegroundColor Cyan
