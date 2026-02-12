"""
OracleSurfer_v10_PROD ("The Sniper")
Production Release
- Architecture: 1h Timeframe / Hybrid Logic
- Key Characteristic: The "All-Weather" Strategy. 
  It is the only version tested that remained profitable in sideways "Chop" markets 
  while capturing parabolic Bull runs via Uncapped RSI.
- Logic:
    1. ENTRY FILTER (Safety): Price > EMA 200.
    2. ENTRY TRIGGER (Aggression): Uncapped RSI (Ignores Overbought signals).
    3. EXIT (Efficiency): Tight Ladder (Start 2.0%, Trail 1.0%).
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

class OracleSurfer_v10_PROD(IStrategy):
    """
    OracleSurfer_v10_PROD
    Hybrid Architecture: v6 Safety Filter + v9 Aggressive Entry + Tight Exit.
    """

    # ===========================
    # 1. CONFIGURATION
    # ===========================
    
    # 1h Timeframe
    timeframe = '1h'
    
    # ROI: UNCAPPED
    # We rely on the Tight Ladder Trailing Stop.
    minimal_roi = {
        "0": 100,       
        "240": 0.1,     
        "480": 0.05,    
    }
    
    # HARD STOP: -5%
    # Standard crash protection.
    stoploss = -0.05
    
    # TRAILING STOP (TIGHT LADDER)
    # Optimized for "Sniping" profits before they evaporate in chop.
    # Start trailing at 2.0%, Trail by 1.0%.
    trailing_stop = True
    trailing_stop_positive = 0.010        # Trail by 1.0%
    trailing_stop_positive_offset = 0.02  # Start trailing after 2.0%
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
    # 2. INDICATORS
    # ===========================
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        
        # 1. ORACLE
        dataframe = self.freqai.start(dataframe, metadata, self)
        
        # 2. TREND (Safety Layer)
        # EMA 200 ensures we don't counter-trade the macro trend.
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
    # 3. ENTRY LOGIC
    # ===========================
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        
        target_col = "&s_regime_class"
        if target_col in dataframe.columns:
            oracle_signal = dataframe[target_col]
        else:
            oracle_signal = pd.Series("NEUTRAL", index=dataframe.index)

        # --- LONG ENTRY ---
        # 1. Oracle BULL
        # 2. Price > EMA 200 (Safety)
        # 3. Uncapped RSI (Aggression: We buy even if RSI > 75)
        # 4. Strong Momentum (MACD > Signal, RSI > 50, ADX > 25)
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
        # 2. Price < EMA 200 (Safety)
        # 3. Uncapped RSI (Aggression: We sell even if RSI < 25)
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
    # 4. EXIT LOGIC
    # ===========================
    
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    # ===========================
    # 5. RISK MANAGEMENT
    # ===========================
    
    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                        current_rate: float, current_profit: float, **kwargs) -> float:
        
        # Quick Break-Even Logic
        # If profit > 1.2%, lock in 0.1%.
        # This is tighter than v6 (1.5%) to survive chop.
        if current_profit > 0.012:
            return 0.001 
        
        return -1

    # ===========================
    # 6. FREQAI BOILERPLATE
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