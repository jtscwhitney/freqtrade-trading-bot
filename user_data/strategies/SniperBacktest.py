import numpy as np
import pandas as pd
import pandas_ta as ta
from freqtrade.strategy import IStrategy
from freqtrade.freqai.prediction_models.XGBoostClassifier import XGBoostClassifier

class SniperBacktest(IStrategy):
    """
    Project: Phase B - The Sniper Verification
    Description: 
        - Runs the Oracle (FreqAI) on 4h candles to determine REGIME.
        - Runs the Sniper (Indicators) on 15m candles to determine ENTRY.
        - TRADES only when Oracle says BULL/BEAR and Sniper says BUY/SELL.
    """
    # 1. Give trades room to breathe. Don't sell until +6% profit, 
    #    or +3% if held for 2 hours.
    minimal_roi = {
        "0": 0.10,    # Aim for 10% moonshots
        "60": 0.05,   # Accept 5% if it takes an hour
        "120": 0.02   # Accept 2% if it's stuck for 2 hours
    }

    # 2. Tighten the hard stop, but enable TRAILING.
    # This locks in profit as the price goes up.
    stoploss = -0.05  # 5% Hard Stop (Emergency only)
    
    trailing_stop = True
    trailing_stop_positive = 0.015       # Trail behind price by 1.5%
    trailing_stop_positive_offset = 0.025 # Only start trailing once we are 2.5% in profit
    trailing_only_offset_is_reached = True
    timeframe = "15m" # SNIPER SPEED
    
    # FreqAI needs this to be True to handle the 4h projection correctly
    process_only_new_candles = True
    startup_candle_count = 200

    # --- 1. THE SNIPER INDICATORS (15m) ---
    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        # A. Run FreqAI (The Oracle) 
        # This triggers the feature_engineering functions below automatically
        dataframe = self.freqai.start(dataframe, metadata, self)

        # B. Calculate Sniper Indicators (VWMA + RSI) on 15m
        # VWMA (Volume Weighted Moving Average)
        pv = dataframe['close'] * dataframe['volume']
        vwma = pv.rolling(window=20).sum() / dataframe['volume'].rolling(window=20).sum()
        dataframe['vwma'] = vwma

        # RSI (Relative Strength Index)
        dataframe['rsi'] = ta.rsi(dataframe['close'], length=14)

        return dataframe

    # --- 2. THE ORACLE BRAIN (4h) ---
    # We must ensure we ONLY generate features for the 4h timeframe.
    
    def feature_engineering_expand_all(self, dataframe: pd.DataFrame, period: int,
                                       metadata: dict, **kwargs) -> pd.DataFrame:
        # --- GATEKEEPER ---
        # The Oracle model was trained ONLY on '4h' data. 
        # It creates columns like '%regime_chop_..._4h'.
        # If we let this run on '15m', it creates '%regime_chop_..._15m'.
        # The model will see these extra 15m columns and CRASH.
        # So, we return immediately if the timeframe is not 4h.
        if metadata.get('tf', '') != '4h':
            return dataframe

        # 1. Regime: Choppiness Index
        dataframe['%regime_chop'] = ta.chop(dataframe['high'], dataframe['low'], dataframe['close'], length=14)
        
        # 2. Efficiency: KAMA Distance
        kama = ta.kama(dataframe['close'], length=10)
        dataframe['%trend_kama_dist'] = (dataframe['close'] - kama) / kama
        
        # 3. Valuation: LTVD (Long-term MA)
        long_ma = ta.sma(dataframe['close'], length=200) 
        dataframe['%val_ltvd'] = (dataframe['close'] - long_ma) / dataframe['close']
        
        # 4. Fear: Williams VixFix
        period_vix = 22
        highest_close = dataframe['close'].rolling(window=period_vix).max()
        dataframe['%fear_vixfix'] = (highest_close - dataframe['low']) / highest_close * 100
        
        # 5. Truth: OBV Oscillator
        obv = ta.obv(dataframe['close'], dataframe['volume'])
        obv_ma = ta.sma(obv, length=20)
        dataframe['%truth_obv_osc'] = (obv - obv_ma) / obv_ma
        
        # Fill NaNs
        return dataframe.fillna(0)

    def feature_engineering_expand_basic(self, dataframe: pd.DataFrame, **kwargs) -> pd.DataFrame:
        # --- GATEKEEPER ---
        # Also protect the basic expansion (pct-change)
        # We need metadata to check timeframe, but this signature often doesn't have it by default
        # in some versions, but we can check columns or rely on FreqAI context.
        # Safer approach: Check if we are handling the Oracle's timeframe implicitly.
        # Actually, 'metadata' IS passed to this function in newer Freqtrade versions.
        # We will retrieve it from kwargs if not explicit.
        
        metadata = kwargs.get('metadata', {})
        if metadata.get('tf', '') != '4h':
            return dataframe

        dataframe['%pct-change'] = dataframe['close'].pct_change().fillna(0)
        return dataframe

    def set_freqai_targets(self, dataframe: pd.DataFrame, **kwargs) -> pd.DataFrame:
        # IDENTICAL Target Logic to Oracle
        self.freqai.class_names = ["BEAR", "NEUTRAL", "BULL"]
        horizon = 24
        dataframe['atr'] = ta.atr(dataframe['high'], dataframe['low'], dataframe['close'], length=14)
        barrier_threshold = dataframe['atr'] * 2.0 

        future_max = dataframe['high'].shift(-1).rolling(window=horizon, min_periods=1).max()
        future_min = dataframe['low'].shift(-1).rolling(window=horizon, min_periods=1).min()

        dataframe['&s_regime_class'] = "NEUTRAL"
        
        valid_mask = (pd.notna(future_max) & pd.notna(future_min) & pd.notna(barrier_threshold))
        bull_condition = valid_mask & (future_max > (dataframe['close'] + barrier_threshold))
        bear_condition = valid_mask & (future_min < (dataframe['close'] - barrier_threshold))

        dataframe.loc[bear_condition, '&s_regime_class'] = "BEAR"
        dataframe.loc[bull_condition, '&s_regime_class'] = "BULL"

        return dataframe

    # --- 3. THE EXECUTION LOGIC (Merges Oracle + Sniper) ---
    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        
        # 1. READ THE ORACLE
        target_col = "&s_regime_class"
        if target_col in dataframe.columns:
            oracle_signal = dataframe[target_col]
        else:
            return dataframe

        # 2. DEFINE SNIPER CONDITIONS (THE FLIP)
        
        # OLD LOGIC: Buy when price < VWMA (Pullback)
        # NEW LOGIC: Buy when price CROSSES ABOVE VWMA (Momentum Breakout)
        # This catches the start of the move, not the dip.
        
        # We need the previous candle's close to detect a cross
        dataframe['close_shifted'] = dataframe['close'].shift(1)
        
        # Breakout Condition: Price crossed above VWMA
        sniper_breakout = (
            (dataframe['close'] > dataframe['vwma']) & 
            (dataframe['close_shifted'] < dataframe['vwma'])
        )

        # RSI Filter: Ensure we aren't buying the absolute top (RSI < 70)
        sniper_safe_rsi = (dataframe['rsi'] < 70)

        # 3. COMBINE THEM
        # ENTER LONG if:
        # A. Oracle says "BULL"
        # B. Sniper says "Momentum Breakout"
        dataframe.loc[
            (oracle_signal == "BULL") &
            (sniper_breakout) &
            (sniper_safe_rsi),
            'enter_long'] = 1

        # ENTER SHORT if:
        # A. Oracle says "BEAR"
        # B. Price CROSSES BELOW VWMA
        dataframe.loc[
            (oracle_signal == "BEAR") &
            (dataframe['close'] < dataframe['vwma']) &
            (dataframe['close_shifted'] > dataframe['vwma']),
            'enter_short'] = 1
            
        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        # Simple Exit: RSI Reversion
        # Exit LONG if RSI > 70
        dataframe.loc[
            (dataframe['rsi'] > 70),
            'exit_long'] = 1
            
        # Exit SHORT if RSI < 30
        dataframe.loc[
            (dataframe['rsi'] < 30),
            'exit_short'] = 1
            
        return dataframe