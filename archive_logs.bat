@echo off
REM Freqtrade Log Archiver - Windows Batch Script
REM Archives rotated log files before they're deleted

echo ========================================
echo FREQTRADE LOG ARCHIVER
echo ========================================
echo.

python archive_logs.py %*

if %errorlevel% neq 0 (
    echo.
    echo Archive failed!
    pause
    exit /b 1
)

echo.
echo Archive complete!
pause
