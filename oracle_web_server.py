#!/usr/bin/env python3
"""
Simple web server to display Oracle signals in a browser
Run this script and open http://localhost:8888 in your browser
"""

from flask import Flask, jsonify, render_template_string
import re
from pathlib import Path
from datetime import datetime

app = Flask(__name__)

LOG_FILE = Path("user_data/logs/freqtrade.log")

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="60">
    <title>Oracle Signal Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        .container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            padding: 40px;
            max-width: 700px;
            width: 100%;
        }
        h1 {
            color: #333;
            margin-bottom: 10px;
            text-align: center;
            font-size: 2em;
        }
        .subtitle {
            text-align: center;
            color: #6c757d;
            margin-bottom: 30px;
            font-size: 0.9em;
        }
        .signal-box {
            background: #f8f9fa;
            border-radius: 15px;
            padding: 30px;
            margin-bottom: 20px;
        }
        .regime-display {
            text-align: center;
            padding: 30px;
            border-radius: 15px;
            margin-bottom: 20px;
            font-size: 3em;
            font-weight: bold;
        }
        .regime-bull {
            background: #d4edda;
            color: #155724;
            border: 3px solid #28a745;
        }
        .regime-bear {
            background: #f8d7da;
            color: #721c24;
            border: 3px solid #dc3545;
        }
        .regime-neutral {
            background: #fff3cd;
            color: #856404;
            border: 3px solid #ffc107;
        }
        .signal-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            padding: 10px 0;
            border-bottom: 1px solid #e9ecef;
        }
        .signal-row:last-child {
            border-bottom: none;
        }
        .label {
            font-weight: 600;
            color: #555;
            font-size: 1.1em;
        }
        .value {
            font-size: 1.2em;
            font-weight: bold;
            color: #333;
        }
        .timestamp {
            color: #6c757d;
            font-size: 0.9em;
            text-align: center;
            margin-top: 20px;
        }
        .interpretation {
            text-align: center;
            padding: 15px;
            background: #e9ecef;
            border-radius: 10px;
            margin-top: 20px;
            font-style: italic;
            color: #495057;
        }
        .link-box {
            background: #e7f3ff;
            border-radius: 10px;
            padding: 15px;
            margin-top: 20px;
            text-align: center;
        }
        .link-box a {
            color: #0066cc;
            text-decoration: none;
            font-weight: 600;
        }
        .link-box a:hover {
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔮 Oracle Signal Dashboard</h1>
        <div class="subtitle">Real-time FreqAI Regime Predictions</div>
        
        {% if oracle_signal %}
        <div class="regime-display regime-{{ oracle_signal.regime.lower() }}">
            {{ oracle_signal.regime }}
        </div>
        
        <div class="signal-box">
            <div class="signal-row">
                <span class="label">Trading Pair:</span>
                <span class="value">{{ oracle_signal.pair }}</span>
            </div>
            <div class="signal-row">
                <span class="label">Regime:</span>
                <span class="value">{{ oracle_signal.regime }}</span>
            </div>
            <div class="signal-row">
                <span class="label">Last Update:</span>
                <span class="value">{{ oracle_signal.log_time }}</span>
            </div>
            <div class="signal-row">
                <span class="label">Timestamp:</span>
                <span class="value">{{ oracle_signal.timestamp }}</span>
            </div>
        </div>
        
        <div class="interpretation">
            {{ oracle_signal.interpretation }}
        </div>
        {% else %}
        <div class="signal-box">
            <div style="text-align: center; color: #6c757d; padding: 20px;">
                No Oracle signal found yet.<br>
                The bot may be waiting for the next candle to close.<br>
                <br>
                Oracle signals update every hour when a new candle closes.
            </div>
        </div>
        {% endif %}
        
        <div class="timestamp">
            Page auto-refreshes every 60 seconds<br>
            Last refresh: {{ current_time }}
        </div>
        
        <div class="link-box">
            <a href="http://localhost:8080" target="_blank">Open Freqtrade Web UI</a> | 
            <a href="/api/oracle" target="_blank">JSON API</a>
        </div>
    </div>
</body>
</html>
"""

def get_latest_oracle_from_log():
    """Extract the latest Oracle signal from the log file"""
    try:
        if not LOG_FILE.exists():
            return None
        
        with open(LOG_FILE, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        for line in reversed(lines):
            # Try new format first: "Oracle Signal for BTC/USDT:USDT: BULL"
            if "Oracle Signal for" in line:
                # Match everything after "Oracle Signal for " until the last ": " before the regime
                match = re.search(r'Oracle Signal for (.+?):\s*(\w+)$', line)
                if match:
                    pair = match.group(1).strip()
                    regime = match.group(2).strip()
                    
                    time_match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                    log_time = time_match.group(1) if time_match else "Unknown"
                    
                    interpretation = {
                        'BULL': 'BULLISH - Oracle predicts upward movement',
                        'BEAR': 'BEARISH - Oracle predicts downward movement',
                        'NEUTRAL': 'NEUTRAL - Oracle predicts sideways movement'
                    }.get(regime, f'Unknown regime: {regime}')
                    
                    return {
                        'pair': pair,
                        'regime': regime,
                        'timestamp': log_time,  # Use log_time as timestamp
                        'log_time': log_time,
                        'interpretation': interpretation
                    }
            # Fallback to old format: "Oracle Signal Update - BTC/USDT:USDT | Timestamp: 1517 | Regime: BULL"
            elif "Oracle Signal Update" in line:
                match = re.search(r'Oracle Signal Update - ([^|]+) \| Timestamp: (\d+) \| Regime: (\w+)', line)
                if match:
                    pair = match.group(1).strip()
                    timestamp = match.group(2)
                    regime = match.group(3)
                    
                    time_match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                    log_time = time_match.group(1) if time_match else "Unknown"
                    
                    interpretation = {
                        'BULL': 'BULLISH - Oracle predicts upward movement',
                        'BEAR': 'BEARISH - Oracle predicts downward movement',
                        'NEUTRAL': 'NEUTRAL - Oracle predicts sideways movement'
                    }.get(regime, f'Unknown regime: {regime}')
                    
                    return {
                        'pair': pair,
                        'regime': regime,
                        'timestamp': timestamp,
                        'log_time': log_time,
                        'interpretation': interpretation
                    }
        return None
    except Exception as e:
        print(f"Error reading log file: {e}")
        return None

@app.route('/')
def index():
    """Main dashboard page"""
    oracle_signal = get_latest_oracle_from_log()
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return render_template_string(HTML_TEMPLATE, 
                                 oracle_signal=oracle_signal,
                                 current_time=current_time)

@app.route('/api/oracle')
def api_oracle():
    """JSON API endpoint for Oracle signal"""
    oracle_signal = get_latest_oracle_from_log()
    if oracle_signal:
        return jsonify({
            'status': 'success',
            'data': oracle_signal
        })
    else:
        return jsonify({
            'status': 'no_signal',
            'message': 'No Oracle signal found. Bot may be waiting for next candle.'
        })

if __name__ == '__main__':
    print("=" * 70)
    print("Oracle Signal Web Dashboard")
    print("=" * 70)
    print()
    print("Starting web server on http://localhost:8888")
    print("Open this URL in your browser to see the Oracle signal dashboard")
    print()
    print("Endpoints:")
    print("  - http://localhost:8888/          (Dashboard)")
    print("  - http://localhost:8888/api/oracle (JSON API)")
    print()
    print("Press Ctrl+C to stop the server")
    print("=" * 70)
    print()
    
    app.run(host='0.0.0.0', port=8888, debug=False)
