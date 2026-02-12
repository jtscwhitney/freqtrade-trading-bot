@echo off
REM Stop/Remove Freqtrade Log Archiving Scheduled Task

echo ========================================
echo STOPPING FREQTRADE LOG ARCHIVING
echo ========================================
echo.

REM Check if running as admin
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] This script must be run as Administrator
    echo.
    echo Right-click and select "Run as Administrator"
    pause
    exit /b 1
)

REM Check if task exists
schtasks /query /tn "FreqtradeLogArchiver" >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Scheduled task "FreqtradeLogArchiver" not found.
    echo        It may have already been removed or never created.
    pause
    exit /b 0
)

echo Found scheduled task: FreqtradeLogArchiver
echo.
echo Choose an option:
echo   1. Disable the task (can be re-enabled later)
echo   2. Delete the task completely
echo   3. Cancel
echo.
set /p choice="Enter choice (1-3): "

if "%choice%"=="1" (
    echo.
    echo Disabling task...
    schtasks /change /tn "FreqtradeLogArchiver" /disable
    if %errorlevel% equ 0 (
        echo [OK] Task disabled successfully!
        echo       You can re-enable it later with: schtasks /change /tn "FreqtradeLogArchiver" /enable
    ) else (
        echo [ERROR] Failed to disable task
    )
) else if "%choice%"=="2" (
    echo.
    echo Deleting task...
    schtasks /delete /tn "FreqtradeLogArchiver" /f
    if %errorlevel% equ 0 (
        echo [OK] Task deleted successfully!
    ) else (
        echo [ERROR] Failed to delete task
    )
) else (
    echo.
    echo Cancelled.
    exit /b 0
)

echo.
pause
