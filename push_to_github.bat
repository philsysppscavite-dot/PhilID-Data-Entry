@echo off
setlocal enabledelayedexpansion

REM ============================================================
REM  Pushes this project to:
REM  https://github.com/philsysppscavite-dot/PhilID-Data-Entry.git
REM
REM  Authentication is handled by Git Credential Manager (installed
REM  with Git for Windows). The first time you push, a browser
REM  window will open asking you to sign in to GitHub. After that,
REM  your credentials are cached securely by Windows, so future
REM  pushes won't ask again.
REM ============================================================

set REPO_URL=github.com/philsysppscavite-dot/PhilID-Data-Entry.git

where git >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Git is not installed or not on PATH.
    echo Download it from https://git-scm.com/download/win and try again.
    pause
    exit /b 1
)

if not exist ".git" (
    echo Initializing a new git repository here...
    git init
)

REM Always make sure the local branch is named "main", even if the
REM repo already existed with a different default branch (e.g. "master").
git branch -M main

echo.
echo Configuring remote...
git remote remove origin >nul 2>nul
git remote add origin https://%REPO_URL%

echo.
echo Staging and committing all files...
git add -A
git commit -m "Update: role-based reporting, transmittal printing, 29-digit QR validation, all-caps data entry, masterlist import" 2>nul
if errorlevel 1 (
    echo (Nothing new to commit -- continuing to push in case the remote is behind.)
)

echo.
echo Pushing to GitHub...
echo If a browser window opens, sign in to GitHub there to authenticate.
git push -u origin main

if errorlevel 1 (
    echo.
    echo [ERROR] Push failed. Common causes:
    echo   - You didn't complete the browser sign-in, or signed into the wrong account
    echo   - Your GitHub account doesn't have write access to this repo
    echo   - The repo already has commits that conflict with yours
    echo     ^(try: git pull origin main --allow-unrelated-histories^)
    echo.
    pause
    exit /b 1
)

echo.
echo Push succeeded.

echo.
echo ============================================================
echo  Verifying what is actually tracked in this repo:
echo ============================================================
for /f %%C in ('git ls-files ^| find /c /v ""') do set TRACKED_COUNT=%%C
echo Total files tracked by git: %TRACKED_COUNT%
echo.
echo Full list (also matches what is now on GitHub):
git ls-files
echo.
echo If you expected a file that is NOT in the list above, it is
echo most likely being excluded by .gitignore. Open .gitignore in
echo this folder to see what is intentionally excluded (things like
echo .env, __pycache__, venv, or uploaded files are usually excluded
echo on purpose to avoid leaking secrets or bloating the repo).
echo.
echo.
pause
