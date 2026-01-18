# HTML Editor Local Startup Script (Django)
# Uses virtual environment Python explicitly

Set-Location $PSScriptRoot
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Starting HTML Editor (Django)..." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Run database migrations
Write-Host "Running database migrations..." -ForegroundColor Yellow
& ".\venv\Scripts\python.exe" manage.py migrate --noinput
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Migration failed" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host ""

# Collect static files
Write-Host "Collecting static files..." -ForegroundColor Yellow
& ".\venv\Scripts\python.exe" manage.py collectstatic --noinput
if ($LASTEXITCODE -ne 0) {
    Write-Host "WARNING: Static file collection failed, continuing..." -ForegroundColor Yellow
}
Write-Host ""

# Start Django development server
Write-Host "Starting Django development server..." -ForegroundColor Green
Write-Host "Access at: http://127.0.0.1:5000" -ForegroundColor Green
Write-Host ""
& ".\venv\Scripts\python.exe" manage.py runserver 127.0.0.1:5000
