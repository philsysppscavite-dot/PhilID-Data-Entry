@echo off
setlocal enabledelayedexpansion

REM ============================================================
REM  Pushes this project to:
REM  git@github.com:philsysppscavite-dot/PhilID-Data-Entry.git
REM
REM  You'll be prompted for a GitHub Personal Access Token (PAT).
REM  It is only held in memory for this run -- it is never written
REM  to any file, and is scrubbed from the saved git remote after
REM  the push completes.
REM
REM  How to create a token (2 minutes):
REM    1. github.com -> your profile photo -> Settings
REM    2. Developer settings -> Personal access tokens -> Fine-grained tokens
REM    3. "Generate new token" -> Repository access: "Only select
REM       repositories" -> choose PhilID-Data-Entry
REM    4. Permissions -> Repository permissions -> "Contents": Read and write
REM    5. Generate, then COPY the token (you only see it once)
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
echo Paste your GitHub Personal Access Token below.
echo (Nothing will be displayed as you type/paste -- that's expected.)
echo.

REM Masked input via PowerShell (native batch can't hide typed characters)
for /f "usebackq delims=" %%T in (`powershell -NoProfile -Command "$s = Read-Host -AsSecureString 'Token'; $p = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($s)); Write-Output $p"`) do set GH_TOKEN=%%T

if "%GH_TOKEN%"=="" (
    echo [ERROR] No token entered. Aborting.
    pause
    exit /b 1
)

echo.
echo Configuring temporary authenticated remote...
git remote remove origin >nul 2>nul
git remote add origin https://%GH_TOKEN%@%REPO_URL%

echo.
echo Staging and committing all files...
git add -A
git commit -m "Update: role-based reporting, transmittal printing, 29-digit QR validation, all-caps data entry, masterlist import" 2>nul
if errorlevel 1 (
    echo (Nothing new to commit -- continuing to push in case the remote is behind.)
)

echo.
echo Pushing to GitHub...
git push -u origin main

if errorlevel 1 (
    echo.
    echo [ERROR] Push failed. Common causes:
    echo   - Token doesn't have "Contents: Read and write" on this repo
    echo   - The repo already has commits that conflict with yours
    echo     ^(try: git pull origin main --allow-unrelated-histories^)
    echo   - Token was mistyped/expired
    goto cleanup
)

echo.
echo Push succeeded.

:cleanup
echo.
echo Removing the token from the saved remote URL for safety...
git remote remove origin >nul 2>nul
git remote add origin https://%REPO_URL%
set GH_TOKEN=

echo.
echo Done. Your remote "origin" is now set to:
echo   https://%REPO_URL%
echo (no token stored). Future pushes will ask you to sign in again,
echo or you can switch to the SSH URL if you have SSH keys set up:
echo   git remote set-url origin git@github.com:philsysppscavite-dot/PhilID-Data-Entry.git
echo.
pause