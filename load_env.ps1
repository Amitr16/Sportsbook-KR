# PowerShell script to load environment variables from env.local
Get-Content env.local | ForEach-Object { 
    if ($_ -match '^(.*?)=(.*)$') { 
        Set-Item -Path "env:$($matches[1])" -Value $matches[2] 
        Write-Host "Loaded: $($matches[1])=$($matches[2])"
    } 
}

Write-Host "Environment variables loaded successfully!"
Write-Host "DATABASE_URL: $env:DATABASE_URL"
