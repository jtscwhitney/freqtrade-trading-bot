# PowerShell script to stop/remove Freqtrade Log Archiving scheduled task

Write-Host "========================================"
Write-Host "STOPPING FREQTRADE LOG ARCHIVING"
Write-Host "========================================"
Write-Host ""

# Check if running as admin
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "[ERROR] This script must be run as Administrator" -ForegroundColor Red
    Write-Host "Right-click PowerShell and select 'Run as Administrator'" -ForegroundColor Yellow
    exit 1
}

$TaskName = "FreqtradeLogArchiver"

# Check if task exists
try {
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
    Write-Host "Found scheduled task: $TaskName"
    Write-Host "Current Status: $($task.State)"
    Write-Host ""
    
    Write-Host "Choose an option:"
    Write-Host "  1. Disable the task (can be re-enabled later)"
    Write-Host "  2. Delete the task completely"
    Write-Host "  3. Cancel"
    Write-Host ""
    $choice = Read-Host "Enter choice (1-3)"
    
    switch ($choice) {
        "1" {
            Write-Host ""
            Write-Host "Disabling task..."
            Disable-ScheduledTask -TaskName $TaskName
            Write-Host "[OK] Task disabled successfully!" -ForegroundColor Green
            Write-Host "     You can re-enable it later with:" -ForegroundColor Cyan
            Write-Host "     Enable-ScheduledTask -TaskName $TaskName" -ForegroundColor Cyan
        }
        "2" {
            Write-Host ""
            Write-Host "Deleting task..."
            Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
            Write-Host "[OK] Task deleted successfully!" -ForegroundColor Green
        }
        "3" {
            Write-Host ""
            Write-Host "Cancelled."
            exit 0
        }
        default {
            Write-Host ""
            Write-Host "[ERROR] Invalid choice" -ForegroundColor Red
            exit 1
        }
    }
} catch {
    Write-Host "[INFO] Scheduled task '$TaskName' not found." -ForegroundColor Yellow
    Write-Host "        It may have already been removed or never created."
    exit 0
}

Write-Host ""
Write-Host "Done!"
