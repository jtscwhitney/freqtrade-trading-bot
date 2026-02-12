#!/usr/bin/env python3
"""
Simple script to check Oracle predictions via Freqtrade API
Usage: python check_oracle_api.py
"""

import requests
import json
from datetime import datetime
from requests.auth import HTTPBasicAuth

# Configuration
API_BASE_URL = "http://localhost:8080"
USERNAME = "freqtrader"
PASSWORD = "SuperSecurePassword123"

def get_api_data(endpoint, use_auth=True):
    """Make authenticated API request using Basic Auth"""
    try:
        auth = HTTPBasicAuth(USERNAME, PASSWORD) if use_auth else None
        response = requests.get(f"{API_BASE_URL}{endpoint}", auth=auth)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"   API request failed: {response.status_code} - {response.text[:200]}")
            return None
    except Exception as e:
        print(f"   Error making API request: {e}")
        return None

def main():
    print("=" * 60)
    print("Oracle API Access Check")
    print("=" * 60)
    print()
    
    # Test ping first (no auth required)
    print("1. Testing API connection...")
    ping_result = get_api_data("/api/v1/ping", use_auth=False)
    if ping_result:
        print(f"   [OK] API is accessible: {ping_result}")
    else:
        print("   [FAIL] API is not accessible. Is the bot running?")
        return
    print()
    
    # Test authentication with version endpoint (more reliable)
    print("2. Testing authentication...")
    version = get_api_data("/api/v1/version", use_auth=True)
    if version:
        print("   [OK] Authentication successful")
        print(f"   Freqtrade Version: {version.get('version', 'unknown')}")
    else:
        print("   [FAIL] Authentication failed - check username/password in config")
        return
    print()
    
    # Get status
    print("3. Getting bot status...")
    status = get_api_data("/api/v1/status", use_auth=True)
    if status is not None:
        if isinstance(status, list):
            print(f"   Status: {status}")
            print("   (Status endpoint returns array format)")
        elif isinstance(status, dict):
            print(f"   Bot State: {status.get('state', 'unknown')}")
            print(f"   Strategy: {status.get('strategy', 'unknown')}")
    print()
    
    # Get balance (shows bot is working)
    print("4. Getting account balance...")
    balance = get_api_data("/api/v1/balance", use_auth=True)
    if balance:
        currencies = balance.get('currencies', [])
        print(f"   Account Balance:")
        for curr in currencies[:3]:  # Show first 3 currencies
            print(f"   - {curr.get('currency', 'unknown')}: {curr.get('balance', 0):.2f} (Free: {curr.get('free', 0):.2f})")
    print()
    
    # Try to get trades (different endpoint formats)
    print("5. Checking for trades...")
    trade_endpoints = [
        "/api/v1/trades",
        "/api/v1/trades/open",
        "/api/v1/trades?limit=5"
    ]
    trades_found = False
    for endpoint in trade_endpoints:
        trades = get_api_data(endpoint, use_auth=True)
        if trades and isinstance(trades, list) and len(trades) > 0:
            print(f"   Found {len(trades)} trades via {endpoint}")
            for trade in trades[:3]:
                if isinstance(trade, dict):
                    print(f"   - {trade.get('pair', 'unknown')}: {trade.get('profit_pct', 0):.2f}%")
            trades_found = True
            break
        elif trades and isinstance(trades, dict):
            trade_list = trades.get('trades', [])
            if trade_list:
                print(f"   Found {len(trade_list)} trades")
                for trade in trade_list[:3]:
                    print(f"   - {trade.get('pair', 'unknown')}: {trade.get('profit_pct', 0):.2f}%")
                trades_found = True
                break
    if not trades_found:
        print("   No trades found (this is normal if no trades are open)")
    print()
    
    # Try FreqAI-specific endpoints (may not exist in all versions)
    print("6. Checking for FreqAI/Oracle endpoints...")
    freqai_endpoints = [
        "/api/v1/freqai/info",
        "/api/v1/freqai/predictions",
        "/api/v1/freqai/status"
    ]
    freqai_found = False
    for endpoint in freqai_endpoints:
        result = get_api_data(endpoint, use_auth=True)
        if result:
            print(f"   [OK] {endpoint}:")
            print(json.dumps(result, indent=4))
            freqai_found = True
            break
    if not freqai_found:
        print("   (FreqAI-specific API endpoints not available)")
        print("   Oracle predictions are available via the web UI at http://localhost:8080")
    print()
    
    print("=" * 60)
    print("Note: Some endpoints may vary by Freqtrade version.")
    print("The web UI at http://localhost:8080 is the most reliable way")
    print("to view Oracle predictions.")
    print("=" * 60)

if __name__ == "__main__":
    main()
