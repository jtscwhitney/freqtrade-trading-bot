# Freqtrade Log Rotation Setup Guide

This guide helps you preserve log history beyond Freqtrade's default 3 rotated files.

## Problem

Freqtrade automatically rotates logs when they reach ~10MB:
- `freqtrade.log` → `freqtrade.log.1`
- `freqtrade.log.1` → `freqtrade.log.2`
- `freqtrade.log.2` → `freqtrade.log.3`
- `freqtrade.log.3` → **DELETED** (oldest logs are lost)

This means you only have ~30MB of log history (~3 files × 10MB).

## Solutions

### Solution 1: Manual Log Archiving Script ✅

**Windows:**
```batch
archive_logs.bat
```

**Linux/Mac:**
```bash
python3 archive_logs.py
# or
./archive_logs.sh
```

**Features:**
- Archives rotated logs before they're deleted
- Creates timestamped archive files: `freqtrade-YYYYMMDD.log.N`
- Automatically cleans up archives older than 30 days (configurable)
- Can be run manually or scheduled

**Options:**
```bash
python archive_logs.py --help
python archive_logs.py --log-dir user_data/logs --archive-dir user_data/logs/archive
python archive_logs.py --dry-run  # See what would be archived
python archive_logs.py --keep-days 60  # Keep archives for 60 days
```

### Solution 2: Windows Task Scheduler (Automatic) ✅

**Setup:**
1. Open PowerShell as Administrator
2. Run:
```powershell
.\setup_log_rotation_windows.ps1
```

This creates a scheduled task that runs `archive_logs.py` every hour.

**Manual Task Management:**
```powershell
# View task
Get-ScheduledTask -TaskName FreqtradeLogArchiver

# Run immediately
Start-ScheduledTask -TaskName FreqtradeLogArchiver

# Remove task
Unregister-ScheduledTask -TaskName FreqtradeLogArchiver -Confirm:$false
```

### Solution 3: Linux Logrotate (Automatic) ✅

**Setup:**
1. Copy `logrotate_freqtrade.conf` to `/etc/logrotate.d/freqtrade`:
```bash
sudo cp logrotate_freqtrade.conf /etc/logrotate.d/freqtrade
```

2. Edit the path in the config file to match your setup:
```bash
sudo nano /etc/logrotate.d/freqtrade
```

3. Test the configuration:
```bash
sudo logrotate -d /etc/logrotate.d/freqtrade
```

4. Run manually to test:
```bash
sudo logrotate -f /etc/logrotate.d/freqtrade
```

**Configuration:**
- Keeps 10 rotated files (instead of 3)
- Compresses old logs to save space
- Rotates at 10MB (matches Freqtrade's internal rotation)

### Solution 4: Consistent Log Path ✅

**Updated `docker-compose.yml`:**
- Changed log path from `/freqtrade/logs/freqtrade.log` to `/freqtrade/user_data/logs/freqtrade.log`
- All logs now stored in `user_data/logs/` for consistency
- Works with both `docker compose up` and `docker compose run --rm`

**If using `docker compose run --rm` directly:**
```bash
docker compose run --rm freqtrade trade \
  --config /freqtrade/user_data/config_sniper_BTC_DryRun.json \
  --strategy OracleSurfer_v12_PROD \
  --freqaimodel XGBoostClassifier \
  --logfile /freqtrade/user_data/logs/freqtrade.log \
  --userdir /freqtrade/user_data \
  -v
```

## Archive Directory Structure

After archiving, your log structure will look like:
```
user_data/logs/
├── freqtrade.log              # Current log
├── freqtrade.log.1            # Most recent rotation
├── freqtrade.log.2            # Second rotation
├── freqtrade.log.3            # Third rotation (oldest kept by Freqtrade)
└── archive/                   # Archived logs (preserved)
    ├── freqtrade-20260204.log.1
    ├── freqtrade-20260204.log.2
    ├── freqtrade-20260204.log.3
    ├── freqtrade-20260205.log.1
    └── ...
```

## Best Practices

1. **Run archiving frequently**: Archive logs before they reach rotation limit
   - Recommended: Every hour (via Task Scheduler/cron)
   - Minimum: Once per day

2. **Monitor archive size**: Archives can grow large over time
   - Default: Keeps archives for 30 days
   - Adjust with `--keep-days` parameter

3. **Backup archives**: Consider backing up archive directory periodically
   ```bash
   # Example: Backup monthly
   tar -czf freqtrade-logs-2026-02.tar.gz user_data/logs/archive/
   ```

4. **Test archiving**: Run with `--dry-run` first to verify:
   ```bash
   python archive_logs.py --dry-run
   ```

## Troubleshooting

### "No rotated log files found"
- Logs haven't rotated yet (current log is < 10MB)
- Check log directory path is correct
- Verify logs are being written

### "Permission denied"
- Windows: Run PowerShell as Administrator
- Linux: Use `sudo` or ensure user has write access to archive directory

### "Archive directory not found"
- Script will create it automatically
- If it fails, create manually: `mkdir -p user_data/logs/archive`

### Scheduled task not running
- Check Task Scheduler: `taskschd.msc`
- Verify Python path is correct in task action
- Check task history for errors

## Summary

✅ **Log Archiving Script**: `archive_logs.py` - Manual or scheduled archiving  
✅ **Windows Automation**: `setup_log_rotation_windows.ps1` - Task Scheduler setup  
✅ **Linux Automation**: `logrotate_freqtrade.conf` - Logrotate configuration  
✅ **Consistent Log Path**: Updated `docker-compose.yml` - All logs in `user_data/logs/`

Your logs will now be preserved indefinitely (or until you manually clean up old archives)!
