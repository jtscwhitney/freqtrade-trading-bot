#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Oracle Validation Script
Runs a backtest and validates that the Oracle is producing changing predictions/probabilities
"""

import subprocess
import re
import json
import sys
from datetime import datetime
from collections import defaultdict

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

def run_backtest():
    """Run Freqtrade backtest and capture output"""
    print("="*70)
    print("RUNNING ORACLE BACKTEST VALIDATION")
    print("="*70)
    print("\nStarting backtest...")
    
    # Use docker-compose run to ensure container is available
    # Use last 14 days of data for validation
    from datetime import datetime, timedelta
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=14)).strftime("%Y%m%d")
    timerange = f"{start_date}-{end_date}"
    
    cmd = [
        "docker-compose", "run", "--rm", "freqtrade",
        "backtesting",
        "--config", "/freqtrade/user_data/config_oracle.json",
        "--strategy", "RegimeValidation",
        "--freqaimodel", "XGBoostClassifier",
        "--timerange", timerange,
        "--userdir", "/freqtrade/user_data",
        "-v"
    ]
    
    try:
        print(f"Timerange: {timerange}")
        print("Running backtest (this may take 1-2 minutes)...")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600, encoding='utf-8', errors='replace')
        print("Backtest completed!")
        print(f"Stdout length: {len(result.stdout)} chars")
        print(f"Stderr length: {len(result.stderr)} chars")
        return result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return None, "Backtest timed out after 10 minutes"
    except Exception as e:
        return None, str(e)

def extract_predictions(log_output):
    """Extract Oracle predictions and probabilities from logs"""
    predictions = []
    
    # Pattern to match: "DEBUG: Found class probabilities: {'BEAR': 0.0149, 'NEUTRAL': 0.0, 'BULL': 0.9851}"
    prob_pattern = r"DEBUG: Found class probabilities: ({.*?})"
    # Also match: "DEBUG: Oracle is attempting to broadcast: BULL with confidence: {'BEAR': 0.0149, ...}"
    broadcast_pattern = r"DEBUG: Oracle is attempting to broadcast: (\w+) with confidence: ({.*?})"
    
    lines = log_output.split('\n')
    print(f"Analyzing {len(lines)} log lines...")
    
    for i, line in enumerate(lines):
        # Look for probability logs
        prob_match = re.search(prob_pattern, line)
        broadcast_match = re.search(broadcast_pattern, line)
        
        if prob_match or broadcast_match:
            try:
                if broadcast_match:
                    regime = broadcast_match.group(1)
                    probs_str = broadcast_match.group(2)
                else:
                    regime = None
                    probs_str = prob_match.group(1)
                
                # Parse probabilities dict safely
                probs_dict = eval(probs_str.replace("'", '"')) if "'" in probs_str else eval(probs_str)
                
                # Try to get timestamp from the line itself or nearby lines
                timestamp = None
                # Check current line first
                ts_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                if ts_match:
                    timestamp = ts_match.group(1)
                else:
                    # Check nearby lines
                    for j in range(max(0, i-5), min(len(lines), i+5)):
                        ts_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', lines[j])
                        if ts_match:
                            timestamp = ts_match.group(1)
                            break
                
                # Determine regime if not already set
                if not regime and probs_dict:
                    regime = max(probs_dict.items(), key=lambda x: x[1])[0]
                
                predictions.append({
                    'timestamp': timestamp or f"Line {i}",
                    'probabilities': probs_dict,
                    'regime': regime
                })
            except Exception as e:
                print(f"Warning: Could not parse prediction at line {i}: {e}")
                pass
    
    print(f"Extracted {len(predictions)} predictions from logs")
    return predictions

def validate_oracle(predictions):
    """Validate that Oracle is working correctly"""
    print("\n" + "="*70)
    print("VALIDATION RESULTS")
    print("="*70)
    
    if not predictions:
        print("[FAIL] No predictions found in logs")
        print("   The Oracle may not be producing predictions correctly.")
        return False
    
    print(f"\n[OK] Found {len(predictions)} predictions")
    
    # Check 1: Probabilities should change over time
    prob_changes = []
    regimes_seen = set()
    
    for i in range(1, len(predictions)):
        prev = predictions[i-1]
        curr = predictions[i]
        
        prev_probs = prev['probabilities']
        curr_probs = curr['probabilities']
        
        # Calculate change in probabilities
        changes = {}
        for key in ['BEAR', 'NEUTRAL', 'BULL']:
            prev_val = prev_probs.get(key, 0.0)
            curr_val = curr_probs.get(key, 0.0)
            delta = abs(curr_val - prev_val)
            if delta > 0.0001:  # Significant change (>0.01%)
                changes[key] = delta
        
        if changes:
            prob_changes.append({
                'from': prev['timestamp'],
                'to': curr['timestamp'],
                'changes': changes
            })
        
        regimes_seen.add(curr['regime'])
    
    # Validation checks
    checks_passed = 0
    total_checks = 4
    
    # Check 1: Has predictions
    if len(predictions) > 0:
        print(f"[OK] Check 1: Oracle produced {len(predictions)} predictions")
        checks_passed += 1
    else:
        print("[FAIL] Check 1: No predictions found")
    
    # Check 2: Probabilities change over time
    if len(prob_changes) > 0:
        print(f"[OK] Check 2: Probabilities changed {len(prob_changes)} times")
        print(f"   (This indicates the model is responding to new data)")
        checks_passed += 1
    else:
        print("[WARN] Check 2: WARNING - Probabilities did not change")
        print("   (This may indicate stale predictions or very stable market)")
    
    # Check 3: Multiple regimes seen
    if len(regimes_seen) > 1:
        print(f"[OK] Check 3: Oracle predicted multiple regimes: {regimes_seen}")
        checks_passed += 1
    else:
        print(f"[WARN] Check 3: Only one regime seen: {regimes_seen}")
        print("   (This is normal if market conditions are stable)")
    
    # Check 4: Probabilities sum to ~1.0
    prob_sums_valid = True
    for pred in predictions[:10]:  # Check first 10
        probs = pred['probabilities']
        total = sum(probs.values())
        if abs(total - 1.0) > 0.1:  # Allow 10% tolerance
            prob_sums_valid = False
            break
    
    if prob_sums_valid:
        print("[OK] Check 4: Probability values are valid (sum to ~1.0)")
        checks_passed += 1
    else:
        print("[FAIL] Check 4: Probability values don't sum to ~1.0")
    
    # Show sample predictions
    print("\n" + "-"*70)
    print("SAMPLE PREDICTIONS (First 5):")
    print("-"*70)
    for i, pred in enumerate(predictions[:5]):
        probs = pred['probabilities']
        regime = pred['regime']
        print(f"{i+1}. {pred['timestamp']}: {regime} | "
              f"BEAR={probs.get('BEAR', 0.0):.4f} "
              f"NEUTRAL={probs.get('NEUTRAL', 0.0):.4f} "
              f"BULL={probs.get('BULL', 0.0):.4f}")
    
    # Show probability changes
    if prob_changes:
        print("\n" + "-"*70)
        print("PROBABILITY CHANGES DETECTED:")
        print("-"*70)
        for change in prob_changes[:5]:  # Show first 5 changes
            changes_str = ", ".join([f"{k}: {v:.6f}" for k, v in change['changes'].items()])
            print(f"{change['from']} -> {change['to']}: {changes_str}")
    
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
    stdout, stderr = run_backtest()
    
    if stdout is None:
        print(f"[FAIL] Backtest failed: {stderr}")
        return
    
    # Extract predictions from logs
    predictions = extract_predictions(stdout + "\n" + stderr)
    
    # Validate
    validate_oracle(predictions)
    
    # Also check for training logs
    if "Done training" in stdout or "Done training" in stderr:
        print("\n[OK] Model training completed successfully")
    else:
        print("\n[WARN] No training completion message found")

if __name__ == "__main__":
    main()
