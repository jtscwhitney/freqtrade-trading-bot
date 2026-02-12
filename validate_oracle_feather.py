#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Oracle Validation Script - Reads actual backtest prediction files
This is more accurate than parsing logs because it reads the actual predictions FreqAI made
"""

import pandas as pd
import glob
import os
from pathlib import Path

def find_backtest_predictions():
    """Find all backtest prediction feather files"""
    predictions_dir = Path("user_data/models/Regime_Oracle_v5/backtesting_predictions")
    
    if not predictions_dir.exists():
        print(f"[FAIL] Predictions directory not found: {predictions_dir}")
        return []
    
    feather_files = list(predictions_dir.glob("*.feather"))
    print(f"Found {len(feather_files)} prediction files")
    return sorted(feather_files)

def analyze_predictions(feather_files):
    """Analyze predictions from feather files"""
    all_predictions = []
    
    for feather_file in feather_files[-10:]:  # Analyze last 10 files (most recent)
        try:
            df = pd.read_feather(feather_file)
            
            # Check what columns are available
            if 'BEAR' in df.columns and 'BULL' in df.columns:
                # Get the latest row (most recent prediction)
                latest = df.iloc[-1]
                
                bear_prob = float(latest.get('BEAR', 0.0))
                bull_prob = float(latest.get('BULL', 0.0))
                neutral_prob = float(latest.get('NEUTRAL', 0.0)) if 'NEUTRAL' in df.columns else 0.0
                
                # Get regime from prediction column or probabilities
                regime_col = latest.get('&s_regime_class', None)
                if pd.isna(regime_col) or regime_col is None:
                    # Determine from probabilities
                    probs = {'BEAR': bear_prob, 'NEUTRAL': neutral_prob, 'BULL': bull_prob}
                    regime = max(probs.items(), key=lambda x: x[1])[0] if any(probs.values()) else None
                else:
                    regime = str(regime_col).upper()
                
                # Get timestamp
                timestamp = None
                if 'date' in df.columns:
                    timestamp = str(df.iloc[-1]['date'])
                
                all_predictions.append({
                    'file': feather_file.name,
                    'timestamp': timestamp,
                    'regime': regime,
                    'probabilities': {
                        'BEAR': bear_prob,
                        'NEUTRAL': neutral_prob,
                        'BULL': bull_prob
                    },
                    'do_predict': float(latest.get('do_predict', 0.0)) if 'do_predict' in df.columns else None
                })
        except Exception as e:
            print(f"Warning: Could not read {feather_file.name}: {e}")
    
    return all_predictions

def validate_oracle(predictions):
    """Validate Oracle predictions"""
    print("\n" + "="*70)
    print("ORACLE VALIDATION RESULTS")
    print("="*70)
    
    if not predictions:
        print("[FAIL] No predictions found in feather files")
        return False
    
    print(f"\n[OK] Found {len(predictions)} predictions from backtest files")
    
    # Validation checks
    checks_passed = 0
    total_checks = 4
    
    # Check 1: Has predictions
    if len(predictions) > 0:
        print(f"[OK] Check 1: Found {len(predictions)} predictions")
        checks_passed += 1
    
    # Check 2: Probabilities change over time
    prob_changes = []
    for i in range(1, len(predictions)):
        prev = predictions[i-1]['probabilities']
        curr = predictions[i]['probabilities']
        
        for key in ['BEAR', 'NEUTRAL', 'BULL']:
            delta = abs(curr.get(key, 0.0) - prev.get(key, 0.0))
            if delta > 0.0001:
                prob_changes.append({
                    'from': predictions[i-1]['file'],
                    'to': predictions[i]['file'],
                    'key': key,
                    'delta': delta
                })
    
    if len(prob_changes) > 0:
        print(f"[OK] Check 2: Probabilities changed {len(prob_changes)} times")
        checks_passed += 1
    else:
        print("[WARN] Check 2: Probabilities did not change")
        print("   (This may indicate very stable market or model not updating)")
    
    # Check 3: Multiple regimes seen
    regimes_seen = set([p['regime'] for p in predictions if p['regime']])
    if len(regimes_seen) > 1:
        print(f"[OK] Check 3: Multiple regimes seen: {regimes_seen}")
        checks_passed += 1
    else:
        print(f"[WARN] Check 3: Only one regime seen: {regimes_seen}")
    
    # Check 4: Probabilities are valid (non-zero and sum to ~1.0)
    valid_probs = 0
    for pred in predictions:
        probs = pred['probabilities']
        total = sum(probs.values())
        has_nonzero = any(v > 0.001 for v in probs.values())
        
        if has_nonzero and 0.9 <= total <= 1.1:  # Allow 10% tolerance
            valid_probs += 1
    
    if valid_probs > len(predictions) * 0.5:  # At least 50% should be valid
        print(f"[OK] Check 4: {valid_probs}/{len(predictions)} predictions have valid probabilities")
        checks_passed += 1
    else:
        print(f"[FAIL] Check 4: Only {valid_probs}/{len(predictions)} predictions have valid probabilities")
        print("   (Probabilities should sum to ~1.0 and be non-zero)")
    
    # Show sample predictions
    print("\n" + "-"*70)
    print("SAMPLE PREDICTIONS (Last 5):")
    print("-"*70)
    for i, pred in enumerate(predictions[-5:]):
        probs = pred['probabilities']
        regime = pred['regime'] or 'UNKNOWN'
        do_predict = pred.get('do_predict', 'N/A')
        print(f"{i+1}. {pred['file']}: {regime} | "
              f"BEAR={probs['BEAR']:.6f} "
              f"NEUTRAL={probs['NEUTRAL']:.6f} "
              f"BULL={probs['BULL']:.6f} | "
              f"do_predict={do_predict}")
    
    # Show probability changes
    if prob_changes:
        print("\n" + "-"*70)
        print("PROBABILITY CHANGES DETECTED:")
        print("-"*70)
        for change in prob_changes[:10]:
            print(f"{change['from']} -> {change['to']}: {change['key']} changed by {change['delta']:.6f}")
    
    # Final verdict
    print("\n" + "="*70)
    if checks_passed >= 3:
        print(f"[PASS] VALIDATION PASSED ({checks_passed}/{total_checks} checks passed)")
        print("   Oracle appears to be functioning correctly!")
    else:
        print(f"[WARN] VALIDATION WARNINGS ({checks_passed}/{total_checks} checks passed)")
        print("   Review the results above for potential issues.")
    print("="*70)
    
    return checks_passed >= 3

def main():
    print("="*70)
    print("ORACLE VALIDATION - READING BACKTEST PREDICTION FILES")
    print("="*70)
    
    # Find prediction files
    feather_files = find_backtest_predictions()
    
    if not feather_files:
        print("\n[INFO] No prediction files found. Running a backtest first...")
        print("Run: docker-compose run --rm freqtrade backtesting --config /freqtrade/user_data/config_oracle.json --strategy RegimeValidation --freqaimodel XGBoostClassifier --timerange 20260110-20260116 --userdir /freqtrade/user_data -v")
        return
    
    # Analyze predictions
    predictions = analyze_predictions(feather_files)
    
    # Validate
    validate_oracle(predictions)

if __name__ == "__main__":
    main()
