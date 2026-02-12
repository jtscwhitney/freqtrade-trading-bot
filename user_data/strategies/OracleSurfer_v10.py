"""
OracleSurfer_v10 ("The Sniper")
- The Synthesis of v6, v8, and v9.
- LOGIC:
    1. ENTRY FILTER (Safety): EMA 200 (From v6).
       - Critical for surviving Bear Markets (Test 01).
    2. MOMENTUM (Aggression): Uncapped RSI (From v9).
       - Critical for capturing Parabolic Runs (Bull Market).
       - Safe to use because EMA 200 protects us from "Bear Rallies".
    3. EXIT (Efficiency): Tight Ladder (From v9).
       - Start Trailing at 2.0%, Trail by 1.0%.
       - Maximizes profit capture and minimizes chop losses.
"""

import numpy as np
import pandas as pd
import pandas_ta as ta
from pandas import DataFrame
from freqtrade.strategy import IStrategy
from freqtrade.persistence import Trade
from typing import Optional
import talib.abstract as ta_lib
from datetime import datetime

class OracleSurfer_v10(IStrategy):
    """
    OracleSurfer_v10
    Hybrid Architecture: v6 Safety + v9 Efficiency.
    """

    # ===========================
    # STRATEGY PARAMETERS
    # ===========================
    
    timeframe = '1h'
    
    # ROI: UNCAPPED
    minimal_roi = {
        "0": 100,       
        "240": 0.1,     
        "480": 0.05,    
    }
    
    # HARD STOP: -5%
    stoploss = -0.05
    
    # TRAILING STOP (TIGHT / v9 Logic)
    # Start at 2.0%, Trail by 1.0%.
    trailing_stop = True
    trailing_stop_positive = 0.010        
    trailing_stop_positive_offset = 0.02  
    trailing_only_offset_is_reached = True
    
    process_only_new_candles = True
    startup_candle_count = 240
    
    can_short = True
    
    # Enable Custom Stoploss for Break-Even Logic
    use_custom_stoploss = True

    order_types = {
        'entry': 'market',
        'exit': 'market',
        'stoploss': 'market',
        'stoploss_on_exchange': False
    }

    # ===========================
    # INDICATORS
    # ===========================
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        
        # 1. ORACLE
        dataframe = self.freqai.start(dataframe, metadata, self)
        
        # 2. TREND (v6 Logic - The Iron Shield)
        dataframe['ema_200'] = ta_lib.EMA(dataframe, timeperiod=200)
        
        # 3. MOMENTUM
        dataframe['rsi'] = ta_lib.RSI(dataframe, timeperiod=14)
        
        macd = ta_lib.MACD(dataframe)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        
        # 4. STRENGTH
        dataframe['adx'] = ta_lib.ADX(dataframe)
        
        return dataframe

    # ===========================
    # ENTRY LOGIC (HYBRID)
    # ===========================
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        
        target_col = "&s_regime_class"
        if target_col in dataframe.columns:
            oracle_signal = dataframe[target_col]
        else:
            oracle_signal = pd.Series("NEUTRAL", index=dataframe.index)

        # --- LONG ENTRY ---
        # 1. Oracle BULL
        # 2. Price > EMA 200 (v6 Safety)
        # 3. No RSI Cap (v9 Aggression)
        dataframe.loc[
            (
                (oracle_signal == "BULL") &
                (dataframe['close'] > dataframe['ema_200']) & 
                (dataframe['rsi'] > 50) & 
                (dataframe['macd'] > dataframe['macdsignal']) &
                (dataframe['adx'] > 25)
            ),
            'enter_long'] = 1
        
        # --- SHORT ENTRY ---
        # 1. Oracle BEAR
        # 2. Price < EMA 200 (v6 Safety)
        # 3. No RSI Floor (v9 Aggression)
        dataframe.loc[
            (
                (oracle_signal == "BEAR") &
                (dataframe['close'] < dataframe['ema_200']) &
                (dataframe['rsi'] < 50) & 
                (dataframe['macd'] < dataframe['macdsignal']) &
                (dataframe['adx'] > 25)
            ),
            'enter_short'] = 1
            
        return dataframe

    # ===========================
    # EXIT LOGIC
    # ===========================
    
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    # ===========================
    # CUSTOM STOPLOSS (v9 Logic)
    # ===========================
    
    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                        current_rate: float, current_profit: float, **kwargs) -> float:
        
        # Break-Even at 1.2% profit
        if current_profit > 0.012:
            return 0.001 
        
        return -1

    # ===========================
    # FREQAI BOILERPLATE
    # ===========================
    def feature_engineering_expand_all(self, dataframe: DataFrame, period: int, metadata: dict, **kwargs) -> DataFrame:
        if metadata.get('tf', '') != '4h': return dataframe
        dataframe['%regime_chop'] = ta.chop(dataframe['high'], dataframe['low'], dataframe['close'], length=14)
        kama = ta.kama(dataframe['close'], length=10)
        dataframe['%trend_kama_dist'] = (dataframe['close'] - kama) / kama
        long_ma = ta.sma(dataframe['close'], length=200)
        dataframe['%val_ltvd'] = (dataframe['close'] - long_ma) / dataframe['close']
        period_vix = 22
        highest_close = dataframe['close'].rolling(window=period_vix).max()
        dataframe['%fear_vixfix'] = (highest_close - dataframe['low']) / highest_close * 100
        obv = ta.obv(dataframe['close'], dataframe['volume'])
        obv_ma = ta.sma(obv, length=20)
        dataframe['%truth_obv_osc'] = (obv - obv_ma) / obv_ma
        return dataframe.fillna(0)

    def feature_engineering_expand_basic(self, dataframe: DataFrame, **kwargs) -> DataFrame:
        metadata = kwargs.get('metadata', {})
        if metadata.get('tf', '') != '4h': return dataframe
        dataframe['%pct-change'] = dataframe['close'].pct_change().fillna(0)
        return dataframe

    def set_freqai_targets(self, dataframe: DataFrame, **kwargs) -> DataFrame:
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