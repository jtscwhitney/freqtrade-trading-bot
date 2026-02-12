#!/usr/bin/env python3
"""
Log API Service - Serves Freqtrade log file for download.
Runs as a sidecar container sharing the user_data volume.
Matches the logfile path from docker-compose: /freqtrade/user_data/logs/freqtrade.log
"""

import os
from pathlib import Path
from flask import Flask, Response, send_file, request
from functools import wraps

app = Flask(__name__)

# Path must match docker-compose --logfile parameter
LOG_FILE = Path(os.environ.get("LOG_FILE", "/freqtrade/user_data/logs/freqtrade.log"))

# Auth - matches Freqtrade API credentials (from config or env)
API_USERNAME = os.environ.get("FREQTRADE_API_USERNAME", "freqtrader")
API_PASSWORD = os.environ.get("FREQTRADE_API_PASSWORD", "SuperSecurePassword123")


def require_auth(f):
    """Basic Auth decorator matching Freqtrade API"""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or auth.username != API_USERNAME or auth.password != API_PASSWORD:
            return Response(
                "Unauthorized",
                401,
                {"WWW-Authenticate": 'Basic realm="Log API"'},
            )
        return f(*args, **kwargs)
    return decorated


@app.route("/api/v1/logs/download")
@require_auth
def download_log():
    """Download the Freqtrade log file as attachment."""
    if not LOG_FILE.exists():
        return Response("Log file not found", status=404)
    try:
        return send_file(
            LOG_FILE,
            as_attachment=True,
            download_name="freqtrade.log",
            mimetype="text/plain",
        )
    except Exception as e:
        return Response(str(e), status=500)


@app.route("/api/v1/logs/health")
def health():
    """Health check endpoint (no auth required)."""
    return {"status": "ok", "log_exists": LOG_FILE.exists()}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8081)
