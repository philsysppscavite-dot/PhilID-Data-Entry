@echo off
cd /d "%~dp0"
if not exist "venv\" (
    echo Virtual environment not found. Run run.bat first to set up the app.
    pause
    exit /b 1
)
call venv\Scripts\activate.bat
python reset_admin.py
pause
