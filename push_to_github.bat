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
for /f "usebackq delims=" %%T in (`powershell -NoProfile -Command "$s = Read-Host -AsSecureString 'Token'; $b = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($s); $p = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($b); [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($b); Write-Output $p.Trim()"`) do set "GH_TOKEN=%%T"

if "%GH_TOKEN%"=="" (
    echo [ERROR] No token entered. Aborting.
    pause
    exit /b 1
)

REM Base64-encode "x-access-token:<token>" for use as an HTTP Basic auth
REM header. Sending it this way (instead of embedding it in the remote URL)
REM avoids git/curl's strict URL parser entirely, so stray characters from
REM copy/paste can't cause a "malformed URL" failure.
for /f "usebackq delims=" %%B in (`powershell -NoProfile -Command "[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes('x-access-token:' + $env:GH_TOKEN))"`) do set "GH_AUTH_HEADER=%%B"

echo.
echo Configuring remote (no token stored in the URL)...
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
git -c credential.helper= -c http.extraHeader="Authorization: Basic %GH_AUTH_HEADER%" push -u origin main

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
echo Clearing token from memory...
set GH_TOKEN=
set GH_AUTH_HEADER=

echo.
echo Done. Your remote "origin" is set to:
echo   https://%REPO_URL%
echo (no token stored anywhere). Future pushes will ask for your token again,
echo or you can switch to the SSH URL if you have SSH keys set up:
echo   git remote set-url origin git@github.com:philsysppscavite-dot/PhilID-Data-Entry.git
echo.
pause
