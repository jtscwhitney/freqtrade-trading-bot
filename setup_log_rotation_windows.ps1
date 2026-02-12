# PowerShell script to set up Windows Task Scheduler for log archiving
# Run this script as Administrator to schedule automatic log archiving

param(
    [string]$ScriptPath = "$PSScriptRoot\archive_logs.py",
    [string]$PythonPath = "python",
    [int]$IntervalMinutes = 60
)

Write-Host "========================================"
Write-Host "FREQTRADE LOG ARCHIVING SETUP"
Write-Host "========================================"
Write-Host ""

# Check if running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "[ERROR] This script must be run as Administrator" -ForegroundColor Red
    Write-Host "Right-click PowerShell and select 'Run as Administrator'" -ForegroundColor Yellow
    exit 1
}

# Verify script exists
if (-not (Test-Path $ScriptPath)) {
    Write-Host "[ERROR] Archive script not found: $ScriptPath" -ForegroundColor Red
    exit 1
}

# Get absolute path
$ScriptPath = (Resolve-Path $ScriptPath).Path
$WorkingDir = Split-Path -Parent $ScriptPath

Write-Host "Script Path: $ScriptPath"
Write-Host "Working Directory: $WorkingDir"
Write-Host "Python: $PythonPath"
Write-Host "Interval: Every $IntervalMinutes minutes"
Write-Host ""

# Create scheduled task
$TaskName = "FreqtradeLogArchiver"
$TaskDescription = "Automatically archives Freqtrade rotated log files before they're deleted"

# Check if task already exists
$existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existingTask) {
    Write-Host "[INFO] Task already exists. Updating..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# Create action
$Action = New-ScheduledTaskAction -Execute $PythonPath -Argument "`"$ScriptPath`"" -WorkingDirectory $WorkingDir

# Create trigger (every hour)
$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes) -RepetitionDuration (New-TimeSpan -Days 365)

# Create settings
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RunOnlyIfNetworkAvailable:$false

# Create principal (run as current user)
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

# Register task
try {
    Register-ScheduledTask -TaskName $TaskName -Description $TaskDescription -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal | Out-Null
    Write-Host "[OK] Scheduled task created successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Task Name: $TaskName"
    Write-Host "Next Run: $((Get-ScheduledTask -TaskName $TaskName).Triggers[0].NextRunTime)"
    Write-Host ""
    Write-Host "To view/manage the task:" -ForegroundColor Cyan
    Write-Host "  Task Scheduler -> Task Scheduler Library -> $TaskName"
    Write-Host ""
    Write-Host "To test immediately:" -ForegroundColor Cyan
    Write-Host "  Start-ScheduledTask -TaskName $TaskName"
    Write-Host ""
    Write-Host "To remove the task:" -ForegroundColor Yellow
    Write-Host "  Unregister-ScheduledTask -TaskName $TaskName -Confirm:`$false"
} catch {
    Write-Host "[ERROR] Failed to create scheduled task: $_" -ForegroundColor Red
    exit 1
}
