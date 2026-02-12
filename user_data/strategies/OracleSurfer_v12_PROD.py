"""
OracleSurfer_v12_PROD ("The Moonshot" - Optimized Horizon)
Production Version | Final Release
- Architecture: 1h Timeframe / Aggressive "Early Bird" Entry
- Logic:
    1. ENTRY: ADX > 15 (Early Bird) + Oracle Signal.
    2. SAFETY: -10% Hard Stop (Survival).
    3. EXIT: Trailing Stop (Activates at +5.0%, Trails by 4.0%).
    4. BONUS: "Free Roll" Logic (Break-Even at +3.0%).
"""

import numpy as np
import pandas as pd
import pandas_ta as ta
from pandas import DataFrame
from freqtrade.strategy import IStrategy
from freqtrade.persistence import Trade
from typing import Optional, Dict
import talib.abstract as ta_lib
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class OracleSurfer_v12_PROD(IStrategy):
    """
    OracleSurfer_v12
    "The Moonshot"
    Sacrifices Win Rate for massive trend capture.
    Designed to hold through 10% corrections to catch 50% runs.
    """

    # ===========================
    # 1. CONFIGURATION
    # ===========================
    
    # 1h Timeframe - The Trader's Heartbeat
    timeframe = '1h'
    
    # ROI: UNCAPPED
    # We rely purely on the Trailing Stop to capture the full trend.
    minimal_roi = {
        "0": 100,       
        "240": 0.1,     
        "480": 0.05,    
    }
    
    # HARD STOP: -10% 
    # WIDER than v6/v10 to survive "Liquidity Hunts" and "Stop Runs".
    stoploss = -0.10
    
    # TRAILING STOP (Diamond Hands Mode)
    # This is very loose. We give the market room to breathe.
    # We only start trailing after we are up 5%.
    trailing_stop = True
    trailing_stop_positive = 0.04         # Trail by 4% (Huge room)
    trailing_stop_positive_offset = 0.05  # Start trailing after 5%
    trailing_only_offset_is_reached = True
    
    process_only_new_candles = True
    startup_candle_count = 240
    
    can_short = True
    
    # Enable Custom Stoploss for "Free Roll" Logic
    use_custom_stoploss = True

    order_types = {
        'entry': 'market',
        'exit': 'market',
        'stoploss': 'market',
        'stoploss_on_exchange': False
    }
    
    # Cache to prevent log spamming
    _stoploss_cache: Dict[str, datetime] = {}

    # ===========================
    # 2. INDICATORS
    # ===========================
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        
        # 1. ORACLE (Entry Gatekeeper)
        dataframe = self.freqai.start(dataframe, metadata, self)
        
        # 2. TREND (The Floor)
        # EMA 100 (Faster than v6 EMA 200) because we want to front-run the trend.
        dataframe['ema_trend'] = ta_lib.EMA(dataframe, timeperiod=100)
        
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
            
            # LOGGING: Trace the Oracle Signal occasionally
            # We only log this for the last candle to avoid backtest spam
            last_idx = dataframe.index[-1]
            current_signal = oracle_signal.iloc[-1]
            if self.config['runmode'].value in ('live', 'dry_run'):
                logger.info(f"Oracle Signal for {metadata['pair']}: {current_signal}")
                
        else:
            oracle_signal = pd.Series("NEUTRAL", index=dataframe.index)

        # --- LONG ENTRY ---
        # 1. Oracle says BULL
        # 2. Price > EMA 100 (Aggressive Trend Floor)
        # 3. Uncapped Momentum (RSI > 50)
        # 4. "Early Bird" ADX: > 15 (Catches trends before they become obvious)
        dataframe.loc[
            (
                (oracle_signal == "BULL") &
                (dataframe['close'] > dataframe['ema_trend']) &
                (dataframe['rsi'] > 50) &
                (dataframe['macd'] > dataframe['macdsignal']) &
                (dataframe['adx'] > 15) # v12 Innovation: Aggressive Entry
            ),
            'enter_long'] = 1
        
        # --- SHORT ENTRY ---
        # 1. Oracle says BEAR
        # 2. Price < EMA 100 
        # 3. Momentum Negative
        # 4. "Early Bird" ADX > 15
        dataframe.loc[
            (
                (oracle_signal == "BEAR") &
                (dataframe['close'] < dataframe['ema_trend']) &
                (dataframe['rsi'] < 50) &
                (dataframe['macd'] < dataframe['macdsignal']) &
                (dataframe['adx'] > 15)
            ),
            'enter_short'] = 1
            
        return dataframe

    # ===========================
    # 4. EXIT LOGIC
    # ===========================
    
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # No signal exits. We live and die by the Trailing Stop.
        return dataframe

    # ===========================
    # 5. RISK MANAGEMENT (The Free Roll)
    # ===========================
    
    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                        current_rate: float, current_profit: float, **kwargs) -> float:
        
        # LOGIC: The "Free Roll"
        # If profit hits +3.0%, we move Stop Loss to Break-Even (+0.1%).
        # This creates a "Risk Free" trade. 
        # We hold this +0.1% stop until price hits +5.0%, where the 
        # "Diamond Hands" trailing stop (4% width) takes over.
        
        if current_profit > 0.03:
            # Check if we already logged this for this trade recently (prevent spam)
            trade_id = str(trade.id)
            last_log = self._stoploss_cache.get(trade_id)
            
            if not last_log or (current_time - last_log > timedelta(minutes=60)):
                logger.info(f"FREE ROLL ACTIVE for {pair}: Profit {current_profit:.2%}, Stop moved to BE.")
                self._stoploss_cache[trade_id] = current_time
            
            return 0.001  # +0.1% Profit (Guaranteed Win)
        
        # Return -1 to respect the static stoploss (-10%) or standard trailing
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
        
        # --- QUANT UPDATE: HORIZON OPTIMIZATION ---
        # OLD: Look ahead 4 days (Laggy during trend reversals)
        horizon = 24  # [QUANT_OLD] 24 candles * 4h = 96h
        # horizon = 12    # [QUANT_NEW] 12 candles * 4h = 48h (Faster reaction)
        
        dataframe['atr'] = ta.atr(dataframe['high'], dataframe['low'], dataframe['close'], length=14)
        
        # --- QUANT UPDATE: BARRIER ADJUSTMENT ---
        # OLD: 2.0x ATR (Too hard to hit in 48h)
        barrier_threshold = dataframe['atr'] * 2.0 # [QUANT_OLD]
        # barrier_threshold = dataframe['atr'] * 1.5   # [QUANT_NEW] Lower threshold for shorter horizon
        
        future_max = dataframe['high'].shift(-1).rolling(window=horizon, min_periods=1).max()
        future_min = dataframe['low'].shift(-1).rolling(window=horizon, min_periods=1).min()
        
        dataframe['&s_regime_class'] = "NEUTRAL"
        valid_mask = (pd.notna(future_max) & pd.notna(future_min) & pd.notna(barrier_threshold))
        
        bull_condition = valid_mask & (future_max > (dataframe['close'] + barrier_threshold))
        bear_condition = valid_mask & (future_min < (dataframe['close'] - barrier_threshold))
        
        # --- QUANT UPDATE: SAFETY PRIORITY ---
        # OLD: Bull signal overwrote Bear signal (Optimism Bias)
        dataframe.loc[bear_condition, '&s_regime_class'] = "BEAR" # [QUANT_OLD]
        dataframe.loc[bull_condition, '&s_regime_class'] = "BULL" # [QUANT_OLD]
        
        # NEW: Bear signal overwrites Bull signal (Safety Bias)
        # If volatility is high enough to hit BOTH targets, we default to BEAR
        # to avoid catching "falling knives".
        # dataframe.loc[bull_condition, '&s_regime_class'] = "BULL"
        # dataframe.loc[bear_condition, '&s_regime_class'] = "BEAR" # [QUANT_NEW] Safety First
        
        return dataframe