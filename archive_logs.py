#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Freqtrade Log Archiver
======================
Archives rotated log files before they are deleted by Freqtrade's log rotation.
This preserves log history beyond the default 3 rotated files.

Usage:
    python archive_logs.py [--log-dir user_data/logs] [--archive-dir user_data/logs/archive]
    
The script:
1. Checks for rotated log files (freqtrade.log.1, .2, .3)
2. Archives them with timestamps before they're deleted
3. Can be run manually or scheduled via cron/task scheduler
"""

import os
import shutil
import argparse
from pathlib import Path
from datetime import datetime
import sys

def archive_logs(log_dir="user_data/logs", archive_dir="user_data/logs/archive", dry_run=False):
    """
    Archive rotated log files before they're deleted
    
    Args:
        log_dir: Directory containing log files
        archive_dir: Directory to store archived logs
        dry_run: If True, only show what would be archived without actually doing it
    """
    log_path = Path(log_dir)
    archive_path = Path(archive_dir)
    
    if not log_path.exists():
        print(f"[ERROR] Log directory does not exist: {log_path}")
        return False
    
    # Create archive directory if it doesn't exist
    if not dry_run:
        archive_path.mkdir(parents=True, exist_ok=True)
        print(f"[INFO] Archive directory: {archive_path}")
    
    # Find rotated log files
    rotated_logs = []
    for i in range(1, 10):  # Check up to .9
        log_file = log_path / f"freqtrade.log.{i}"
        if log_file.exists():
            rotated_logs.append((i, log_file))
    
    if not rotated_logs:
        print(f"[INFO] No rotated log files found in {log_path}")
        return True
    
    print(f"[INFO] Found {len(rotated_logs)} rotated log file(s)")
    
    archived_count = 0
    skipped_count = 0
    
    for rotation_num, log_file in rotated_logs:
        # Get file modification time
        mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
        date_str = mtime.strftime("%Y%m%d")
        
        # Create archive filename: freqtrade-YYYYMMDD.log.N
        archive_filename = f"freqtrade-{date_str}.log.{rotation_num}"
        archive_file = archive_path / archive_filename
        
        # Check if already archived
        if archive_file.exists():
            print(f"[SKIP] Already archived: {log_file.name} -> {archive_filename}")
            skipped_count += 1
            continue
        
        if dry_run:
            print(f"[DRY-RUN] Would archive: {log_file.name} -> {archive_filename}")
            archived_count += 1
        else:
            try:
                # Copy (don't move) so original stays for Freqtrade rotation
                shutil.copy2(log_file, archive_file)
                print(f"[OK] Archived: {log_file.name} -> {archive_filename} ({log_file.stat().st_size / 1024 / 1024:.2f} MB)")
                archived_count += 1
            except Exception as e:
                print(f"[ERROR] Failed to archive {log_file.name}: {e}")
                return False
    
    print(f"\n[SUMMARY] Archived: {archived_count}, Skipped: {skipped_count}")
    
    # Clean up old archives (optional - keep last 30 days)
    if not dry_run and archive_path.exists():
        cleanup_old_archives(archive_path, days_to_keep=30)
    
    return True

def cleanup_old_archives(archive_path, days_to_keep=30):
    """Remove archived logs older than specified days"""
    cutoff_date = datetime.now().timestamp() - (days_to_keep * 24 * 60 * 60)
    
    deleted_count = 0
    deleted_size = 0
    
    for archive_file in archive_path.glob("freqtrade-*.log.*"):
        if archive_file.stat().st_mtime < cutoff_date:
            try:
                size = archive_file.stat().st_size
                archive_file.unlink()
                deleted_count += 1
                deleted_size += size
                print(f"[CLEANUP] Deleted old archive: {archive_file.name}")
            except Exception as e:
                print(f"[WARN] Failed to delete {archive_file.name}: {e}")
    
    if deleted_count > 0:
        print(f"[CLEANUP] Removed {deleted_count} old archive(s), freed {deleted_size / 1024 / 1024:.2f} MB")

def main():
    parser = argparse.ArgumentParser(
        description='Archive Freqtrade rotated log files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Archive logs with default paths
  python archive_logs.py

  # Specify custom directories
  python archive_logs.py --log-dir user_data/logs --archive-dir user_data/logs/archive

  # Dry run to see what would be archived
  python archive_logs.py --dry-run

  # Keep archives for 60 days instead of 30
  python archive_logs.py --keep-days 60
        """
    )
    
    parser.add_argument(
        '--log-dir',
        type=str,
        default='user_data/logs',
        help='Directory containing log files (default: user_data/logs)'
    )
    
    parser.add_argument(
        '--archive-dir',
        type=str,
        default='user_data/logs/archive',
        help='Directory to store archived logs (default: user_data/logs/archive)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be archived without actually doing it'
    )
    
    parser.add_argument(
        '--keep-days',
        type=int,
        default=30,
        help='Number of days to keep archived logs before cleanup (default: 30)'
    )
    
    args = parser.parse_args()
    
    print("="*70)
    print("FREQTRADE LOG ARCHIVER")
    print("="*70)
    print(f"Log Directory: {args.log_dir}")
    print(f"Archive Directory: {args.archive_dir}")
    print(f"Keep Archives: {args.keep_days} days")
    if args.dry_run:
        print("Mode: DRY RUN (no files will be modified)")
    print()
    
    success = archive_logs(
        log_dir=args.log_dir,
        archive_dir=args.archive_dir,
        dry_run=args.dry_run
    )
    
    if success:
        print("\n" + "="*70)
        print("ARCHIVE COMPLETE")
        print("="*70)
    else:
        print("\n" + "="*70)
        print("ARCHIVE FAILED")
        print("="*70)
        sys.exit(1)

if __name__ == "__main__":
    main()
