#!/bin/bash
# ============================================================
# Freqtrade Dry Run Summary — droplet_dryrun_summary.sh
# Run on the DigitalOcean Droplet or via SSH:
#   ssh root@YOUR_IP 'bash -s' < scripts/droplet_dryrun_summary.sh
# Output: JSON to stdout, save with > dryrun_summary.json
# ============================================================

HOST="http://localhost:8080"
USER="freqtrader"
PASS="SuperSecurePassword123"
AUTH="-u ${USER}:${PASS}"

echo "{"

# --- Bot status ---
echo '"bot_status":'
curl -s $AUTH "${HOST}/api/v1/show_config" | python3 -c "
import json, sys
d = json.load(sys.stdin)
print(json.dumps({
    'state': d.get('state'),
    'strategy': d.get('strategy'),
    'dry_run': d.get('dry_run'),
    'timeframe': d.get('timeframe'),
    'stake_amount': d.get('stake_amount'),
    'max_open_trades': d.get('max_open_trades'),
    'bot_name': d.get('bot_name'),
    'freqai_enabled': d.get('freqai', {}).get('enabled'),
    'freqai_identifier': d.get('freqai', {}).get('identifier'),
}, indent=2))
"
echo ","

# --- Profit summary ---
echo '"profit_summary":'
curl -s $AUTH "${HOST}/api/v1/profit" | python3 -c "
import json, sys
d = json.load(sys.stdin)
print(json.dumps({
    'profit_all_coin':        d.get('profit_all_coin'),
    'profit_all_percent':     d.get('profit_all_percent'),
    'profit_all_percent_mean':d.get('profit_all_percent_mean'),
    'profit_factor':          d.get('profit_factor'),
    'winning_trades':         d.get('winning_trades'),
    'losing_trades':          d.get('losing_trades'),
    'draw_trades':            d.get('draw_trades'),
    'winrate':                d.get('winrate'),
    'expectancy':             d.get('expectancy'),
    'expectancy_ratio':       d.get('expectancy_ratio'),
    'sharpe':                 d.get('sharpe'),
    'sortino':                d.get('sortino'),
    'calmar':                 d.get('calmar'),
    'max_drawdown':           d.get('max_drawdown'),
    'max_drawdown_abs':       d.get('max_drawdown_abs'),
    'trade_count':            d.get('trade_count'),
    'first_trade_date':       d.get('first_trade_date'),
    'latest_trade_date':      d.get('latest_trade_date'),
    'avg_duration':           d.get('avg_duration'),
    'best_pair':              d.get('best_pair'),
    'worst_pair':             d.get('worst_pair'),
    'profit_closed_coin':     d.get('profit_closed_coin'),
    'profit_closed_percent':  d.get('profit_closed_percent'),
    'profit_closed_percent_mean': d.get('profit_closed_percent_mean'),
    'closed_trade_count':     d.get('closed_trade_count'),
    'open_trade_count':       d.get('open_trade_count'),
    'bot_start_date':         d.get('bot_start_date'),
    'bot_start_timestamp':    d.get('bot_start_timestamp'),
}, indent=2))
"
echo ","

# --- Performance per pair ---
echo '"performance":'
curl -s $AUTH "${HOST}/api/v1/performance" | python3 -c "
import json, sys
d = json.load(sys.stdin)
print(json.dumps(d, indent=2))
"
echo ","

# --- Exit reason breakdown ---
echo '"exit_reasons":'
curl -s $AUTH "${HOST}/api/v1/trades?limit=500&offset=0" | python3 -c "
import json, sys
from collections import defaultdict
d = json.load(sys.stdin)
trades = d.get('trades', [])
reasons = defaultdict(lambda: {'count': 0, 'profit_sum': 0.0, 'profit_pcts': []})
for t in trades:
    if t.get('is_open'): continue
    r = t.get('exit_reason', 'unknown')
    pct = t.get('profit_pct', 0) or 0
    reasons[r]['count'] += 1
    reasons[r]['profit_sum'] += pct
    reasons[r]['profit_pcts'].append(pct)
result = {}
for k, v in reasons.items():
    n = v['count']
    result[k] = {
        'count': n,
        'avg_profit_pct': round(v['profit_sum'] / n, 4) if n else 0,
        'total_profit_pct': round(v['profit_sum'], 4),
    }
print(json.dumps(result, indent=2))
"
echo ","

# --- Open trades ---
echo '"open_trades":'
curl -s $AUTH "${HOST}/api/v1/status" | python3 -c "
import json, sys
d = json.load(sys.stdin)
out = []
for t in d:
    out.append({
        'pair':          t.get('pair'),
        'open_date':     t.get('open_date'),
        'open_rate':     t.get('open_rate'),
        'current_rate':  t.get('current_rate'),
        'profit_pct':    t.get('profit_pct'),
        'profit_abs':    t.get('profit_abs'),
        'trade_id':      t.get('trade_id'),
        'enter_tag':     t.get('enter_tag'),
        'is_short':      t.get('is_short'),
        'amount':        t.get('amount'),
        'stake_amount':  t.get('stake_amount'),
    })
print(json.dumps(out, indent=2))
"
echo ","

# --- Last 20 closed trades (most recent activity) ---
echo '"recent_closed_trades":'
curl -s $AUTH "${HOST}/api/v1/trades?limit=20&offset=0" | python3 -c "
import json, sys
d = json.load(sys.stdin)
trades = d.get('trades', [])
closed = [t for t in trades if not t.get('is_open')][:20]
out = []
for t in closed:
    out.append({
        'trade_id':    t.get('trade_id'),
        'pair':        t.get('pair'),
        'open_date':   t.get('open_date'),
        'close_date':  t.get('close_date'),
        'open_rate':   t.get('open_rate'),
        'close_rate':  t.get('close_rate'),
        'profit_pct':  t.get('profit_pct'),
        'profit_abs':  t.get('profit_abs'),
        'exit_reason': t.get('exit_reason'),
        'enter_tag':   t.get('enter_tag'),
        'is_short':    t.get('is_short'),
    })
print(json.dumps(out, indent=2))
"
echo ","

# --- FreqAI model info (last training) ---
echo '"freqai_info":'
curl -s $AUTH "${HOST}/api/v1/freqai/Oracle_Surfer_DryRun/BTC%2FUSDT%3AUSDT" 2>/dev/null | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    print(json.dumps(d, indent=2))
except:
    print('\"not_available\"')
"
echo ","

# --- Balance / wallet ---
echo '"balance":'
curl -s $AUTH "${HOST}/api/v1/balance" | python3 -c "
import json, sys
d = json.load(sys.stdin)
print(json.dumps({
    'currencies': [c for c in d.get('currencies', []) if c.get('currency') in ('USDT', 'BTC')],
    'total': d.get('total'),
    'value': d.get('value'),
    'starting_capital': d.get('starting_capital'),
    'starting_capital_pct': d.get('starting_capital_pct'),
}, indent=2))
"

echo "}"
