@echo off
chcp 65001 >nul
REM HTML Editor Local Startup Script (Django)
REM Uses virtual environment Python explicitly

cd /d %~dp0
echo ========================================
echo Starting HTML Editor (Django)...
echo ========================================
echo.

REM Run database migrations
echo Running database migrations...
call venv\Scripts\python.exe manage.py migrate --noinput
if errorlevel 1 (
    echo ERROR: Migration failed
    pause
    exit /b 1
)
echo.

REM Collect static files
echo Collecting static files...
call venv\Scripts\python.exe manage.py collectstatic --noinput
if errorlevel 1 (
    echo WARNING: Static file collection failed, continuing...
)
echo.

REM Start Django development server
echo Starting Django development server...
call venv\Scripts\python.exe manage.py runserver 127.0.0.1:5000

pause
