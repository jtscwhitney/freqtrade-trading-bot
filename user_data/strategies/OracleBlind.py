import numpy as np
import pandas as pd
import pandas_ta as ta
from freqtrade.strategy import IStrategy
from datetime import datetime, timedelta

class OracleBlind(IStrategy):
    """
    Project: Phase C.3 - Blind Faith + 2x Leverage
    Description: 
        - Buy when Oracle says BULL.
        - Exit 1: Trailing Stop (Lock in profits).
        - Exit 2: Time Limit (Force sell after 4 days).
        - LEVERAGE: 2x (Doubles the profit/loss volatility).
    """
    
    # --- LEVERAGE SETTINGS ---
    # We request 2x leverage. 
    # NOTE: Your config.json must have "trading_mode": "futures" for this to work.
    # Leverage Callback
    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: str, side: str,
                 **kwargs) -> float:
        return 2.0
    can_short = True

    # --- SAFETY HARNESS (Wide Stops for Leverage) ---
    # Stoploss is calculated on PRICE movement, not equity.
    # A -0.10 (10%) price drop at 2x leverage = -20% Equity Loss.
    stoploss = -0.10 
    
    # Trailing Stop:
    # "If profit hits 5%, trail the price by 3%."
    # At 2x leverage, a 5% price move equals 10% ROE.
    trailing_stop = True
    trailing_stop_positive = 0.03        # Trail 3% behind the peak
    trailing_stop_positive_offset = 0.05 # Only activate after 5% profit
    trailing_only_offset_is_reached = True

    # ROI: Disabled
    minimal_roi = { "0": 100 }

    # Standard Settings
    timeframe = "15m" 
    process_only_new_candles = True
    startup_candle_count = 200
    use_custom_exit_signal = True

    # --- 2. INDICATORS (FreqAI Only) ---
    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe = self.freqai.start(dataframe, metadata, self)
        return dataframe

    # --- 3. ORACLE BRAIN (Standard 4h Features) ---
    def feature_engineering_expand_all(self, dataframe: pd.DataFrame, period: int, metadata: dict, **kwargs) -> pd.DataFrame:
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

    def feature_engineering_expand_basic(self, dataframe: pd.DataFrame, **kwargs) -> pd.DataFrame:
        metadata = kwargs.get('metadata', {})
        if metadata.get('tf', '') != '4h': return dataframe
        dataframe['%pct-change'] = dataframe['close'].pct_change().fillna(0)
        return dataframe

    def set_freqai_targets(self, dataframe: pd.DataFrame, **kwargs) -> pd.DataFrame:
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

    # --- 4. ENTRY (Blind Faith) ---
    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        target_col = "&s_regime_class"
        if target_col in dataframe.columns:
            oracle_signal = dataframe[target_col]
        else:
            return dataframe

        dataframe.loc[(oracle_signal == "BULL"), 'enter_long'] = 1
        dataframe.loc[(oracle_signal == "BEAR"), 'enter_short'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe['exit_long'] = 0
        dataframe['exit_short'] = 0
        return dataframe

    # --- 5. EXIT (The 4-Day Timer) ---
    def custom_exit(self, pair: str, trade: 'Trade', current_time: datetime, current_rate: float,
                    current_profit: float, **kwargs):
        
        # Calculate hold time in hours
        time_diff = (current_time - trade.open_date_utc).total_seconds() / 3600 
        
        # 4 Days = 96 Hours
        if time_diff >= 96:
            return "oracle_horizon_expired"
            
        return None