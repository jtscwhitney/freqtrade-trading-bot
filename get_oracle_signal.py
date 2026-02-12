#!/usr/bin/env python3
"""
Get current Oracle signal from log file or API
Usage: python get_oracle_signal.py
"""

import requests
import json
import re
from datetime import datetime
from requests.auth import HTTPBasicAuth
from pathlib import Path

# Configuration
API_BASE_URL = "http://localhost:8080"
USERNAME = "freqtrader"
PASSWORD = "SuperSecurePassword123"
LOG_FILE = Path("user_data/logs/freqtrade.log")

def get_latest_oracle_from_log():
    """Extract the latest Oracle signal from the log file"""
    try:
        if not LOG_FILE.exists():
            return None
        
        # Read the log file and search backwards for Oracle signals
        with open(LOG_FILE, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        # Search backwards for the most recent Oracle signal
        for line in reversed(lines):
            if "Oracle Signal Update" in line:
                # Parse the log line
                # Format: 2026-02-04 18:43:19,999 - OracleSurfer_v12_PROD - INFO - Oracle Signal Update - BTC/USDT:USDT | Timestamp: 1513 | Regime: BULL
                match = re.search(r'Oracle Signal Update - ([^|]+) \| Timestamp: (\d+) \| Regime: (\w+)', line)
                if match:
                    pair = match.group(1).strip()
                    timestamp = match.group(2)
                    regime = match.group(3)
                    
                    # Extract the log timestamp
                    time_match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                    log_time = time_match.group(1) if time_match else "Unknown"
                    
                    return {
                        'pair': pair,
                        'regime': regime,
                        'timestamp': timestamp,
                        'log_time': log_time,
                        'source': 'log_file'
                    }
        return None
    except Exception as e:
        print(f"Error reading log file: {e}")
        return None

def get_api_data(endpoint, use_auth=True):
    """Make authenticated API request"""
    try:
        auth = HTTPBasicAuth(USERNAME, PASSWORD) if use_auth else None
        response = requests.get(f"{API_BASE_URL}{endpoint}", auth=auth, timeout=5)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        return None

def main():
    print("=" * 70)
    print("Current Oracle Signal")
    print("=" * 70)
    print()
    
    # Method 1: Try to get from log file (most reliable)
    print("Method 1: Reading from log file...")
    oracle_signal = get_latest_oracle_from_log()
    
    if oracle_signal:
        print(f"   [OK] Found Oracle signal in log file")
        print()
        print("   Current Oracle Signal:")
        print(f"   Pair:        {oracle_signal['pair']}")
        print(f"   Regime:      {oracle_signal['regime']}")
        print(f"   Timestamp:   {oracle_signal['timestamp']}")
        print(f"   Log Time:    {oracle_signal['log_time']}")
        print()
        
        # Display regime interpretation
        regime = oracle_signal['regime']
        if regime == "BULL":
            print("   Interpretation: BULLISH - Oracle predicts upward movement")
        elif regime == "BEAR":
            print("   Interpretation: BEARISH - Oracle predicts downward movement")
        elif regime == "NEUTRAL":
            print("   Interpretation: NEUTRAL - Oracle predicts sideways movement")
        else:
            print(f"   Interpretation: Unknown regime ({regime})")
    else:
        print("   [WARNING] No Oracle signal found in log file")
        print("   (Bot may not have processed a new candle yet)")
        print()
    
    # Method 2: Try API endpoints (may not work, but worth trying)
    print("Method 2: Checking API endpoints...")
    api_endpoints = [
        "/api/v1/pair_candles/BTC_USDT:USDT?timeframe=1h&limit=1",
        "/api/v1/pairs",
    ]
    
    api_found = False
    for endpoint in api_endpoints:
        result = get_api_data(endpoint, use_auth=True)
        if result:
            print(f"   [OK] Retrieved data from {endpoint}")
            # Check if result contains FreqAI data
            if isinstance(result, dict):
                # Look for FreqAI-related keys
                freqai_keys = [k for k in result.keys() if 'freqai' in k.lower() or 'regime' in k.lower() or 'oracle' in k.lower()]
                if freqai_keys:
                    print(f"   Found FreqAI keys: {freqai_keys}")
                    api_found = True
            elif isinstance(result, list) and len(result) > 0:
                # Check first item for FreqAI data
                if isinstance(result[0], dict):
                    freqai_keys = [k for k in result[0].keys() if 'freqai' in k.lower() or 'regime' in k.lower()]
                    if freqai_keys:
                        print(f"   Found FreqAI data in response")
                        api_found = True
    if not api_found:
        print("   [INFO] API endpoints don't contain Oracle data")
        print("   (This is expected - use log file method instead)")
    print()
    
    # Summary
    print("=" * 70)
    if oracle_signal:
        print(f"Current Oracle Signal: {oracle_signal['regime']} for {oracle_signal['pair']}")
        print(f"Last Update: {oracle_signal['log_time']}")
    else:
        print("No Oracle signal found. The bot may be waiting for the next candle.")
        print("Oracle signals are logged every hour when a new candle closes.")
    print("=" * 70)
    print()
    print("Note: Oracle signals update every hour when a new candle closes.")
    print("Run this script again after the next hourly candle to see updates.")

if __name__ == "__main__":
    main()
