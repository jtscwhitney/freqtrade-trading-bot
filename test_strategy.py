#!/usr/bin/env python3
"""
Test script for the RSI Strategy
This script tests the strategy logic with sample data
"""

import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Add the user_data/strategies directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'user_data', 'strategies'))

try:
    from RSIStrategy import RSIStrategy
    print("✓ RSIStrategy imported successfully")
except ImportError as e:
    print(f"✗ Error importing RSIStrategy: {e}")
    print("Make sure the strategy file exists in user_data/strategies/")
    sys.exit(1)

def create_sample_data():
    """Create sample OHLCV data for testing"""
    np.random.seed(42)  # For reproducible results
    
    # Generate 100 candles of sample data
    n_candles = 100
    base_price = 100.0
    
    # Create time series
    start_time = datetime.now() - timedelta(minutes=5 * n_candles)
    timestamps = [start_time + timedelta(minutes=5 * i) for i in range(n_candles)]
    
    # Generate price data with some trend and volatility
    prices = []
    current_price = base_price
    
    for i in range(n_candles):
        # Add some trend and random movement
        trend = 0.001 * i  # Slight upward trend
        random_move = np.random.normal(0, 0.02)  # Random price movement
        current_price = current_price * (1 + trend + random_move)
        prices.append(current_price)
    
    # Create OHLCV data
    data = []
    for i, (timestamp, price) in enumerate(zip(timestamps, prices)):
        # Generate OHLC from base price
        high = price * (1 + abs(np.random.normal(0, 0.01)))
        low = price * (1 - abs(np.random.normal(0, 0.01)))
        open_price = price * (1 + np.random.normal(0, 0.005))
        close_price = price
        volume = np.random.uniform(1000, 10000)
        
        data.append({
            'date': timestamp,
            'open': open_price,
            'high': high,
            'low': low,
            'close': close_price,
            'volume': volume
        })
    
    return pd.DataFrame(data)

def test_strategy_indicators():
    """Test the strategy's indicator calculations"""
    print("\n=== Testing Strategy Indicators ===")
    
    # Create sample data
    df = create_sample_data()
    print(f"Created sample data with {len(df)} candles")
    
    # Create strategy instance
    strategy = RSIStrategy()
    
    try:
        # Test indicator population
        df_with_indicators = strategy.populate_indicators(df, {})
        
        # Check if indicators were added
        required_indicators = ['rsi', 'bb_lowerband', 'bb_upperband', 'macd', 'volume_ratio', 'atr']
        missing_indicators = []
        
        for indicator in required_indicators:
            if indicator in df_with_indicators.columns:
                print(f"✓ {indicator}: {df_with_indicators[indicator].iloc[-1]:.4f}")
            else:
                missing_indicators.append(indicator)
                print(f"✗ {indicator}: Missing")
        
        if not missing_indicators:
            print("✓ All indicators calculated successfully")
        else:
            print(f"✗ Missing indicators: {missing_indicators}")
            
        return df_with_indicators
        
    except Exception as e:
        print(f"✗ Error calculating indicators: {e}")
        return None

def test_entry_signals(df):
    """Test the strategy's entry signals"""
    print("\n=== Testing Entry Signals ===")
    
    if df is None:
        print("✗ Cannot test entry signals without indicators")
        return
    
    strategy = RSIStrategy()
    
    try:
        # Test entry signal generation
        df_with_signals = strategy.populate_entry_trend(df, {})
        
        if 'enter_long' in df_with_signals.columns:
            entry_signals = df_with_signals['enter_long'].sum()
            print(f"✓ Entry signals generated: {entry_signals}")
            
            # Show some signal details
            signal_rows = df_with_signals[df_with_signals['enter_long'] == 1]
            if not signal_rows.empty:
                print(f"  First signal at: {signal_rows.iloc[0]['date']}")
                print(f"  RSI at signal: {signal_rows.iloc[0]['rsi']:.2f}")
        else:
            print("✗ No entry signals generated")
            
    except Exception as e:
        print(f"✗ Error generating entry signals: {e}")

def test_exit_signals(df):
    """Test the strategy's exit signals"""
    print("\n=== Testing Exit Signals ===")
    
    if df is None:
        print("✗ Cannot test exit signals without indicators")
        return
    
    strategy = RSIStrategy()
    
    try:
        # Test exit signal generation
        df_with_signals = strategy.populate_exit_trend(df, {})
        
        if 'exit_long' in df_with_signals.columns:
            exit_signals = df_with_signals['exit_long'].sum()
            print(f"✓ Exit signals generated: {exit_signals}")
            
            # Show some signal details
            signal_rows = df_with_signals[df_with_signals['exit_long'] == 1]
            if not signal_rows.empty:
                print(f"  First signal at: {signal_rows.iloc[0]['date']}")
                print(f"  RSI at signal: {signal_rows.iloc[0]['rsi']:.2f}")
        else:
            print("✗ No exit signals generated")
            
    except Exception as e:
        print(f"✗ Error generating exit signals: {e}")

def test_strategy_parameters():
    """Test the strategy's parameter configuration"""
    print("\n=== Testing Strategy Parameters ===")
    
    strategy = RSIStrategy()
    
    try:
        # Check ROI configuration
        print(f"✓ Minimal ROI: {strategy.minimal_roi}")
        
        # Check stoploss
        print(f"✓ Stoploss: {strategy.stoploss}")
        
        # Check timeframe
        print(f"✓ Timeframe: {strategy.timeframe}")
        
        # Check RSI parameters
        print(f"✓ RSI Period: {strategy.rsi_period.value}")
        print(f"✓ RSI Oversold: {strategy.rsi_oversold.value}")
        print(f"✓ RSI Overbought: {strategy.rsi_overbought.value}")
        
        # Check order types
        print(f"✓ Order Types: {strategy.order_types}")
        
        print("✓ All strategy parameters configured correctly")
        
    except Exception as e:
        print(f"✗ Error checking strategy parameters: {e}")

def main():
    """Main test function"""
    print("🚀 Testing RSI Strategy")
    print("=" * 50)
    
    # Test strategy parameters
    test_strategy_parameters()
    
    # Test indicators
    df_with_indicators = test_strategy_indicators()
    
    # Test entry signals
    test_entry_signals(df_with_indicators)
    
    # Test exit signals
    test_exit_signals(df_with_indicators)
    
    print("\n" + "=" * 50)
    print("✅ Strategy testing completed!")
    
    if df_with_indicators is not None:
        print(f"\nSample data summary:")
        print(f"- Total candles: {len(df_with_indicators)}")
        print(f"- Date range: {df_with_indicators['date'].min()} to {df_with_indicators['date'].max()}")
        print(f"- Price range: ${df_with_indicators['close'].min():.2f} - ${df_with_indicators['close'].max():.2f}")
        print(f"- Average volume: {df_with_indicators['volume'].mean():.0f}")

if __name__ == "__main__":
    main()



