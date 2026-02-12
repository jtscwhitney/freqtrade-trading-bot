# Merge Trades with Oracle Signals

This script merges Freqtrade backtest trade exports with Oracle (FreqAI) predictions, providing a comprehensive view of trade performance alongside Oracle regime signals and confidence scores.

## Features

- ✅ Merges trade data with Oracle predictions from feather files
- ✅ Includes Oracle regime (BULL/BEAR/NEUTRAL) at entry and exit
- ✅ Includes Oracle confidence scores (probability values)
- ✅ Tracks Oracle regime changes during trades
- ✅ Supports both JSON and CSV trade exports
- ✅ Exports to CSV or JSON format

## Prerequisites

1. **Run a backtest with FreqAI enabled:**
   ```bash
   freqtrade backtesting \
     --strategy OracleSurfer_v12_PROD \
     --config user_data/config_sniper_BTC_DryRun.json \
     --freqaimodel XGBoostClassifier \
     --timerange 20250101-20250201 \
     --export trades
   ```

2. **Ensure prediction files exist:**
   - Predictions are automatically saved to: `user_data/models/{freqai_identifier}/backtesting_predictions/`
   - Files are named: `cb_btc_{timestamp}_prediction.feather`

## Usage

### Windows (Batch File)

```batch
merge_trades_with_oracle.bat user_data\backtest_results\backtest-result.json Oracle_Surfer_DryRun trades_with_oracle.csv
```

### Python Script (Cross-Platform)

```bash
python merge_trades_with_oracle.py \
  --trades-file user_data/backtest_results/backtest-result.json \
  --freqai-id Oracle_Surfer_DryRun \
  --output trades_with_oracle.csv
```

### Command-Line Options

```
--trades-file PATH       Path to trade export file (JSON or CSV)
--trades PATTERN         Glob pattern to find trade files (e.g., "*.json")
--freqai-id ID           FreqAI identifier from config (required)
--pair SYMBOL            Trading pair symbol (default: BTC)
--output PATH            Output file path (default: trades_with_oracle.csv)
--format FORMAT          Output format: csv, json, or both (default: csv)
```

## Examples

### Example 1: Merge Single Trade File

```bash
python merge_trades_with_oracle.py \
  --trades-file user_data/backtest_results/backtest-result.json \
  --freqai-id Oracle_Surfer_DryRun \
  --output trades_with_oracle.csv
```

### Example 2: Merge Multiple Trade Files

```bash
python merge_trades_with_oracle.py \
  --trades "user_data/backtest_results/*.json" \
  --freqai-id Oracle_Surfer_DryRun \
  --output combined_trades_with_oracle.csv
```

### Example 3: Export as JSON

```bash
python merge_trades_with_oracle.py \
  --trades-file user_data/backtest_results/backtest-result.json \
  --freqai-id Oracle_Surfer_DryRun \
  --output trades_with_oracle.json \
  --format json
```

### Example 4: Export Both Formats

```bash
python merge_trades_with_oracle.py \
  --trades-file user_data/backtest_results/backtest-result.json \
  --freqai-id Oracle_Surfer_DryRun \
  --output trades_with_oracle \
  --format both
```

## Output Columns

The merged output includes all original trade columns plus:

### Entry Oracle Data
- `entry_oracle_regime` - Oracle prediction at entry (BULL/BEAR/NEUTRAL)
- `entry_oracle_bear_prob` - BEAR probability at entry (0.0-1.0)
- `entry_oracle_bull_prob` - BULL probability at entry (0.0-1.0)
- `entry_oracle_neutral_prob` - NEUTRAL probability at entry (0.0-1.0)
- `entry_oracle_confidence` - Highest probability (confidence score)
- `entry_oracle_prediction_time` - Timestamp of Oracle prediction used
- `entry_oracle_do_predict` - Whether prediction was valid

### Exit Oracle Data
- `exit_oracle_regime` - Oracle prediction at exit (BULL/BEAR/NEUTRAL)
- `exit_oracle_bear_prob` - BEAR probability at exit
- `exit_oracle_bull_prob` - BULL probability at exit
- `exit_oracle_neutral_prob` - NEUTRAL probability at exit
- `exit_oracle_confidence` - Highest probability at exit
- `exit_oracle_prediction_time` - Timestamp of Oracle prediction used
- `exit_oracle_do_predict` - Whether prediction was valid

