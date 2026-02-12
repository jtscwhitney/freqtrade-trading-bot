@echo off
REM Launches PowerShell as Administrator to run the log rotation setup script
REM This is a workaround if you can't run Cursor as Administrator

echo ========================================
echo LAUNCHING POWERSHELL AS ADMINISTRATOR
echo ========================================
echo.
echo This will open a new PowerShell window with Administrator privileges.
echo In that window, navigate to this directory and run:
echo   .\setup_log_rotation_windows.ps1
echo.
pause

REM Launch PowerShell as Administrator
powershell -Command "Start-Process powershell -ArgumentList '-NoExit', '-Command', 'cd ''%CD%''; Write-Host \"Current Directory: %CD%\" -ForegroundColor Green; Write-Host \"Run: .\setup_log_rotation_windows.ps1\" -ForegroundColor Yellow' -Verb RunAs"
