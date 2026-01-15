import zmq
import ccxt
import time
import json
import pandas as pd
import numpy as np  # Standard math library
from datetime import datetime

# --- CONFIGURATION ---
ORACLE_ADDRESS = "tcp://127.0.0.1:5555" 
SYMBOL = 'BTC/USDT'
TIMEFRAME = '15m'       
VWMA_LENGTH = 20        
RSI_LENGTH = 14
RSI_OVERSOLD = 40

def connect_to_oracle():
    """Establishes connection to Module A"""
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    socket.connect(ORACLE_ADDRESS)
    socket.subscribe("") 
    print(f"[Module B] Connecting to Oracle at {ORACLE_ADDRESS}...")
    return socket

def get_market_data(exchange):
    """Fetches the latest 15m candle"""
    try:
        bars = exchange.fetch_ohlcv(SYMBOL, timeframe=TIMEFRAME, limit=100)
        df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    except Exception as e:
        print(f"Data Error: {e}")
        return pd.DataFrame()

# --- CUSTOM INDICATORS (No External Libs Needed) ---
def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_indicators(df):
    """Adds Sniper indicators using standard Pandas"""
    if df.empty: return None
    
    # 1. VWMA (Volume Weighted Moving Average)
    pv = df['close'] * df['volume']
    vwma = pv.rolling(window=VWMA_LENGTH).sum() / df['volume'].rolling(window=VWMA_LENGTH).sum()
    df['vwma'] = vwma
    
    # 2. RSI (Relative Strength Index)
    # We use a simple calculation to avoid 'pandas_ta' dependency issues
    delta = df['close'].diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ma_up = up.ewm(com=RSI_LENGTH - 1, adjust=True, min_periods=RSI_LENGTH).mean()
    ma_down = down.ewm(com=RSI_LENGTH - 1, adjust=True, min_periods=RSI_LENGTH).mean()
    rs = ma_up / ma_down
    df['rsi'] = 100 - (100 / (1 + rs))
    
    return df.iloc[-1]

def main():
    socket = connect_to_oracle()
    exchange = ccxt.binance()
    print("-------------------------------------------------")
    print(f"[Module B] SNIPER ACTIVE - Watching {SYMBOL}")
    print("-------------------------------------------------")
    
    current_regime = "WAITING_FOR_ORACLE"

    while True:
        try:
            # 1. READ ORACLE
            try:
                msg = socket.recv_json(flags=zmq.NOBLOCK)
                if isinstance(msg, dict) and 'type' in msg and msg['type'] == 'REGIME_SIGNAL':
                    current_regime = msg['regime']
                    print(f"\n>>> ORACLE UPDATE: Regime is now {current_regime} <<<\n")
            except zmq.Again:
                pass 

            # 2. ANALYZE MARKET
            df = get_market_data(exchange)
            latest = calculate_indicators(df)
            
            if latest is not None:
                price = latest['close']
                vwma = latest['vwma']
                rsi = latest['rsi']
                timestamp = datetime.now().strftime("%H:%M:%S")

                # 3. DECISION LOGIC
                signal = "WAIT"
                if "BULL" in current_regime or "TRAINING" in current_regime:
                    if price < vwma and rsi < RSI_OVERSOLD:
                        signal = ">>> SNIPER ENTRY <<<"
                    elif price < vwma:
                         signal = "Price Cheap (Wait for RSI)"
                else:
                    signal = "SLEEPING (Oracle says Bear)"
                
                print(f"\r[{timestamp}] Regime: {current_regime} | Price: {price:.2f} | VWMA: {vwma:.2f} | RSI: {rsi:.1f} | {signal}", end="")
            
            time.sleep(10) 

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()