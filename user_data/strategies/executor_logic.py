import zmq
import ccxt
import time
import json
import pandas as pd
import numpy as np  # Standard math library
from datetime import datetime, timezone

# --- CONFIGURATION ---
ORACLE_ADDRESS = "tcp://127.0.0.1:5555" 
SYMBOL = 'BTC/USDT'
TIMEFRAME = '15m'       
VWMA_LENGTH = 20        
RSI_LENGTH = 14
RSI_OVERSOLD = 40
HEARTBEAT_INTERVAL = 10  # Update display every 10 seconds (matches Oracle broadcast interval)
LOG_FILE = "executor_signals.log"  # File to log broadcasted signals

def connect_to_oracle():
    """Establishes connection to Module A"""
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    socket.connect(ORACLE_ADDRESS)
    socket.subscribe("") 
    # Set socket timeout to detect connection issues
    socket.setsockopt(zmq.RCVTIMEO, 1000)  # 1 second timeout for testing
    print(f"[Module B] Connecting to Oracle at {ORACLE_ADDRESS}...")
    print(f"[Module B] ZMQ Socket created and subscribed to all messages")
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

def get_last_4h_candle_close():
    """Calculate the last 4h candle close time (00:00, 04:00, 08:00, 12:00, 16:00, 20:00 UTC)"""
    try:
        # Get current UTC time
        now_utc = datetime.now(timezone.utc)
        
        # 4h candle boundaries: 00:00, 04:00, 08:00, 12:00, 16:00, 20:00 UTC
        current_hour = now_utc.hour
        
        # Find last 4h boundary (the one we're currently in or just passed)
        boundaries = [0, 4, 8, 12, 16, 20]
        last_hour = None
        
        # Work backwards to find the last boundary
        for boundary in reversed(boundaries):
            if current_hour >= boundary:
                last_hour = boundary
                break
        
        # If we're before 00:00 (shouldn't happen, but handle it)
        if last_hour is None:
            # Use previous day's 20:00
            last_day = now_utc.replace(hour=20, minute=0, second=0, microsecond=0) - pd.Timedelta(days=1)
        else:
            # Set to last boundary, same day
            last_day = now_utc.replace(hour=last_hour, minute=0, second=0, microsecond=0)
            # If we're exactly at a boundary, that's the last one
            # If we're past it, we already have the right one
        
        # Convert to local time
        local_dt = last_day.astimezone()
        return local_dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        # Fallback: return current time
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def get_next_4h_candle_close():
    """Calculate the next 4h candle close time (00:00, 04:00, 08:00, 12:00, 16:00, 20:00 UTC)"""
    try:
        # Get current UTC time
        now_utc = datetime.now(timezone.utc)
        
        # 4h candle boundaries: 00:00, 04:00, 08:00, 12:00, 16:00, 20:00 UTC
        current_hour = now_utc.hour
        
        # Find next 4h boundary
        boundaries = [0, 4, 8, 12, 16, 20]
        next_hour = None
        
        for boundary in boundaries:
            if current_hour < boundary:
                next_hour = boundary
                break
        
        # If we're past 20:00, next candle is 00:00 next day
        if next_hour is None:
            next_day = now_utc.replace(hour=0, minute=0, second=0, microsecond=0) + pd.Timedelta(days=1)
        else:
            # Set to next boundary, same day
            next_day = now_utc.replace(hour=next_hour, minute=0, second=0, microsecond=0)
            # If we're exactly at a boundary (or past it), use next boundary
            if next_day <= now_utc:
                # Find the next boundary after this one
                boundary_idx = boundaries.index(next_hour)
                if boundary_idx < len(boundaries) - 1:
                    next_hour = boundaries[boundary_idx + 1]
                    next_day = now_utc.replace(hour=next_hour, minute=0, second=0, microsecond=0)
                else:
                    # Past 20:00, next is 00:00 next day
                    next_day = now_utc.replace(hour=0, minute=0, second=0, microsecond=0) + pd.Timedelta(days=1)
        
        # Convert to local time
        local_dt = next_day.astimezone()
        return local_dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        # Fallback: return current time + 4 hours
        return (datetime.now() + pd.Timedelta(hours=4)).strftime("%Y-%m-%d %H:%M:%S")

