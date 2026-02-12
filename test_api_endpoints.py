#!/usr/bin/env python3
"""Quick test of API endpoints"""
import requests
from requests.auth import HTTPBasicAuth

API_BASE = "http://localhost:8080"
AUTH = HTTPBasicAuth('freqtrader', 'SuperSecurePassword123')

endpoints = [
    ('/api/v1/ping', False),
    ('/api/v1/status', True),
    ('/api/v1/version', True),
    ('/api/v1/trades/open', True),
    ('/api/v1/balance', True),
]

for endpoint, needs_auth in endpoints:
    auth = AUTH if needs_auth else None
    try:
        r = requests.get(f"{API_BASE}{endpoint}", auth=auth)
        print(f"{endpoint}: {r.status_code} - {str(r.json())[:100]}")
    except Exception as e:
        print(f"{endpoint}: Error - {e}")
