@echo off
setlocal
cd /d "%~dp0"

if not exist "venv\" (
    echo Virtual environment not found. Run run.bat first at least once.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

if not exist "instance\checkin.db" (
    echo Database not set up yet. Run run.bat or setup_db.py first.
    pause
    exit /b 1
)

set PORT=8080
if not "%1"=="" set PORT=%1

echo ============================================
echo   CheckPoint - Production Server (Waitress)
echo   Listening on http://0.0.0.0:%PORT%
echo   Remember: the browser QR scanner needs HTTPS
echo   for camera access on any device other than
echo   this machine itself (localhost is exempt).
echo   Press CTRL+C to stop.
echo ============================================
echo.

waitress-serve --host=0.0.0.0 --port=%PORT% wsgi:app

pause
