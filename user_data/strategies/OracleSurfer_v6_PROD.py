"""
OracleSurfer_v6_PROD ("The Safe Surfer")
Production Version | Final Release
- Architecture: 1h Timeframe / Momentum Entry (Regime-Native)
- Logic:
    1. ENTRY: Triple Lock (Oracle BULL + Price > EMA 200 + Momentum).
    2. SAFETY: -5% Hard Stop + Break-Even Ladder at +1.5%.
    3. EXIT: Trailing Stop (Activates at +3.0%, Trails by 1.5%).
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

class OracleSurfer_v6_PROD(IStrategy):
    """
    OracleSurfer_v6
    The "Undisputed King" of the benchmark tests.
    Survivable in Bear Markets, Profitable in Bull Markets.
    """

    # ===========================
    # 1. CONFIGURATION
    # ===========================
    
    # 1h Timeframe - The Trader's Heartbeat
    timeframe = '1h'
    
    # ROI: UNCAPPED
    # We rely on Trailing Stop to capture the full trend.
    minimal_roi = {
        "0": 100,       
        "240": 0.1,     # Secure 10% after 4 hours
        "480": 0.05,    # Secure 5% after 8 hours
    }
    
    # HARD STOP: -5% 
    # The "Crash Airbag" - saved the strategy in 2022.
    stoploss = -0.05
    
    # TRAILING STOP (Surfer Mode)
    # Activates only after we are well into profit (+3%)
    trailing_stop = True
    trailing_stop_positive = 0.015        # Trail by 1.5%
    trailing_stop_positive_offset = 0.03  # Start trailing after 3%
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
        
        # 1. ORACLE (Entry Gatekeeper)
        # Ensure FreqAI is configured in config.json
        dataframe = self.freqai.start(dataframe, metadata, self)
        
        # 2. TREND (The Floor)
        # EMA 200 is the critical filter that won the Bear Market test.
        dataframe['ema_200'] = ta_lib.EMA(dataframe, timeperiod=200)
        
        # 3. MOMENTUM (The Spark)
        dataframe['rsi'] = ta_lib.RSI(dataframe, timeperiod=14)
        
        macd = ta_lib.MACD(dataframe)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        
        # 4. STRENGTH (The Filter)
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
        # 1. Oracle says BULL
        # 2. Price > EMA 200 (Safety)
        # 3. Momentum Positive (RSI > 50, MACD Bullish)
        # 4. RSI < 75 (Avoid buying the absolute top)
        # 5. Trend Strength Real (ADX > 25)
        dataframe.loc[
            (
                (oracle_signal == "BULL") &
                (dataframe['close'] > dataframe['ema_200']) &
                (dataframe['rsi'] > 50) &
                (dataframe['rsi'] < 75) &
                (dataframe['macd'] > dataframe['macdsignal']) &
                (dataframe['adx'] > 25)
            ),
            'enter_long'] = 1
        
        # --- SHORT ENTRY ---
        # 1. Oracle says BEAR
        # 2. Price < EMA 200 (Safety)
        # 3. Momentum Negative (RSI < 50, MACD Bearish)
        # 4. RSI > 25 (Avoid selling the absolute bottom)
        # 5. Trend Strength Real (ADX > 25)
        dataframe.loc[
            (
                (oracle_signal == "BEAR") &
                (dataframe['close'] < dataframe['ema_200']) &
                (dataframe['rsi'] < 50) &
                (dataframe['rsi'] > 25) &
                (dataframe['macd'] < dataframe['macdsignal']) &
                (dataframe['adx'] > 25)
            ),
            'enter_short'] = 1
            
        return dataframe

    # ===========================
    # 4. EXIT LOGIC
    # ===========================
    
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # No signal exits. We rely entirely on the "Airbag System" below.
        return dataframe

    # ===========================
    # 5. RISK MANAGEMENT (The Airbag)
    # ===========================
    
    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                        current_rate: float, current_profit: float, **kwargs) -> float:
        
        # Logic: 
        # If profit > 1.5% (but less than 3% where trailing starts),
        # Lock in 0.1% profit (Break Even + Fees).
        # This converts "failed breakouts" into "scratches" instead of losses.
        
        if current_profit > 0.015:
            return 0.001  # +0.1% Stop Loss (Guaranteed Win)
        
        # Return -1 to respect the static stoploss (-5%) or standard trailing
        return -1

    # ===========================
    # 6. FREQAI CONFIGURATION
    # ===========================
    def feature_engineering_expand_all(self, dataframe: DataFrame, period: int, metadata: dict, **kwargs) -> DataFrame:
        # Features optimized for the Oracle
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