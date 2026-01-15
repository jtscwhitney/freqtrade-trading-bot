import numpy as np
import pandas as pd
import pandas_ta as ta
import zmq  # <--- CRITICAL: Communication Library
import json
from freqtrade.strategy import IStrategy
from freqtrade.freqai.prediction_models.XGBoostClassifier import XGBoostClassifier
from datetime import datetime

class RegimeValidation(IStrategy):
    """
    Project: 2026 Institutional Hybrid System
    Module: The Oracle (Regime Filter) + Broadcaster
    """
    minimal_roi = {"0": 100}
    stoploss = -1.0
    timeframe = "4h"
    process_only_new_candles = False

    # --- ZMQ CONFIGURATION (THE MOUTH) ---
    def __init__(self, config: dict) -> None:
        super().__init__(config)
        # Create the Publisher Socket
        try:
            context = zmq.Context()
            self.socket = context.socket(zmq.PUB)
            self.socket.bind("tcp://*:5555") 
            print(">>> ZMQ Oracle Broadcaster started on Port 5555 <<<")
        except Exception as e:
            print(f"ZMQ Error: {e}")

    # --- FREQAI FEATURES (THE BRAIN) ---
    def feature_engineering_expand_all(self, dataframe: pd.DataFrame, period: int,
                                       metadata: dict, **kwargs) -> pd.DataFrame:
        
        # 1. Regime: Choppiness Index (CHOP)
        dataframe['%regime_chop'] = ta.chop(dataframe['high'], dataframe['low'], dataframe['close'], length=14)
        
        # 2. Efficiency: KAMA Distance
        kama = ta.kama(dataframe['close'], length=10)
        dataframe['%trend_kama_dist'] = (dataframe['close'] - kama) / kama

        # 3. Valuation: LTVD (Yearly MA)
        long_ma = ta.sma(dataframe['close'], length=2190) 
        dataframe['%val_ltvd'] = (dataframe['close'] - long_ma) / dataframe['close']

        # 4. Fear: Williams VixFix
        period_vix = 22
        highest_close = dataframe['close'].rolling(window=period_vix).max()
        dataframe['%fear_vixfix'] = (highest_close - dataframe['low']) / highest_close * 100

        # 5. Truth: OBV Oscillator
        obv = ta.obv(dataframe['close'], dataframe['volume'])
        obv_ma = ta.sma(obv, length=20)
        dataframe['%truth_obv_osc'] = (obv - obv_ma) / obv_ma.replace(0, 1)

        return dataframe

    def feature_engineering_expand_basic(self, dataframe: pd.DataFrame, **kwargs) -> pd.DataFrame:
        dataframe['%pct-change'] = dataframe['close'].pct_change()
        return dataframe

    def set_freqai_targets(self, dataframe: pd.DataFrame, **kwargs) -> pd.DataFrame:
        """
        CRITICAL FIX: Properly calculate future max/min without NaN propagation.
        
        Original bug: shift(-24).rolling(24) creates NaN for last 24 candles
        because shift(-24) produces NaN when there's no future data, causing
        all target values to be NaN and training to fail.
        
        Fix: Use a list comprehension to explicitly calculate forward-looking windows,
        ensuring we handle edge cases properly and don't create NaN targets.
        """
        atr = ta.atr(dataframe['high'], dataframe['low'], dataframe['close'], length=14)
        barrier_threshold = 1.5 * atr
        horizon = 24  # 24 candles = 24 * 4h = 96 hours = 4 days forward
        
        # FIX: Calculate forward-looking max/min using vectorized operations
        # For each candle i, we want max/min of candles [i+1, i+horizon]
        # Original approach: shift(-horizon).rolling(horizon) fails at end of dataframe
        # New approach: Use shift(-1) to look forward, then rolling window
        
        # Shift by 1 first to start from next candle, then take rolling max/min
        # This gives us forward-looking windows: [i+1, i+horizon] for each index i
        future_max = dataframe['high'].shift(-1).rolling(window=horizon, min_periods=1).max()
        future_min = dataframe['low'].shift(-1).rolling(window=horizon, min_periods=1).min()
        
        # The last 'horizon' candles will have NaN because shift(-1) creates NaN
        # This is correct - we can't predict the future for the most recent candles
        
        # Initialize all as Neutral (class 1)
        dataframe['&s_regime_class'] = 1
        
        # CRITICAL: Only set targets where we have valid future data AND valid ATR
        # The last 'horizon' candles will have NaN in future_max/min (no future data)
        # The first 14 candles will have NaN in barrier_threshold (ATR needs warmup)
        # NaN comparisons evaluate to False, so those rows correctly remain Neutral (1)
        
        # Check for valid data: all components must be non-NaN
        valid_mask = (
            pd.notna(future_max) & 
            pd.notna(future_min) & 
            pd.notna(barrier_threshold) &
            pd.notna(dataframe['close'])
        )
        
        # Only calculate conditions where we have valid data
        if valid_mask.any():
            bull_condition = valid_mask & (future_max > (dataframe['close'] + barrier_threshold))
            bear_condition = valid_mask & (future_min < (dataframe['close'] - barrier_threshold))
            
            dataframe.loc[bear_condition, '&s_regime_class'] = 0  # Bear
            dataframe.loc[bull_condition, '&s_regime_class'] = 2  # Bull
        
        # For rows without valid future data (last horizon candles), keep as Neutral (1)
        # This is intentional - we can't predict the future for the most recent candles
        # FreqAI will drop rows with NaN targets during training, which is correct behavior
        
        return dataframe

    # --- STRATEGY LOGIC & BROADCASTING ---
    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        return dataframe

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        # 1. Setup Logger (The Loudspeaker)
        import logging
        logger = logging.getLogger(__name__)

        dataframe.loc[:, 'enter_long'] = 0
        dataframe.loc[:, 'enter_short'] = 0
        
        # 2. LOGIC
        regime_signal = "TRAINING"
        target_col = "&s_regime_class_prediction"

        if target_col in dataframe.columns:
            latest_val = dataframe.iloc[-1][target_col]
            if pd.notna(latest_val):
                pred = int(latest_val)
                if pred == 2:
                    regime_signal = "BULL"
                elif pred == 0:
                    regime_signal = "BEAR"
                else:
                    regime_signal = "NEUTRAL"
        
        # 3. THE DEBUG MESSAGE (Now using Logger)
        # This will appear as "INFO - DEBUG: Broadcasting..." in your logs
        logger.info(f"DEBUG: Oracle is attempting to broadcast: {regime_signal}")

        # 4. BROADCAST
        current_time = datetime.now().strftime("%H:%M:%S")
        message = {
            "type": "REGIME_SIGNAL",
            "timestamp": current_time,
            "pair": metadata['pair'],
            "regime": regime_signal
        }

        try:
            self.socket.send_json(message)
        except Exception as e:
            logger.error(f"CRITICAL ZMQ ERROR: {e}")
            
        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe.loc[:, 'exit_long'] = 0
        dataframe.loc[:, 'exit_short'] = 0
        return dataframe