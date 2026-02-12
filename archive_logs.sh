#!/bin/bash
# Freqtrade Log Archiver - Linux/Mac Script
# Archives rotated log files before they're deleted

echo "========================================"
echo "FREQTRADE LOG ARCHIVER"
echo "========================================"
echo

python3 archive_logs.py "$@"

if [ $? -ne 0 ]; then
    echo
    echo "Archive failed!"
    exit 1
fi

echo
echo "Archive complete!"
