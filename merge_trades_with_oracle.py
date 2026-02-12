#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Merge Freqtrade Backtest Trades with Oracle Signals
====================================================
This script merges exported backtest trade data with Oracle (FreqAI) predictions
from feather files, providing a comprehensive view of trade performance alongside
Oracle regime signals and confidence scores.

Usage:
    python merge_trades_with_oracle.py \
        --trades user_data/backtest_results/backtest-result-*.json \
        --freqai-id Oracle_Surfer_DryRun \
        --output trades_with_oracle.csv

Or specify individual files:
    python merge_trades_with_oracle.py \
        --trades-file user_data/backtest_results/backtest-result.json \
        --freqai-id Oracle_Surfer_DryRun \
        --output trades_with_oracle.csv
"""

import pandas as pd
import json
import glob
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List
import sys

def load_trades_from_json(json_file: Path) -> pd.DataFrame:
    """Load trades from Freqtrade backtest JSON export"""
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Freqtrade exports trades in different formats
        trades = []
        
        if isinstance(data, dict):
            # Format 1: Direct trades list
            if 'trades' in data:
                trades = data['trades']
            # Format 2: Nested under strategy.{strategy_name}.trades
            elif 'strategy' in data:
                strategy_data = data['strategy']
                if isinstance(strategy_data, dict):
                    # Find the strategy name key (e.g., "OracleSurfer_v12_PROD")
                    for strategy_name, strategy_info in strategy_data.items():
                        if isinstance(strategy_info, dict) and 'trades' in strategy_info:
                            trades = strategy_info['trades']
                            print(f"[INFO] Found trades under strategy: {strategy_name}")
                            break
            # Format 3: Try to find any list that looks like trades
            if not trades:
                for key, value in data.items():
                    if isinstance(value, dict):
                        # Check if this dict contains trades
                        if 'trades' in value:
                            trades = value['trades']
                            break
                        # Check nested strategy structure
                        for sub_key, sub_value in value.items():
                            if isinstance(sub_value, dict) and 'trades' in sub_value:
                                trades = sub_value['trades']
                                break
                        if trades:
                            break
        elif isinstance(data, list):
            # Format 4: Direct list of trades
            trades = data
        else:
            print(f"[ERROR] Unexpected JSON format in {json_file}")
            return pd.DataFrame()
        
        if not trades:
            print(f"[WARN] No trades found in {json_file}")
            print(f"       JSON structure: {list(data.keys()) if isinstance(data, dict) else 'list'}")
            if isinstance(data, dict) and 'strategy' in data:
                print(f"       Strategy keys: {list(data['strategy'].keys()) if isinstance(data['strategy'], dict) else 'N/A'}")
            return pd.DataFrame()
        
        # Convert to DataFrame
        df = pd.DataFrame(trades)
        
        # Standardize column names (Freqtrade uses different names)
        column_mapping = {
            'open_date': 'entry_time',
            'close_date': 'exit_time',
            'open_timestamp': 'entry_time',
            'close_timestamp': 'exit_time',
            'profit_abs': 'profit',
            'profit_pct': 'profit_pct',
            'is_short': 'is_short',
            'pair': 'pair',
            'stake_amount': 'stake_amount',
            'amount': 'amount',
            'open_rate': 'entry_rate',
            'close_rate': 'exit_rate',
        }
        
        for old_col, new_col in column_mapping.items():
            if old_col in df.columns and new_col not in df.columns:
                df[new_col] = df[old_col]
        
        # Ensure datetime columns
        for time_col in ['entry_time', 'exit_time']:
            if time_col in df.columns:
                df[time_col] = pd.to_datetime(df[time_col], errors='coerce', utc=True)
        
        print(f"[OK] Loaded {len(df)} trades from {json_file.name}")
        return df
        
    except Exception as e:
        print(f"[ERROR] Failed to load {json_file}: {e}")
        return pd.DataFrame()

def load_trades_from_csv(csv_file: Path) -> pd.DataFrame:
    """Load trades from CSV export"""
    try:
        df = pd.read_csv(csv_file)
        
        # Standardize datetime columns
        for time_col in ['entry_time', 'exit_time', 'open_date', 'close_date']:
            if time_col in df.columns:
                df[time_col] = pd.to_datetime(df[time_col], errors='coerce', utc=True)
        
        print(f"[OK] Loaded {len(df)} trades from {csv_file.name}")
        return df
        
    except Exception as e:
        print(f"[ERROR] Failed to load {csv_file}: {e}")
        return pd.DataFrame()

def load_all_predictions(freqai_id: str, pair: str = "BTC") -> pd.DataFrame:
    """Load all Oracle predictions from feather files"""
    predictions_dir = Path(f"user_data/models/{freqai_id}/backtesting_predictions")
    
    if not predictions_dir.exists():
        print(f"[ERROR] Predictions directory not found: {predictions_dir}")
        print(f"       Make sure you've run a backtest with --freqaimodel")
        return pd.DataFrame()
    
    # Find all prediction feather files
    feather_files = sorted(predictions_dir.glob(f"cb_{pair.lower()}_*_prediction.feather"))
    
    if not feather_files:
        print(f"[WARN] No prediction files found in {predictions_dir}")
        print(f"       Pattern: cb_{pair.lower()}_*_prediction.feather")
        return pd.DataFrame()
    
    print(f"[INFO] Found {len(feather_files)} prediction files")
    
    # Load and concatenate all predictions
    all_predictions = []
    for feather_file in feather_files:
        try:
            df = pd.read_feather(feather_file)
            
            # Ensure date column is datetime
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'], errors='coerce', utc=True)
            
            all_predictions.append(df)
        except Exception as e:
            print(f"[WARN] Failed to load {feather_file.name}: {e}")
    
    if not all_predictions:
        print(f"[ERROR] No predictions could be loaded")
        return pd.DataFrame()
    
    # Concatenate all predictions
    combined = pd.concat(all_predictions, ignore_index=True)
    
    # Sort by date
    if 'date' in combined.columns:
        combined = combined.sort_values('date').reset_index(drop=True)
    
    # Remove duplicates (in case of overlap)
    if 'date' in combined.columns:
        combined = combined.drop_duplicates(subset=['date'], keep='last')
    
    print(f"[OK] Loaded {len(combined)} total prediction rows")
    print(f"     Date range: {combined['date'].min()} to {combined['date'].max()}")
    
    return combined

def find_closest_prediction(timestamp: pd.Timestamp, predictions_df: pd.DataFrame) -> Optional[Dict]:
    """Find the closest Oracle prediction to a given timestamp"""
    if predictions_df.empty or 'date' not in predictions_df.columns:
        return None
    
    # Find the closest prediction (before or at the timestamp)
    mask = predictions_df['date'] <= timestamp
    if not mask.any():
        # If no prediction before timestamp, use the first one
        closest_idx = 0
    else:
        closest_idx = predictions_df[mask]['date'].idxmax()
    
    row = predictions_df.loc[closest_idx]
    
    # Extract Oracle data
    oracle_data = {
        'oracle_regime': str(row.get('&s_regime_class', 'UNKNOWN')).upper(),
        'oracle_bear_prob': float(row.get('BEAR', 0.0)),
        'oracle_bull_prob': float(row.get('BULL', 0.0)),
        'oracle_neutral_prob': float(row.get('NEUTRAL', 0.0)),
        'oracle_confidence': max(
            float(row.get('BEAR', 0.0)),
            float(row.get('BULL', 0.0)),
            float(row.get('NEUTRAL', 0.0))
        ),
        'oracle_prediction_time': row.get('date'),
        'oracle_do_predict': bool(row.get('do_predict', 0)),
    }
    
    return oracle_data

def merge_trades_with_oracle(trades_df: pd.DataFrame, predictions_df: pd.DataFrame) -> pd.DataFrame:
    """Merge trades with Oracle predictions"""
    if trades_df.empty:
        print("[ERROR] No trades to merge")
        return pd.DataFrame()
    
    if predictions_df.empty:
        print("[WARN] No Oracle predictions available - trades will be exported without Oracle data")
        return trades_df
    
    merged_rows = []
    
    for idx, trade in trades_df.iterrows():
        merged_trade = trade.to_dict()
        
        # Get Oracle signal at entry
        if 'entry_time' in trade and pd.notna(trade['entry_time']):
            entry_oracle = find_closest_prediction(trade['entry_time'], predictions_df)
            if entry_oracle:
                for key, value in entry_oracle.items():
                    merged_trade[f'entry_{key}'] = value
            else:
                # Fill with None if no prediction found
                for key in ['oracle_regime', 'oracle_bear_prob', 'oracle_bull_prob', 
                           'oracle_neutral_prob', 'oracle_confidence', 'oracle_prediction_time', 'oracle_do_predict']:
                    merged_trade[f'entry_{key}'] = None
        
        # Get Oracle signal at exit
        if 'exit_time' in trade and pd.notna(trade['exit_time']):
            exit_oracle = find_closest_prediction(trade['exit_time'], predictions_df)
            if exit_oracle:
                for key, value in exit_oracle.items():
                    merged_trade[f'exit_{key}'] = value
            else:
                # Fill with None if no prediction found
                for key in ['oracle_regime', 'oracle_bear_prob', 'oracle_bull_prob', 
                           'oracle_neutral_prob', 'oracle_confidence', 'oracle_prediction_time', 'oracle_do_predict']:
                    merged_trade[f'exit_{key}'] = None
        
        # Calculate Oracle regime change during trade
        if entry_oracle and exit_oracle:
            merged_trade['oracle_regime_changed'] = (
                entry_oracle['oracle_regime'] != exit_oracle['oracle_regime']
            )
            merged_trade['oracle_regime_change'] = (
                f"{entry_oracle['oracle_regime']} -> {exit_oracle['oracle_regime']}"
            )
        else:
            merged_trade['oracle_regime_changed'] = None
            merged_trade['oracle_regime_change'] = None
        
        merged_rows.append(merged_trade)
    
    merged_df = pd.DataFrame(merged_rows)
    
    print(f"[OK] Merged {len(merged_df)} trades with Oracle predictions")
    
    return merged_df

def main():
    parser = argparse.ArgumentParser(
        description='Merge Freqtrade backtest trades with Oracle (FreqAI) predictions',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Merge trades from JSON export
  python merge_trades_with_oracle.py \\
      --trades-file user_data/backtest_results/backtest-result.json \\
      --freqai-id Oracle_Surfer_DryRun \\
      --output trades_with_oracle.csv

  # Merge trades from CSV export
  python merge_trades_with_oracle.py \\
      --trades-file user_data/backtest_results/trades.csv \\
      --freqai-id Oracle_Surfer_DryRun \\
      --output trades_with_oracle.csv

  # Auto-detect trade files
  python merge_trades_with_oracle.py \\
      --trades "user_data/backtest_results/*.json" \\
      --freqai-id Oracle_Surfer_DryRun \\
      --output trades_with_oracle.csv
        """
    )
    
    parser.add_argument(
        '--trades-file',
        type=str,
        help='Path to trade export file (JSON or CSV)'
    )
    
    parser.add_argument(
        '--trades',
        type=str,
        help='Glob pattern to find trade files (e.g., "user_data/backtest_results/*.json")'
    )
    
    parser.add_argument(
        '--freqai-id',
        type=str,
        required=True,
        help='FreqAI identifier from config (e.g., "Oracle_Surfer_DryRun", "Regime_Oracle_v7_Futures")'
    )
    
    parser.add_argument(
        '--pair',
        type=str,
        default='BTC',
        help='Trading pair symbol (default: BTC)'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        default='trades_with_oracle.csv',
        help='Output file path (CSV or JSON, default: trades_with_oracle.csv)'
    )
    
    parser.add_argument(
        '--format',
        type=str,
        choices=['csv', 'json', 'both'],
        default='csv',
        help='Output format (default: csv)'
    )
    
    args = parser.parse_args()
    
    # Find trade files
    trade_files = []
    if args.trades_file:
        trade_files = [Path(args.trades_file)]
    elif args.trades:
        trade_files = [Path(f) for f in glob.glob(args.trades)]
    else:
        print("[ERROR] Must specify either --trades-file or --trades")
        parser.print_help()
        sys.exit(1)
    
    if not trade_files:
        print(f"[ERROR] No trade files found")
        sys.exit(1)
    
    print("="*70)
    print("MERGE TRADES WITH ORACLE SIGNALS")
    print("="*70)
    print(f"FreqAI Identifier: {args.freqai_id}")
    print(f"Pair: {args.pair}")
    print(f"Trade Files: {len(trade_files)}")
    print()
    
    # Load trades
    all_trades = []
    for trade_file in trade_files:
        if trade_file.suffix.lower() == '.json':
            trades = load_trades_from_json(trade_file)
        elif trade_file.suffix.lower() == '.csv':
            trades = load_trades_from_csv(trade_file)
        else:
            print(f"[WARN] Unknown file type: {trade_file}, trying JSON...")
            trades = load_trades_from_json(trade_file)
        
        if not trades.empty:
            all_trades.append(trades)
    
    if not all_trades:
        print("[ERROR] No trades could be loaded")
        sys.exit(1)
    
    trades_df = pd.concat(all_trades, ignore_index=True)
    print(f"\n[OK] Total trades loaded: {len(trades_df)}")
    
    # Load Oracle predictions
    print("\n" + "-"*70)
    print("Loading Oracle Predictions...")
    print("-"*70)
    predictions_df = load_all_predictions(args.freqai_id, args.pair)
    
    # Merge
    print("\n" + "-"*70)
    print("Merging Trades with Oracle Signals...")
    print("-"*70)
    merged_df = merge_trades_with_oracle(trades_df, predictions_df)
    
    if merged_df.empty:
        print("[ERROR] Merge failed")
        sys.exit(1)
    
    # Export
    output_path = Path(args.output)
    print("\n" + "-"*70)
    print(f"Exporting Results...")
    print("-"*70)
    
    if args.format in ['csv', 'both']:
        csv_path = output_path.with_suffix('.csv') if args.format == 'both' else output_path
        merged_df.to_csv(csv_path, index=False)
        print(f"[OK] Exported CSV: {csv_path}")
        print(f"     Rows: {len(merged_df)}, Columns: {len(merged_df.columns)}")
    
    if args.format in ['json', 'both']:
        json_path = output_path.with_suffix('.json') if args.format == 'both' else output_path
        merged_df.to_json(json_path, orient='records', date_format='iso', indent=2)
        print(f"[OK] Exported JSON: {json_path}")
    
    # Summary statistics
    print("\n" + "="*70)
    print("SUMMARY STATISTICS")
    print("="*70)
    
    if 'entry_oracle_regime' in merged_df.columns:
        entry_regimes = merged_df['entry_oracle_regime'].value_counts()
        print("\nOracle Regime at Entry:")
        for regime, count in entry_regimes.items():
            pct = (count / len(merged_df)) * 100
            print(f"  {regime}: {count} trades ({pct:.1f}%)")
    
    if 'profit' in merged_df.columns or 'profit_pct' in merged_df.columns:
        profit_col = 'profit_pct' if 'profit_pct' in merged_df.columns else 'profit'
        if profit_col in merged_df.columns:
            total_profit = merged_df[profit_col].sum()
            winning_trades = (merged_df[profit_col] > 0).sum()
            win_rate = (winning_trades / len(merged_df)) * 100 if len(merged_df) > 0 else 0
            print(f"\nTrade Performance:")
            print(f"  Total Profit: {total_profit:.2f}")
            print(f"  Winning Trades: {winning_trades}/{len(merged_df)} ({win_rate:.1f}%)")
    
    if 'oracle_regime_changed' in merged_df.columns:
        regime_changes = merged_df['oracle_regime_changed'].sum()
        print(f"\nOracle Regime Changes During Trades: {regime_changes}/{len(merged_df)}")
    
    print("\n" + "="*70)
    print("DONE!")
    print("="*70)
    print(f"\nOutput file: {output_path}")
    print("\nColumns included:")
    oracle_cols = [col for col in merged_df.columns if 'oracle' in col.lower()]
    for col in oracle_cols[:10]:
        print(f"  - {col}")
    if len(oracle_cols) > 10:
        print(f"  ... and {len(oracle_cols) - 10} more Oracle columns")

if __name__ == "__main__":
    main()
