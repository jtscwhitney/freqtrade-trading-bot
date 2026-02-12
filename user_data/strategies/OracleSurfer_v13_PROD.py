# ==========================================
#  OracleSurfer v13 ("The Hyperdrive")
# ==========================================
#  Philosophy: Leveraged Pyramiding (Reverse Martingale)
#  Base Logic: v12 (Moonshot)
#  New Feature: Position Stacking (Add to Winners)
# ==========================================

import numpy as np
import pandas as pd
import pandas_ta as ta
from pandas import DataFrame
from freqtrade.strategy import IStrategy
from freqtrade.persistence import Trade
from datetime import datetime
from typing import Optional
import talib.abstract as ta_lib

class OracleSurfer_v13_PROD(IStrategy):
    """
    OracleSurfer v13 - Hyperdrive
    -----------------------------
    A leveraged variant of 'The Moonshot'.
    It uses 'Pyramiding' to increase position size on winning trades.
    """

    # ====================
    # 1. CONFIGURATION
    # ====================
    timeframe = '1h'

    # LEVERAGE: 3x
    # We amplify the position size.
    # NOTE: You must have sufficient collateral in your Futures wallet.
    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: Optional[str],
                 side: str, **kwargs) -> float:
        return 3.0

    # ROI: UNCAPPED
    minimal_roi = { "0": 100 }

    # HARD STOP: -8% 
    # slightly tighter than v12 (-10%) because 3x leverage 
    # makes a -10% move a -30% equity hit.
    stoploss = -0.08 

    # TRAILING STOP ("Diamond Hands" with a Ratchet)
    trailing_stop = True
    trailing_stop_positive = 0.03         # Trail by 3.0% (Tightened slightly from 4%)
    trailing_stop_positive_offset = 0.06  # Start trailing after 6% profit
    trailing_only_offset_is_reached = True

    process_only_new_candles = True
    startup_candle_count = 240
    can_short = True 
    use_custom_stoploss = True

    # Enable Position Adjustment (Pyramiding)
    position_adjustment_enable = True
    
    # We will buy 2 more times (Total 3 entries)
    # 1. Initial Entry
    # 2. Re-up at +2.5%
    # 3. Re-up at +5.0%
    max_entry_position_adjustment = 2 

    order_types = {
        'entry': 'market',
        'exit': 'market',
        'stoploss': 'market',
        'stoploss_on_exchange': False
    }

    # ====================
    # 2. PYRAMIDING LOGIC (The New Engine)
    # ====================
    def adjust_trade_position(self, trade: Trade, current_time: datetime,
                              current_rate: float, current_profit: float,
                              min_stake: float, max_stake: float,
                              **kwargs) -> Optional[float]:
        """
        Custom Logic to 'Pyramid' into winning trades.
        """
        
        # 1. If we have filled all orders, stop.
        if trade.nr_of_successful_entries >= (self.max_entry_position_adjustment + 1):
            return None

        # 2. Verify we have profit before adding risk
        # Level 1 Add: Profit > 2.5%
        # Level 2 Add: Profit > 5.0%
        
        filled_entries = trade.nr_of_successful_entries
        
        # Logic: If we have 1 entry and profit > 2.5%, buy same amount again.
        if filled_entries == 1 and current_profit > 0.025:
            return trade.stake_amount # Buy equal size (Double down)
            
        # Logic: If we have 2 entries and profit > 5.0%, buy same amount again.
        if filled_entries == 2 and current_profit > 0.05:
            return trade.stake_amount # Buy equal size (Triple down)

        return None

    # ====================
    # 3. INDICATORS (Same as v12)
    # ====================
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # FreqAI
        dataframe = self.freqai.start(dataframe, metadata, self)

        # Trend (EMA 100 - Fast)
        dataframe['ema_trend'] = ta_lib.EMA(dataframe, timeperiod=100)

        # Momentum
        dataframe['rsi'] = ta_lib.RSI(dataframe, timeperiod=14)
        macd = ta_lib.MACD(dataframe)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']

        # Strength (ADX)
        dataframe['adx'] = ta_lib.ADX(dataframe)
        
        return dataframe

    # ====================
    # 4. ENTRY LOGIC (v12 Moonshot Chassis)
    # ====================
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        
        target_col = "&s_regime_class"
        if target_col in dataframe.columns:
            oracle_signal = dataframe[target_col]
        else:
            oracle_signal = pd.Series("NEUTRAL", index=dataframe.index)

        # LONG
        dataframe.loc[
            (
                (oracle_signal == "BULL") &
                (dataframe['close'] > dataframe['ema_trend']) &
                (dataframe['rsi'] > 50) &
                (dataframe['macd'] > dataframe['macdsignal']) &
                (dataframe['adx'] > 15) # Aggressive Entry
            ),
            'enter_long'] = 1

        # SHORT
        dataframe.loc[
            (
                (oracle_signal == "BEAR") &
                (dataframe['close'] < dataframe['ema_trend']) &
                (dataframe['rsi'] < 50) &
                (dataframe['rsi'] > 25) &
                (dataframe['macd'] < dataframe['macdsignal']) &
                (dataframe['adx'] > 15) 
            ),
            'enter_short'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    # ====================
    # 5. RISK MANAGEMENT
    # ====================
    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                        current_rate: float, current_profit: float, **kwargs) -> float:
        
        # AGGRESSIVE BREAK-EVEN
        # Since we are pyramiding, we must protect the principal faster.
        # If profit hits 4% (after the first pyramid add), move stop to Break Even.
        if current_profit > 0.04:
            return 0.001 
            
        return -1

    # ====================
    # 6. FREQAI BOILERPLATE
    # ====================
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