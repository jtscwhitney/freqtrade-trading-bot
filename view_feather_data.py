#!/usr/bin/env python3
"""
Feather File Viewer for Freqtrade Data
This script allows you to view and analyze your .feather files
"""

import pandas as pd
import numpy as np
from datetime import datetime
import matplotlib.pyplot as plt

def view_feather_file(file_path):
    """View the contents of a feather file"""
    try:
        # Read the feather file
        print(f"📊 Loading feather file: {file_path}")
        df = pd.read_feather(file_path)
        
        print(f"\n✅ Successfully loaded data!")
        print(f"📈 Shape: {df.shape}")
        print(f"📅 Date range: {df['date'].min()} to {df['date'].max()}")
        print(f"💰 Price range: ${df['close'].min():.2f} - ${df['close'].max():.2f}")
        
        # Display first few rows
        print(f"\n📋 First 5 rows:")
        print(df.head())
        
        # Display data info
        print(f"\n🔍 Data info:")
        print(df.info())
        
        # Basic statistics
        print(f"\n📊 Basic statistics:")
        print(df.describe())
        
        return df
        
    except Exception as e:
        print(f"❌ Error loading feather file: {e}")
        return None

def analyze_trading_data(df):
    """Analyze the trading data for insights"""
    if df is None:
        return
    
    print(f"\n🔍 Trading Data Analysis:")
    
    # Calculate daily returns
    df['daily_return'] = df['close'].pct_change()
    
    # Volatility analysis
    volatility = df['daily_return'].std() * np.sqrt(288)  # 288 5-min periods per day
    print(f"📊 Daily Volatility: {volatility:.2%}")
    
    # Volume analysis
    avg_volume = df['volume'].mean()
    print(f"📈 Average Volume: {avg_volume:,.0f}")
    
    # Price trends
    price_change = (df['close'].iloc[-1] - df['close'].iloc[0]) / df['close'].iloc[0]
    print(f"📈 Total Price Change: {price_change:.2%}")
    
    # Time-based analysis
    df['hour'] = df['date'].dt.hour
    hourly_volume = df.groupby('hour')['volume'].mean()
    print(f"\n🕐 Hourly Volume Pattern:")
    print(hourly_volume)

def create_sample_chart(df):
    """Create a simple price chart"""
    if df is None:
        return
    
    try:
        # Create a simple price chart
        plt.figure(figsize=(12, 6))
        plt.plot(df['date'], df['close'], label='BTC/USDT Close Price')
        plt.title('BTC/USDT Price Chart (5-minute intervals)')
        plt.xlabel('Date')
        plt.ylabel('Price (USDT)')
        plt.legend()
        plt.grid(True)
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        # Save the chart
        chart_path = 'btc_price_chart.png'
        plt.savefig(chart_path)
        print(f"\n📊 Chart saved as: {chart_path}")
        
        # Show the chart (if in interactive environment)
        plt.show()
        
    except Exception as e:
        print(f"❌ Error creating chart: {e}")

def main():
    """Main function to view and analyze feather data"""
    print("🚀 Freqtrade Feather File Viewer")
    print("=" * 50)
    
    # Path to your feather file
    feather_file = "user_data/data/kucoin/BTC_USDT-5m.feather"
    
    # Load and view the data
    df = view_feather_file(feather_file)
    
    if df is not None:
        # Analyze the data
        analyze_trading_data(df)
        
        # Create a chart
        create_sample_chart(df)
        
        print(f"\n🎉 Analysis complete!")
        print(f"💡 You can now explore this data in Cursor or use it for strategy development")
        
        # Show sample data for manual inspection
        print(f"\n📋 Sample data for manual inspection:")
        print(df.head(10).to_string())
        
    else:
        print("❌ Could not load feather file. Please check the file path.")

if __name__ == "__main__":
    main()








