@echo off
REM Runs archive_logs.py with Administrator privileges
REM Useful if you need elevated permissions for the archive directory

echo ========================================
echo RUNNING LOG ARCHIVER AS ADMINISTRATOR
echo ========================================
echo.

REM Check if running as admin
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting Administrator privileges...
    powershell -Command "Start-Process cmd -ArgumentList '/c cd /d \"%CD%\" && python archive_logs.py %*' -Verb RunAs"
) else (
    echo Running with Administrator privileges...
    python archive_logs.py %*
)