def log_signal(timestamp, regime, signal, price=None, vwma=None, rsi=None, oracle_update_time=None, confidence=None):
    """Logs the broadcasted signal to a file (appends to preserve history)"""
    try:
        log_entry = f"[{timestamp}] Regime: {regime:8s} | Signal: {signal:35s}"
        if price is not None:
            log_entry += f" | Price: ${price:,.2f}"
        if vwma is not None:
            log_entry += f" | VWMA: ${vwma:,.2f}"
        if rsi is not None:
            log_entry += f" | RSI: {rsi:5.1f}"
        if confidence:
            # Format confidence as BEAR:0.0149 NEUTRAL:0.0000 BULL:0.9851
            conf_str = f"BEAR:{confidence.get('BEAR', 0.0):.4f} NEUTRAL:{confidence.get('NEUTRAL', 0.0):.4f} BULL:{confidence.get('BULL', 0.0):.4f}"
            log_entry += f" | Confidence: {conf_str}"
        if oracle_update_time:
            log_entry += f" | Oracle: {oracle_update_time}"
        log_entry += "\n"
        
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(log_entry)
    except Exception as e:
        print(f"Logging Error: {e}")  # Don't crash on logging errors

def main():
    socket = connect_to_oracle()
    exchange = ccxt.binance()
    print("-------------------------------------------------")
    print(f"[Module B] SNIPER ACTIVE - Watching {SYMBOL}")
    print("-------------------------------------------------")
    
    current_regime = "WAITING_FOR_ORACLE"
    last_oracle_update = None  # Last broadcast time
    last_message_time = None  # Timestamp of last received message (for detecting disconnection)
    last_confidence = {"BEAR": 0.0, "NEUTRAL": 0.0, "BULL": 0.0}
    update_count = 0
    ORACLE_TIMEOUT_SECONDS = 30  # Consider Oracle disconnected if no messages for 30 seconds

    while True:
        try:
            # 1. READ ORACLE (Check for new messages - non-blocking)
            oracle_updated = False
            try:
                # Try to read multiple messages if available (Oracle broadcasts frequently)
                while True:
                    msg = socket.recv_json(flags=zmq.NOBLOCK)
                    if isinstance(msg, dict) and 'type' in msg and msg['type'] == 'REGIME_SIGNAL':
                        # CRITICAL FIX: Oracle now sends string labels: "BEAR", "NEUTRAL", "BULL", "TRAINING"
                        # Ensure we normalize to uppercase for consistent comparison
                        new_regime = str(msg.get('regime', 'TRAINING')).upper()
                        oracle_timestamp_str = msg.get('timestamp', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                        # Convert Oracle timestamp (assumed UTC from Docker) to local time
                        try:
                            # Parse the Oracle timestamp format: "YYYY-MM-DD HH:MM:SS"
                            # Assume it's UTC (Docker containers use UTC by default)
                            oracle_dt = datetime.strptime(oracle_timestamp_str, "%Y-%m-%d %H:%M:%S")
                            oracle_dt = oracle_dt.replace(tzinfo=timezone.utc)  # Mark as UTC
                            # Convert to local time
                            local_dt = oracle_dt.astimezone()
                            broadcast_time = local_dt.strftime("%H:%M:%S")
                        except Exception:
                            # Fallback to original if parsing fails
                            broadcast_time = oracle_timestamp_str[-8:] if len(oracle_timestamp_str) >= 8 else oracle_timestamp_str
                        
                        # Track regime change
                        if new_regime != current_regime:
                            current_regime = new_regime
                            oracle_updated = True
                        
                        # Always update broadcast time (BC)
                        last_oracle_update = broadcast_time
                        last_message_time = datetime.now()  # Track when we last received a message
                        # Extract confidence values if available
                        if 'confidence' in msg and isinstance(msg['confidence'], dict):
                            last_confidence = {
                                "BEAR": float(msg['confidence'].get('BEAR', 0.0)),
                                "NEUTRAL": float(msg['confidence'].get('NEUTRAL', 0.0)),
                                "BULL": float(msg['confidence'].get('BULL', 0.0))
                            }
                        update_count += 1
            except zmq.Again:
                pass  # No more messages available

            # 2. ANALYZE MARKET
            df = get_market_data(exchange)
            latest = calculate_indicators(df)
            
            if latest is not None:
                price = latest['close']
                vwma = latest['vwma']
                rsi = latest['rsi']
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # 3. DECISION LOGIC
                # CRITICAL FIX: Explicit handling of string-based regime signals from Oracle
                # Oracle sends: "BEAR", "NEUTRAL", "BULL", or "TRAINING" (all uppercase strings)
                signal = "WAIT"
                current_regime_upper = current_regime.upper()  # Normalize to uppercase
                
                if current_regime_upper == "BULL":
                    # Bullish regime: Look for entry opportunities
                    if price < vwma and rsi < RSI_OVERSOLD:
                        signal = "Look For Long"
                    elif price < vwma:
                        signal = "Price < VWMA (RSI Over)"
                    else:
                        signal = "Price And RSI Over"
                elif current_regime_upper == "TRAINING":
                    # Model is still training - use same logic as BULL but be cautious
                    if price < vwma and rsi < RSI_OVERSOLD:
                        signal = "Training Mode"
                    elif price < vwma:
                        signal = "Training Mode"
                    else:
                        signal = "Training Mode"
                elif current_regime_upper == "NEUTRAL":
                    # Neutral regime: Wait for clearer signal
                    signal = "Wait While Neutral"
                elif current_regime_upper == "BEAR":
                    # Bearish regime: Stay out
                    signal = "Poss Short Entry"
                else:
                    # Unknown regime - default to waiting
                    signal = f"WAITING (Unknown regime: {current_regime})"
                
                # 4. DISPLAY HEARTBEAT (Every ~5 seconds)
                # Show Oracle update prominently if regime changed
                if oracle_updated:
                    print(f"\n{'='*70}")
                    conf_display = f"BEAR:{last_confidence['BEAR']:.4f} NEUTRAL:{last_confidence['NEUTRAL']:.4f} BULL:{last_confidence['BULL']:.4f}"
                    print(f">>> ORACLE UPDATE [{last_oracle_update}]: Regime changed to {current_regime} (Pair: {SYMBOL}) <<<")
                    print(f">>> Confidence: {conf_display} <<<")
                    print(f"{'='*70}")
                
                # Display status line with heartbeat indicator
                # Get the highest confidence value for the current regime (default to 0.0 if not available)
                regime_conf = last_confidence.get(current_regime, 0.0)
                
                # Check if Oracle appears to be disconnected (no messages for timeout period)
                oracle_disconnected = False
                if last_message_time:
                    time_since_last_message = (datetime.now() - last_message_time).total_seconds()
                    if time_since_last_message > ORACLE_TIMEOUT_SECONDS:
                        oracle_disconnected = True
                
                if oracle_disconnected:
                    # Oracle has stopped broadcasting - show disconnected status
                    seconds_ago = int((datetime.now() - last_message_time).total_seconds())
                    oracle_status = f"⚠️  ORACLE DISCONNECTED (Last message {seconds_ago}s ago)"
                    # Optionally reset regime to indicate stale data
                    # current_regime = "STALE_DATA"
                elif last_oracle_update:
                    # Format Oracle status with proper spacing
                    # Calculate last and next 4h candle close times
                    last_candle_close = get_last_4h_candle_close()
                    next_candle_close = get_next_4h_candle_close()
                    # Extract time portion (HH:MM:SS) from the datetime strings
                    last_candle_time = last_candle_close[-8:] if len(last_candle_close) >= 8 else last_candle_close
                    next_update_time = next_candle_close[-8:] if len(next_candle_close) >= 8 else next_candle_close
                    # Build status string with BC (Broadcast), LU (Last Update - last candle close), and NU (Next Update)
                    oracle_status = f"LB: {last_oracle_update:9s} | LC: {last_candle_time:9s} | NC: {next_update_time:9s}"
                else:
                    # No updates received - Oracle may be waiting for new 4h candle
                    oracle_status = f"⚠️  No messages yet (Oracle broadcasts every 10s)"
                
                #heartbeat_line = f"[{timestamp}] 💓 Regime: {current_regime:8s} | Price: ${price:,.2f} | VWMA: ${vwma:,.2f} | RSI: {rsi:5.1f} | {signal:35s} | Oracle: {oracle_status}"
                heartbeat_line = f"[{timestamp}] Trend: {current_regime:8s} | Conf: {regime_conf:.4f} | {signal:35s} | Oracle: {oracle_status}"
                # Print on new line (append instead of overwrite)
                print(heartbeat_line, flush=True)
                
                # 5. LOG TO FILE (Append each heartbeat to preserve history)
                log_signal(timestamp, current_regime, signal, price, vwma, rsi, last_oracle_update, last_confidence)
            
            time.sleep(HEARTBEAT_INTERVAL) 

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()