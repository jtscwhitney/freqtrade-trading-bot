# Quick Start: Log Rotation Setup

## 🚀 Fast Setup (Choose One)

### Option A: Windows (Recommended)

1. **Run archiver manually:**
   ```batch
   archive_logs.bat
   ```

2. **Set up automatic archiving (as Administrator):**
   ```powershell
   .\setup_log_rotation_windows.ps1
   ```

### Option B: Linux/Mac

1. **Run archiver manually:**
   ```bash
   python3 archive_logs.py
   ```

2. **Set up automatic archiving:**
   ```bash
   sudo cp logrotate_freqtrade.conf /etc/logrotate.d/freqtrade
   sudo nano /etc/logrotate.d/freqtrade  # Edit path if needed
   ```

## ✅ What Changed

1. **docker-compose.yml**: Updated to use consistent log path (`user_data/logs/`)
2. **archive_logs.py**: Script to preserve logs before deletion
3. **Windows Task Scheduler**: Automatic archiving every hour
4. **Linux Logrotate**: Keeps 10 rotated files instead of 3

## 📁 Archive Location

Archived logs are saved to: `user_data/logs/archive/`

Files are named: `freqtrade-YYYYMMDD.log.N`

## 🔍 Verify It Works

```bash
# Test archiving (dry run)
python archive_logs.py --dry-run

# Check archive directory
dir user_data\logs\archive
```

## 📖 Full Documentation

See `LOG_ROTATION_SETUP.md` for detailed instructions.
