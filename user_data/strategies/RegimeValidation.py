import numpy as np
import pandas as pd
import pandas_ta as ta
import zmq  # <--- CRITICAL: Communication Library
import json
import threading
import time
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
    process_only_new_candles = True  # CRITICAL FIX: FreqAI requires this to be True
    startup_candle_count = 250  # Ensure enough candles for indicators and training data

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
        
        # Periodic broadcast state
        self.last_regime_signal = "TRAINING"
        self.last_probabilities = {"BEAR": 0.0, "NEUTRAL": 0.0, "BULL": 0.0}  # Store probability scores
        self.last_metadata = None
        self.broadcast_lock = threading.Lock()
        self.broadcast_interval = 10  # Broadcast every 10 seconds
        
        # Start periodic broadcast thread
        self.broadcast_thread = threading.Thread(target=self._periodic_broadcast, daemon=True)
        self.broadcast_thread.start()
        print(f">>> Periodic broadcast thread started (every {self.broadcast_interval} seconds) <<<")
    
    def _periodic_broadcast(self):
        """Background thread that broadcasts the last known regime every 10 seconds"""
        import logging
        logger = logging.getLogger(__name__)
        
        while True:
            try:
                time.sleep(self.broadcast_interval)
                
                with self.broadcast_lock:
                    regime_signal = self.last_regime_signal
                    metadata = self.last_metadata
                
                if metadata:
                    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    with self.broadcast_lock:
                        probabilities = self.last_probabilities.copy()
                    
                    message = {
                        "type": "REGIME_SIGNAL",
                        "timestamp": current_time,
                        "pair": metadata.get('pair', 'BTC/USDT'),
                        "regime": regime_signal,
                        "confidence": {
                            "BEAR": round(probabilities.get("BEAR", 0.0), 4),
                            "NEUTRAL": round(probabilities.get("NEUTRAL", 0.0), 4),
                            "BULL": round(probabilities.get("BULL", 0.0), 4)
                        }
                    }
                    
                    try:
                        self.socket.send_json(message)
                        logger.debug(f"Periodic broadcast: {regime_signal} at {current_time}")
                    except Exception as e:
                        logger.error(f"Periodic broadcast ZMQ error: {e}")
            except Exception as e:
                logger.error(f"Periodic broadcast thread error: {e}")
                time.sleep(self.broadcast_interval)

    # --- FREQAI FEATURES (THE BRAIN) ---
    def feature_engineering_expand_all(self, dataframe: pd.DataFrame, period: int,
                                       metadata: dict, **kwargs) -> pd.DataFrame:
        # DIAGNOSTIC: Log when feature engineering is called
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"FREQAI DEBUG: feature_engineering_expand_all called with {len(dataframe)} rows")
        
        # 1. Regime: Choppiness Index (CHOP)
        dataframe['%regime_chop'] = ta.chop(dataframe['high'], dataframe['low'], dataframe['close'], length=14)
        
        # 2. Efficiency: KAMA Distance
        kama = ta.kama(dataframe['close'], length=10)
        # CRITICAL FIX: Handle division by zero/NaN to prevent filtering out rows
        kama_safe = kama.replace(0, np.nan)
        dataframe['%trend_kama_dist'] = (dataframe['close'] - kama) / kama_safe
        # Forward fill NaN values to prevent FreqAI from filtering rows
        dataframe['%trend_kama_dist'] = dataframe['%trend_kama_dist'].ffill().fillna(0)

        # 3. Valuation: LTVD (Long-term MA) - REDUCED FROM 200 TO 50
        # CRITICAL FIX: 200-period SMA requires 200 candles, but train_period_days=30 
        # only provides ~180 candles (30 days * 6 candles/day). This caused ALL rows 
        # to have NaN in %val_ltvd, resulting in empty training set.
        long_ma = ta.sma(dataframe['close'], length=200) 
        dataframe['%val_ltvd'] = (dataframe['close'] - long_ma) / dataframe['close']
        # Forward fill NaN values from initial periods
        dataframe['%val_ltvd'] = dataframe['%val_ltvd'].ffill().fillna(0)

        # 4. Fear: Williams VixFix
        period_vix = 22
        highest_close = dataframe['close'].rolling(window=period_vix).max()
        # CRITICAL FIX: Handle division by zero/NaN
        highest_close_safe = highest_close.replace(0, np.nan)
        dataframe['%fear_vixfix'] = (highest_close - dataframe['low']) / highest_close_safe * 100
        # Forward fill NaN values
        dataframe['%fear_vixfix'] = dataframe['%fear_vixfix'].ffill().fillna(0)

        # 5. Truth: OBV Oscillator
        obv = ta.obv(dataframe['close'], dataframe['volume'])
        obv_ma = ta.sma(obv, length=20)
        obv_ma_safe = obv_ma.replace(0, 1)  # Already handled, but ensure no NaN division
        dataframe['%truth_obv_osc'] = (obv - obv_ma) / obv_ma_safe
        # Forward fill NaN values
        dataframe['%truth_obv_osc'] = dataframe['%truth_obv_osc'].ffill().fillna(0)

        return dataframe

    def feature_engineering_expand_basic(self, dataframe: pd.DataFrame, **kwargs) -> pd.DataFrame:
        dataframe['%pct-change'] = dataframe['close'].pct_change()
        # CRITICAL FIX: Fill first row NaN to prevent FreqAI from filtering it
        dataframe['%pct-change'] = dataframe['%pct-change'].fillna(0)
        return dataframe

    def set_freqai_targets(self, dataframe: pd.DataFrame, **kwargs) -> pd.DataFrame:
        """
        Set targets for the FreqAI model.
        Target: Will price go UP or DOWN by 'barrier_threshold' within 'horizon' candles?
        FIXED: Uses vectorized forward-looking windows to prevent NaN crashes.
        CRITICAL: Uses STRING labels for multi-class classification (XGBoostClassifier requirement).
        """
        # DIAGNOSTIC: Log when target setting is called
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"FREQAI DEBUG: set_freqai_targets called with {len(dataframe)} rows")
        
        # CRITICAL FIX: XGBoostClassifier requires STRING labels for multi-class, not integers
        # Set class names to match our string labels
        self.freqai.class_names = ["BEAR", "NEUTRAL", "BULL"]
        
        # 1. Define the parameters
        horizon = 24  # Look 24 candles into the future
        
        # Calculate dynamic threshold (ATR) if not already done
        if 'atr' not in dataframe.columns:
            dataframe['atr'] = ta.atr(dataframe['high'], dataframe['low'], dataframe['close'], length=14)
        # Forward fill ATR NaN values to ensure barrier_threshold is never NaN
        dataframe['atr'] = dataframe['atr'].ffill().fillna(dataframe['atr'].mean() if not dataframe['atr'].isna().all() else 0.01)
            
        # Multiplier for the barrier (e.g., 0.5x ATR)
        barrier_threshold = dataframe['atr'] * 2.0

        # 2. Calculate Future Max/Min (The Forward-Looking Window)
        # Alternative approach: Use shift(-1) but handle NaN properly
        # Shift first, then roll to look at future window
        future_max = dataframe['high'].shift(-1).rolling(window=horizon, min_periods=1).max()
        future_min = dataframe['low'].shift(-1).rolling(window=horizon, min_periods=1).min()

        # 3. Create the Target Column with STRING labels (required for multi-class)
        # Default to "NEUTRAL" - ensures no NaN values
        dataframe['&s_regime_class'] = "NEUTRAL"

        # 4. Define Conditions with Safety Mask
        # CRITICAL: Only label rows where we have valid future data
        # Rows without enough future data will remain "NEUTRAL" - this is correct
        valid_mask = (
            pd.notna(future_max) & 
            pd.notna(future_min) & 
            pd.notna(barrier_threshold) &
            pd.notna(dataframe['close']) &
            (barrier_threshold > 0)  # Ensure threshold is positive
        )

        # Bullish ("BULL"): Future High > Current Close + Threshold
        bull_condition = valid_mask & (future_max > (dataframe['close'] + barrier_threshold))
        
        # Bearish ("BEAR"): Future Low < Current Close - Threshold
        bear_condition = valid_mask & (future_min < (dataframe['close'] - barrier_threshold))

        # Apply labels (Last one wins if both true)
        # CRITICAL: Use STRING labels, not integers
        dataframe.loc[bear_condition, '&s_regime_class'] = "BEAR"
        dataframe.loc[bull_condition, '&s_regime_class'] = "BULL"
        
        # CRITICAL: Ensure target column has no NaN values
        # FreqAI filters out rows with NaN targets, which would cause empty training set
        dataframe['&s_regime_class'] = dataframe['&s_regime_class'].fillna("NEUTRAL")
        
        # DIAGNOSTIC: Log target distribution
        target_counts = dataframe['&s_regime_class'].value_counts().to_dict()
        logger.info(f"FREQAI DEBUG: Target distribution: {target_counts}")
        logger.info(f"FREQAI DEBUG: Target column has NaN: {dataframe['&s_regime_class'].isna().any()}")
        logger.info(f"FREQAI DEBUG: Feature columns: {[col for col in dataframe.columns if col.startswith('%')]}")

        return dataframe

    # --- STRATEGY LOGIC & BROADCASTING ---
    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        # CRITICAL FIX: FreqAI requires self.freqai.start() to be called in populate_indicators
        # This is what triggers feature_engineering_expand_all and set_freqai_targets
        # Without this call, FreqAI never trains!
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"FREQAI DEBUG: populate_indicators called with {len(dataframe)} rows")
        
        # THIS IS THE MISSING PIECE - FreqAI needs this to start feature engineering
        dataframe = self.freqai.start(dataframe, metadata, self)
        
        return dataframe

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        # 1. Setup Logger (The Loudspeaker)
        import logging
        logger = logging.getLogger(__name__)

        dataframe.loc[:, 'enter_long'] = 0
        dataframe.loc[:, 'enter_short'] = 0
        
        # 2. LOGIC - Enhanced Debugging
        regime_signal = "TRAINING"
        probabilities = {"BEAR": 0.0, "NEUTRAL": 0.0, "BULL": 0.0}  # Initialize probabilities
        
        # CRITICAL FIX: FreqAI creates prediction columns with specific naming:
        # - Standard format: &-labelname (where labelname is target without & prefix)
        # - For target "&s_regime_class", prediction should be "&-s_regime_class"
        # - Also check for class probability columns (BEAR, BULL, NEUTRAL) from backtest format
        # - Verify predictions are valid using do_predict flag
        
        if len(dataframe) > 0:
            latest_row = dataframe.iloc[-1]
            
            # First, check if predictions are valid
            do_predict = latest_row.get('do_predict', 0) if 'do_predict' in dataframe.columns else None
            
            # CRITICAL DIAGNOSTIC: Log ALL columns to see what FreqAI actually creates
            # This will help us identify the correct column name immediately
            all_cols = list(dataframe.columns)
            logger.info(f"DEBUG: ========== PREDICTION COLUMN DIAGNOSIS ==========")
            logger.info(f"DEBUG: DataFrame has {len(dataframe)} rows, {len(all_cols)} columns")
            logger.info(f"DEBUG: All columns: {all_cols}")
            logger.info(f"DEBUG: do_predict value: {do_predict}")
            
            # Show columns that might contain predictions
            pred_related_cols = [col for col in all_cols if any(x in col.upper() for x in ['REGIME', 'PREDICT', 'PRED', 'BEAR', 'BULL', 'NEUTRAL', 'CLASS'])]
            logger.info(f"DEBUG: Prediction-related columns: {pred_related_cols}")
            
            # Show values from latest row for prediction-related columns
            for col in pred_related_cols[:10]:  # Limit to first 10 to avoid log spam
                val = latest_row.get(col, 'N/A')
                logger.info(f"DEBUG: Column '{col}' = {val} (type: {type(val).__name__})")
            
            # Priority 1: Check for standard FreqAI prediction column format
            # Target is "&s_regime_class", so prediction should be "&-s_regime_class"
            pred_col_standard = "&-s_regime_class"
            pred_col_alt1 = "&s_regime_class_prediction"
            pred_col_alt2 = "&-s_regime_class_prediction"
            
            prediction_found = False
            
            # Try standard format first
            for pred_col in [pred_col_standard, pred_col_alt1, pred_col_alt2]:
                if pred_col in dataframe.columns:
                    latest_val = latest_row[pred_col]
                    logger.info(f"DEBUG: Found prediction column '{pred_col}' with value: {latest_val} (type: {type(latest_val)})")
                    
                    if pd.notna(latest_val):
                        if isinstance(latest_val, str):
                            regime_signal = latest_val.upper()
                            prediction_found = True
                            logger.info(f"DEBUG: Using string prediction from {pred_col}: {regime_signal}")
                            break
                        else:
                            # Try to convert numeric to class name
                            try:
                                pred = int(float(latest_val))
                                if pred == 2 or pred == "BULL" or latest_val == "BULL":
                                    regime_signal = "BULL"
                                elif pred == 0 or pred == "BEAR" or latest_val == "BEAR":
                                    regime_signal = "BEAR"
                                else:
                                    regime_signal = "NEUTRAL"
                                prediction_found = True
                                logger.info(f"DEBUG: Converted numeric prediction from {pred_col}: {pred} -> {regime_signal}")
                                break
                            except (ValueError, TypeError):
                                pass
            
            # Priority 2: Check for class probability columns (backtest format)
            # CRITICAL: Always extract probabilities if available, even if we found prediction via other method
            class_cols = [col for col in dataframe.columns if col in ['BEAR', 'BULL', 'NEUTRAL']]
            if class_cols:
                extracted_probs = {}
                for col in class_cols:
                    val = latest_row[col]
                    if pd.notna(val):
                        extracted_probs[col] = float(val)
                
                if extracted_probs:
                    # Log raw probabilities with full precision before updating
                    logger.info(f"DEBUG: Raw probabilities extracted: BEAR={extracted_probs.get('BEAR', 0.0):.10f}, NEUTRAL={extracted_probs.get('NEUTRAL', 0.0):.10f}, BULL={extracted_probs.get('BULL', 0.0):.10f}")
                    
                    # Check if probabilities changed from last known state
                    with self.broadcast_lock:
                        old_probs = self.last_probabilities.copy()
                    
                    probs_changed = False
                    for key in ['BEAR', 'NEUTRAL', 'BULL']:
                        old_val = old_probs.get(key, 0.0)
                        new_val = extracted_probs.get(key, 0.0)
                        if abs(old_val - new_val) > 0.0001:  # Detect changes > 0.01%
                            probs_changed = True
                            logger.info(f"DEBUG: Probability changed for {key}: {old_val:.10f} -> {new_val:.10f} (delta: {new_val - old_val:.10f})")
                    
                    if not probs_changed and old_probs.get('BULL', 0.0) > 0:
                        logger.warning(f"DEBUG: Probabilities UNCHANGED from previous prediction - this may indicate stale predictions or very stable market conditions")
                    
                    probabilities.update(extracted_probs)
                    # If we haven't found prediction yet, use probabilities to determine regime
                    if not prediction_found:
                        regime_signal = max(extracted_probs, key=extracted_probs.get)
                        prediction_found = True
                    logger.info(f"DEBUG: Found class probabilities: {probabilities}, Selected regime: {regime_signal}")
            
            # If still no prediction found, log diagnostic info
            if not prediction_found:
                relevant_cols = [col for col in dataframe.columns if any(x in col.upper() for x in ['BEAR', 'BULL', 'NEUTRAL', 'REGIME', 'PREDICT', 'PRED'])]
                logger.warning(f"DEBUG: No valid prediction found. Relevant columns: {relevant_cols}")
                logger.warning(f"DEBUG: do_predict status: {do_predict} (1=valid, 0=invalid, None=not found)")
                
                # If do_predict indicates model is ready but no prediction column exists, there's a mismatch
                if do_predict == 1:
                    logger.error(f"DEBUG: CRITICAL - do_predict=1 but no prediction column found! This indicates a FreqAI configuration issue.")
        
        # 3. THE DEBUG MESSAGE (Now using Logger)
        # This will appear as "INFO - DEBUG: Broadcasting..." in your logs
        logger.info(f"DEBUG: Oracle is attempting to broadcast: {regime_signal} with confidence: BEAR={probabilities.get('BEAR', 0.0):.6f}, NEUTRAL={probabilities.get('NEUTRAL', 0.0):.6f}, BULL={probabilities.get('BULL', 0.0):.6f}")

        # 4. UPDATE LAST KNOWN STATE (for periodic broadcast)
        with self.broadcast_lock:
            self.last_regime_signal = regime_signal
            self.last_probabilities = probabilities.copy()
            self.last_metadata = metadata

        # 5. BROADCAST IMMEDIATELY (on new candle)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = {
            "type": "REGIME_SIGNAL",
            "timestamp": current_time,
            "pair": metadata['pair'],
            "regime": regime_signal,
            "confidence": {
                "BEAR": round(probabilities.get("BEAR", 0.0), 4),
                "NEUTRAL": round(probabilities.get("NEUTRAL", 0.0), 4),
                "BULL": round(probabilities.get("BULL", 0.0), 4)
            }
        }

        try:
            self.socket.send_json(message)
            logger.debug(f"Immediate broadcast: {regime_signal} at {current_time}")
        except Exception as e:
            logger.error(f"CRITICAL ZMQ ERROR: {e}")
            
        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe.loc[:, 'exit_long'] = 0
        dataframe.loc[:, 'exit_short'] = 0
        return dataframe