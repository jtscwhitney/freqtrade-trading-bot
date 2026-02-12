"""
BollingerRatchet Strategy - GMODS_11 (Mode C Optimization)

THE "HYBRID SNIPER" CONFIGURATION

Logic Pivot:
- Returning to the ONLY profitable core (GMODS_02).
- Solving the Volume issue by expanding valid setups, not by lowering standards.

1. TIMEFRAME: 15m (Profitable Core).
2. SAFETY: Oracle Panic Exit RESTORED (Blind Exit).
   - If Oracle flips, we exit. History shows "Smart Panic" was too slow.
3. VOLUME: Hybrid Entry Logic.
   - Old: Wick Only (low < bb_lower).
   - New: Wick OR Close (low < bb_lower) | (close < bb_lower).
   - Why: Captures both "wicks" (rejections) and "closes" (momentum oversold).
"""

import numpy as np
import pandas as pd
import pandas_ta as ta
from pandas import DataFrame
from freqtrade.strategy import IStrategy, informative
from freqtrade.persistence import Trade
from typing import Optional
import talib.abstract as ta_lib
from datetime import datetime


class BollingerRatchet_GMODS_11(IStrategy):
    """
    BollingerRatchet GMODS_11
    - 15m Timeframe
    - StdDev 2.0 (High Quality)
    - Hybrid Entry (Wick + Close)
    - Blind Panic Exit (Safety)
    """
    
    # ===========================
    # STRATEGY PARAMETERS
    # ===========================
    
    # Uncapped ROI: Swing Trading
    minimal_roi = {
        "0": 100,       
        "240": 0.15,    
        "480": 0.10,    
        "960": 0.05     
    }
    
    stoploss = -0.10
    
    # Trailing Stop - 15m settings
    trailing_stop = True
    trailing_stop_positive = 0.02         
    trailing_stop_positive_offset = 0.03  
    trailing_only_offset_is_reached = True
    
    timeframe = '15m'
    
    process_only_new_candles = True
    startup_candle_count = 600
    
    order_types = {
        'entry': 'market',
        'exit': 'market',
        'stoploss': 'market',
        'stoploss_on_exchange': False
    }
    
    # ===========================
    # INDICATOR PARAMETERS
    # ===========================
    
    # EMA 500
    ema_length = 500 
    
    # Bollinger Bands
    bb_length = 40    
    
    # QUALITY CONTROL: 2.0 (Standard)
    bb_std_dev = 2.0
    
    position_adjustment_enable = True
    
    # ===========================
    # LEVERAGE
    # ===========================
    
    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: Optional[str],
                 side: str, **kwargs) -> float:
        return 2.0
    
    # ===========================
    # INDICATOR POPULATION
    # ===========================
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        
        # Oracle (FreqAI)
        dataframe = self.freqai.start(dataframe, metadata, self)
        
        # Indicators
        dataframe['ema'] = ta_lib.EMA(dataframe, timeperiod=self.ema_length)
        
        bollinger = ta_lib.BBANDS(dataframe, timeperiod=self.bb_length, nbdevup=self.bb_std_dev, nbdevdn=self.bb_std_dev, matype=0)
        dataframe['bb_upper'] = bollinger['upperband']
        dataframe['bb_middle'] = bollinger['middleband']
        dataframe['bb_lower'] = bollinger['lowerband']
        
        return dataframe

    # ===========================
    # FREQAI (Unchanged)
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

    # ===========================
    # ENTRY (Hybrid Sniper)
    # ===========================
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        
        target_col = "&s_regime_class"
        if target_col in dataframe.columns:
            oracle_signal = dataframe[target_col]
        else:
            oracle_signal = pd.Series("NEUTRAL", index=dataframe.index)

        # --- LONG ENTRY ---
        # 1. Trend is UP (Close > EMA)
        # 2. Oracle != BEAR
        # 3. HYBRID TRIGGER: Wick < Band OR Close < Band
        dataframe.loc[
            (
                (dataframe['close'] > dataframe['ema']) &
                (oracle_signal != "BEAR") &
                (
                    (dataframe['low'] < dataframe['bb_lower']) | 
                    (dataframe['close'] < dataframe['bb_lower'])
                )
            ),
            'enter_long'] = 1
        
        # --- SHORT ENTRY ---
        # 1. Trend is DOWN (Close < EMA)
        # 2. Oracle != BULL
        # 3. HYBRID TRIGGER: Wick > Band OR Close > Band
        dataframe.loc[
            (
                (dataframe['close'] < dataframe['ema']) &
                (oracle_signal != "BULL") &
                (
                    (dataframe['high'] > dataframe['bb_upper']) | 
                    (dataframe['close'] > dataframe['bb_upper'])
                )
            ),
            'enter_short'] = 1
            
        return dataframe

    # ===========================
    # EXIT (Blind Panic)
    # ===========================
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        
        # RESTORED Oracle Invalidation.
        # This is the "Safety Valve" that makes 15m viable.
        
        target_col = "&s_regime_class"
        if target_col in dataframe.columns:
            
            # EXIT LONG if Oracle flips to BEAR
            dataframe.loc[
                (dataframe[target_col] == "BEAR"),
                'exit_long'
            ] = 1
            
            # EXIT SHORT if Oracle flips to BULL 
            dataframe.loc[
                (dataframe[target_col] == "BULL"),
                'exit_short'
            ] = 1
            
        return dataframe