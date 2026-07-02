@echo off
setlocal enabledelayedexpansion
title CheckPoint - QR ID Check-In System
cd /d "%~dp0"

echo ============================================
echo   CheckPoint - QR ID Check-In System
echo ============================================
echo.

REM ---- 1. Check Python is installed ----
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python was not found on this computer.
    echo Please install Python 3.10+ from https://www.python.org/downloads/
    echo and make sure to check "Add Python to PATH" during install.
    echo.
    pause
    exit /b 1
)

REM ---- 2. Create virtual environment if it doesn't exist ----
if not exist "venv\" (
    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

REM ---- 3. Activate virtual environment ----
call venv\Scripts\activate.bat

REM ---- 4. Install/update dependencies ----
echo Checking dependencies...
pip install -r requirements.txt --quiet --disable-pip-version-check
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies. Check your internet connection.
    pause
    exit /b 1
)

REM ---- 5. First-time database setup ----
if not exist "instance\checkin.db" (
    echo.
    echo ============================================
    echo   First-time setup: creating database and
    echo   importing barangay/city/province data.
    echo   You will be asked to create an admin account.
    echo ============================================
    echo.
    python setup_db.py
    if errorlevel 1 (
        echo [ERROR] Database setup failed.
        pause
        exit /b 1
    )
)

REM ---- 6. Run the app ----
echo.
echo ============================================
echo   Starting CheckPoint...
echo   Open your browser to: http://localhost:5000
echo   Press CTRL+C in this window to stop the server.
echo.
echo   Forgot your password?  Run reset_admin.bat
echo   Ready to go live?      See serve_production.bat
echo                          and the README's "Going live" section.
echo ============================================
echo.

start "" http://localhost:5000
python app.py

pause