### Oracle Change Tracking
- `oracle_regime_changed` - Boolean: Did regime change during trade?
- `oracle_regime_change` - String: "BULL -> BEAR" (if changed)

## Understanding Oracle Signals

### Regime Classifications
- **BULL** - Market expected to rise significantly (>2×ATR in next ~4 days)
- **BEAR** - Market expected to fall significantly (<-2×ATR in next ~4 days)
- **NEUTRAL** - Sideways or unclear movement

### Confidence Scores
- Each regime has a probability (0.0 to 1.0)
- `oracle_confidence` is the highest probability among the three
- Higher confidence = more certain prediction
- Probabilities should sum to ~1.0

### Example Output Row

```csv
entry_time,exit_time,profit,entry_oracle_regime,entry_oracle_confidence,exit_oracle_regime,exit_oracle_confidence,oracle_regime_change
2025-01-15 10:00:00,2025-01-15 14:00:00,2.5,BULL,0.864,BULL,0.892,BULL -> BULL
```

## Analysis Use Cases

### 1. Analyze Trade Performance by Oracle Regime

```python
import pandas as pd

df = pd.read_csv('trades_with_oracle.csv')

# Trades entered during BULL regime
bull_trades = df[df['entry_oracle_regime'] == 'BULL']
print(f"BULL trades: {len(bull_trades)}, Win rate: {(bull_trades['profit'] > 0).mean()*100:.1f}%")

# Trades entered during BEAR regime
bear_trades = df[df['entry_oracle_regime'] == 'BEAR']
print(f"BEAR trades: {len(bear_trades)}, Win rate: {(bear_trades['profit'] > 0).mean()*100:.1f}%")
```

### 2. Find Trades Where Oracle Regime Changed

```python
# Trades where Oracle regime changed during the trade
regime_changes = df[df['oracle_regime_changed'] == True]
print(f"Trades with regime changes: {len(regime_changes)}")
print(regime_changes[['entry_time', 'exit_time', 'profit', 'oracle_regime_change']])
```

### 3. Analyze Confidence Impact

```python
# High confidence trades vs low confidence
high_conf = df[df['entry_oracle_confidence'] > 0.7]
low_conf = df[df['entry_oracle_confidence'] < 0.5]

print(f"High confidence trades: {len(high_conf)}, Avg profit: {high_conf['profit'].mean():.2f}")
print(f"Low confidence trades: {len(low_conf)}, Avg profit: {low_conf['profit'].mean():.2f}")
```

## Troubleshooting

### Error: "Predictions directory not found"

**Solution:** Make sure you've run a backtest with `--freqaimodel` flag and the FreqAI identifier matches your config.

Check your config file:
```json
{
  "freqai": {
    "identifier": "Oracle_Surfer_DryRun"  // <-- This is your freqai-id
  }
}
```

### Error: "No trades found"

**Solution:** Ensure you exported trades using `--export trades` during backtesting.

### Warning: "No Oracle predictions available"

**Solution:** The script will still export trades, but without Oracle data. Check that:
1. Backtest was run with `--freqaimodel XGBoostClassifier`
2. FreqAI identifier is correct
3. Prediction files exist in `user_data/models/{freqai_id}/backtesting_predictions/`

### Trades Missing Oracle Data

**Possible causes:**
- Trade timestamps are outside the Oracle prediction date range
- Oracle predictions weren't generated for that time period
- Timezone mismatch between trades and predictions

The script uses the closest prediction before or at the trade timestamp.

## Notes

- Oracle predictions are matched to the closest timestamp (before or at trade time)
- If no prediction exists before a trade, the first available prediction is used
- Predictions are stored per-candle, so multiple trades may share the same Oracle signal
- The script handles timezone-aware timestamps automatically

## See Also

- `validate_oracle_feather.py` - Validate Oracle predictions independently
- `get_oracle_signal.py` - Get current Oracle signal from live bot logs
- `check_oracle_api.py` - Check Oracle status via API
