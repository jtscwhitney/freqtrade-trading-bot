"""
BollingerRatchet Strategy - Converted from Pine Script v6

Original: Jeff-Matt-Kyle Bollinger 03
Conversion: TradingView Pine Script -> Freqtrade Python

Key Features:
- State Machine Entry Logic: Tracks "Potential Order" setup before triggering
- Ratchet Trailing Stop: Custom stop that only tightens, never loosens
- Bar Magnifier: Uses high/low for entry triggers, not just close
- Indicators: EMA 500, BB 50, MFI 14, ATR 14
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


class BollingerRatchet(IStrategy):
    """
    Bollinger Band + EMA strategy with advanced state machine entry logic
    and a custom ratcheting trailing stop that only tightens.
    
    Enhanced with Oracle Regime Filter (FreqAI) to prevent counter-trend trades.
    """
    
    # ===========================
    # STRATEGY PARAMETERS
    # ===========================
    
    # Minimal ROI - Consider commission of 0.055% per trade
    minimal_roi = {
        "0": 0.10,   # 10% profit target
        "60": 0.05,  # 5% after 1 hour
        "120": 0.03  # 3% after 2 hours
    }
    
    # Hard stop loss (emergency only)
    stoploss = -0.10  # -10% emergency stop
    
    # Trailing stop - Let winners run longer
    trailing_stop = True
    trailing_stop_positive = 0.02  # Trail by 2% once in profit
    trailing_stop_positive_offset = 0.05  # Start trailing after 5% profit
    trailing_only_offset_is_reached = True
    
    # Timeframe
    timeframe = '15m'  # Adjust to match your backtesting needs
    
    # Run only on new candles
    process_only_new_candles = True
    
    # Startup candle count (need enough for EMA 500)
    startup_candle_count = 600
    
    # Order types
    order_types = {
        'entry': 'market',
        'exit': 'market',
        'stoploss': 'market',
        'stoploss_on_exchange': False
    }
    
    # ===========================
    # INDICATOR PARAMETERS
    # ===========================
    
    # EMA
    ema_length = 500
    
    # Bollinger Bands
    bb_length = 50
    bb_std_dev = 2.0
    
    # Money Flow Index (MFI)
    mfi_length = 14
    mfi_lower_threshold = 40
    mfi_higher_threshold = 60
    
    # ATR
    atr_length = 14
    atr_risk_factor = 1.4  # Original Pine Script value
    
    # Enable position adjustment (for stop loss updates)
    position_adjustment_enable = True
    
    # ===========================
    # LEVERAGE
    # ===========================
    
    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: Optional[str],
                 side: str, **kwargs) -> float:
        """
        Set leverage to 2x (matching Pine Script margin_long=0.5, margin_short=0.5)
        """
        return 2.0
    
    # ===========================
    # INDICATOR POPULATION
    # ===========================
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Calculate all required indicators:
        - Oracle Regime Filter (FreqAI on 4h timeframe)
        - EMA 500
        - Bollinger Bands (50, 2.0)
        - MFI (14)
        - ATR (14)
        - ATR-based stop levels
        """
        
        # ===========================
        # ORACLE REGIME FILTER (FreqAI)
        # ===========================
        # Run FreqAI to get regime prediction (BEAR, NEUTRAL, BULL)
        # This projects 4h regime predictions onto the current timeframe
        dataframe = self.freqai.start(dataframe, metadata, self)
        
        # EMA
        dataframe['ema'] = ta_lib.EMA(dataframe, timeperiod=self.ema_length)
        
        # Bollinger Bands
        bollinger = ta_lib.BBANDS(
            dataframe,
            timeperiod=self.bb_length,
            nbdevup=self.bb_std_dev,
            nbdevdn=self.bb_std_dev,
            matype=0
        )
        dataframe['bb_upper'] = bollinger['upperband']
        dataframe['bb_middle'] = bollinger['middleband']
        dataframe['bb_lower'] = bollinger['lowerband']
        
        # Money Flow Index (MFI)
        dataframe['mfi'] = ta_lib.MFI(dataframe, timeperiod=self.mfi_length)
        
        # Average True Range (ATR)
        dataframe['atr'] = ta_lib.ATR(dataframe, timeperiod=self.atr_length)
        
        # ATR-based stop levels
        dataframe['atr_lower'] = dataframe['close'] - (dataframe['atr'] * self.atr_risk_factor)
        dataframe['atr_upper'] = dataframe['close'] + (dataframe['atr'] * self.atr_risk_factor)
        
        # ===========================
        # STATE MACHINE LOGIC WITH ORACLE FILTER
        # ===========================
        # Implement the "Potential Order" state tracking using vectorized pandas
        # ENHANCED: Oracle Regime Filter prevents counter-trend setups
        
        # Read Oracle prediction (if available)
        target_col = "&s_regime_class"
        if target_col in dataframe.columns:
            oracle_signal = dataframe[target_col]
        else:
            # If Oracle not available, allow all trades (neutral stance)
            oracle_signal = pd.Series("NEUTRAL", index=dataframe.index)
        
        # --- POTENTIAL LONG SETUP ---
        # Condition: bbLower > emaValue AND low > emaValue AND close < bbLower
        # ORACLE FILTER: Only allow if Oracle is NOT saying BEAR
        potential_long_setup = (
            (dataframe['bb_lower'] > dataframe['ema']) &
            (dataframe['low'] > dataframe['ema']) &
            (dataframe['close'] < dataframe['bb_lower']) &
            (oracle_signal != "BEAR")  # Oracle Filter: No longs in BEAR regime
        )
        
        # --- POTENTIAL SHORT SETUP ---
        # Condition: bbUpper < emaValue AND high < emaValue AND close > bbUpper
        # ORACLE FILTER: Only allow if Oracle is NOT saying BULL
        potential_short_setup = (
            (dataframe['bb_upper'] < dataframe['ema']) &
            (dataframe['high'] < dataframe['ema']) &
            (dataframe['close'] > dataframe['bb_upper']) &
            (oracle_signal != "BULL")  # Oracle Filter: No shorts in BULL regime
        )
        
        # Track setup state with forward fill (state persists until invalidated or triggered)
        dataframe['potential_long'] = potential_long_setup.astype(int)
        dataframe['potential_short'] = potential_short_setup.astype(int)
        
        # Invalidation conditions for Long:
        # - bbLower < emaValue OR low < emaValue
        long_invalidation = (
            (dataframe['bb_lower'] < dataframe['ema']) |
            (dataframe['low'] < dataframe['ema'])
        )
        
        # Invalidation conditions for Short:
        # - bbUpper > emaValue OR high > emaValue
        short_invalidation = (
            (dataframe['bb_upper'] > dataframe['ema']) |
            (dataframe['high'] > dataframe['ema'])
        )
        
        # Propagate the "potential order" state using a custom forward fill with invalidation
        # This is the tricky part - we need to maintain state until either:
        # 1. The condition is invalidated
        # 2. An entry is triggered
        
        # Initialize state columns
        dataframe['is_potential_long'] = False
        dataframe['is_potential_short'] = False
        
        # Iterate to build state (this is necessary for the state machine logic)
        # While not fully vectorized, this is the most accurate translation
        for i in range(1, len(dataframe)):
            # --- LONG STATE ---
            if potential_long_setup.iloc[i]:
                # New potential long setup
                dataframe.loc[dataframe.index[i], 'is_potential_long'] = True
            elif dataframe['is_potential_long'].iloc[i-1] and not long_invalidation.iloc[i]:
                # Continue previous state if not invalidated
                dataframe.loc[dataframe.index[i], 'is_potential_long'] = True
            else:
                dataframe.loc[dataframe.index[i], 'is_potential_long'] = False
            
            # --- SHORT STATE ---
            if potential_short_setup.iloc[i]:
                # New potential short setup
                dataframe.loc[dataframe.index[i], 'is_potential_short'] = True
            elif dataframe['is_potential_short'].iloc[i-1] and not short_invalidation.iloc[i]:
                # Continue previous state if not invalidated
                dataframe.loc[dataframe.index[i], 'is_potential_short'] = True
            else:
                dataframe.loc[dataframe.index[i], 'is_potential_short'] = False
        
        # --- ENTRY TRIGGERS (Bar Magnifier Logic) ---
        # Long: ta.crossover(high, bbLower) - high crosses above bbLower
        dataframe['high_prev'] = dataframe['high'].shift(1)
        dataframe['long_trigger'] = (
            (dataframe['high'] > dataframe['bb_lower']) &
            (dataframe['high_prev'] <= dataframe['bb_lower'])
        )
        
        # Short: ta.crossunder(low, bbUpper) - low crosses below bbUpper
        dataframe['low_prev'] = dataframe['low'].shift(1)
        dataframe['short_trigger'] = (
            (dataframe['low'] < dataframe['bb_upper']) &
            (dataframe['low_prev'] >= dataframe['bb_upper'])
        )
        
        return dataframe
    
    # ===========================
    # FREQAI ORACLE METHODS
    # ===========================
    # These methods define the Oracle's features and targets
    # The Oracle runs on 4h timeframe to predict regime (BEAR/NEUTRAL/BULL)
    
    def feature_engineering_expand_all(self, dataframe: DataFrame, period: int,
                                       metadata: dict, **kwargs) -> DataFrame:
        """
        Create features for the Oracle (4h timeframe only)
        
        CRITICAL: Only generate features for 4h timeframe to match trained model
        """
        # --- GATEKEEPER ---
        # The Oracle model was trained ONLY on '4h' data
        # If we let this run on other timeframes, it creates incompatible columns
        if metadata.get('tf', '') != '4h':
            return dataframe
        
        # 1. Regime: Choppiness Index (measures market choppiness vs. trend)
        dataframe['%regime_chop'] = ta.chop(
            dataframe['high'], 
            dataframe['low'], 
            dataframe['close'], 
            length=14
        )
        
        # 2. Efficiency: KAMA Distance (Kaufman Adaptive Moving Average)
        kama = ta.kama(dataframe['close'], length=10)
        dataframe['%trend_kama_dist'] = (dataframe['close'] - kama) / kama
        
        # 3. Valuation: LTVD (Long-term Value Distance from 200 SMA)
        long_ma = ta.sma(dataframe['close'], length=200)
        dataframe['%val_ltvd'] = (dataframe['close'] - long_ma) / dataframe['close']
        
        # 4. Fear: Williams VixFix (volatility / fear indicator)
        period_vix = 22
        highest_close = dataframe['close'].rolling(window=period_vix).max()
        dataframe['%fear_vixfix'] = (highest_close - dataframe['low']) / highest_close * 100
        
        # 5. Truth: OBV Oscillator (On-Balance Volume momentum)
        obv = ta.obv(dataframe['close'], dataframe['volume'])
        obv_ma = ta.sma(obv, length=20)
        dataframe['%truth_obv_osc'] = (obv - obv_ma) / obv_ma
        
        # Fill NaNs
        return dataframe.fillna(0)
    
    def feature_engineering_expand_basic(self, dataframe: DataFrame, **kwargs) -> DataFrame:
        """
        Create basic features for the Oracle (4h timeframe only)
        """
        # --- GATEKEEPER ---
        metadata = kwargs.get('metadata', {})
        if metadata.get('tf', '') != '4h':
            return dataframe
        
        # Simple percent change
        dataframe['%pct-change'] = dataframe['close'].pct_change().fillna(0)
        return dataframe
    
    def set_freqai_targets(self, dataframe: DataFrame, **kwargs) -> DataFrame:
        """
        Define the Oracle's prediction target: Market Regime
        
        Classification:
        - BULL: Price expected to rise significantly (> 2*ATR in next 24 candles)
        - BEAR: Price expected to fall significantly (< -2*ATR in next 24 candles)
        - NEUTRAL: Sideways or unclear movement
        """
        # Set class names for FreqAI
        self.freqai.class_names = ["BEAR", "NEUTRAL", "BULL"]
        
        # Look-ahead horizon (24 candles on 4h = ~4 days)
        horizon = 24
        
        # Calculate ATR for barrier threshold
        dataframe['atr'] = ta.atr(
            dataframe['high'], 
            dataframe['low'], 
            dataframe['close'], 
            length=14
        )
        barrier_threshold = dataframe['atr'] * 2.0
        
        # Future price movement
        future_max = dataframe['high'].shift(-1).rolling(window=horizon, min_periods=1).max()
        future_min = dataframe['low'].shift(-1).rolling(window=horizon, min_periods=1).min()
        
        # Initialize as NEUTRAL
        dataframe['&s_regime_class'] = "NEUTRAL"
        
        # Create masks for valid data
        valid_mask = (
            pd.notna(future_max) & 
            pd.notna(future_min) & 
            pd.notna(barrier_threshold)
        )
        
        # BULL condition: Future high exceeds current close + 2*ATR
        bull_condition = valid_mask & (future_max > (dataframe['close'] + barrier_threshold))
        
        # BEAR condition: Future low falls below current close - 2*ATR
        bear_condition = valid_mask & (future_min < (dataframe['close'] - barrier_threshold))
        
        # Assign classifications
        dataframe.loc[bear_condition, '&s_regime_class'] = "BEAR"
        dataframe.loc[bull_condition, '&s_regime_class'] = "BULL"
        
        return dataframe
    
    # ===========================
    # ENTRY LOGIC
    # ===========================
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Entry logic implementing the state machine with Oracle regime filter:
        1. Potential Order state must be active (ALREADY FILTERED BY ORACLE)
        2. Trigger condition must be met (crossover/crossunder)
        3. MFI filter must pass
        
        NOTE: Oracle regime filter is applied at the setup stage in populate_indicators.
              - Long setups are blocked when Oracle says BEAR
              - Short setups are blocked when Oracle says BULL
              - Both are allowed when Oracle says NEUTRAL
        """
        
        # --- LONG ENTRY ---
        # Conditions:
        # 1. is_potential_long == True (already includes Oracle filter: no BEAR regime)
        # 2. long_trigger (high crosses above bb_lower)
        # 3. mfi < mfi_lower_threshold
        dataframe.loc[
            (
                (dataframe['is_potential_long'] == True) &
                (dataframe['long_trigger'] == True) &
                (dataframe['mfi'] < self.mfi_lower_threshold)
            ),
            'enter_long'] = 1
        
        # --- SHORT ENTRY ---
        # Conditions:
        # 1. is_potential_short == True (already includes Oracle filter: no BULL regime)
        # 2. short_trigger (low crosses below bb_upper)
        # 3. mfi > mfi_higher_threshold
        dataframe.loc[
            (
                (dataframe['is_potential_short'] == True) &
                (dataframe['short_trigger'] == True) &
                (dataframe['mfi'] > self.mfi_higher_threshold)
            ),
            'enter_short'] = 1
        
        return dataframe
    
    # ===========================
    # EXIT LOGIC
    # ===========================
    
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Exit logic is handled primarily by custom_stoploss.
        No additional exit signals needed here.
        """
        # No exit signals - rely on custom_stoploss and ROI
        return dataframe
    
    # ===========================
    # CUSTOM RATCHET STOP LOSS (CURRENTLY DISABLED)
    # ===========================
    # 
    # NOTE: This custom stop loss implementation is currently COMMENTED OUT.
    # The built-in Freqtrade stop loss mechanism is performing better (84.6% win rate).
    # 
    # To re-enable the custom stop loss:
    # 1. Uncomment all code below
    # 2. Set: use_custom_stoploss = True (at top of class)
    # 3. Remove or adjust the built-in trailing_stop parameters
    # 
    # ===========================
    
    # def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
    #                     current_rate: float, current_profit: float, 
    #                     after_fill: bool, **kwargs) -> Optional[float]:
    #     """
    #     Implements the RATCHET trailing stop logic from Pine Script + Trailing Take-Profit.
    #     
    #     Enhanced with:
    #     1. Tighter initial stops (ATR × 1.0 instead of 1.4)
    #     2. Trailing take-profit (starts after 5% profit, trails by 2%)
    #     3. Ratchet logic (only tightens, never loosens)
    #     
    #     For LONG positions:
    #     - Initial stop: ATRLower (tighter with atr_risk_factor = 1.0)
    #     - If profit >= 5%: Start trailing (lock in profits)
    #     - If close >= bb_middle: Ratchet stop tighter
    #     
    #     For SHORT positions:
    #     - Initial stop: ATRUpper (tighter with atr_risk_factor = 1.0)
    #     - If profit >= 5%: Start trailing (lock in profits)
    #     - If close <= bb_middle: Ratchet stop tighter
    #     """
    #     
    #     # Get the current candle data
    #     dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
    #     
    #     if dataframe is None or len(dataframe) == 0:
    #         return None
    #     
    #     # Get the latest candle
    #     last_candle = dataframe.iloc[-1]
    #     
    #     # Extract values
    #     close = last_candle['close']
    #     bb_middle = last_candle['bb_middle']
    #     atr_lower = last_candle['atr_lower']
    #     atr_upper = last_candle['atr_upper']
    #     
    #     # Trailing take-profit parameters
    #     trailing_offset = 0.05  # Start trailing after 5% profit
    #     trailing_distance = 0.02  # Trail by 2%
    #     
    #     # Get the current stop loss from trade custom data (or initialize)
    #     if trade.is_short:
    #         # SHORT POSITION
    #         # Initial stop: ATRUpper (now tighter with atr_risk_factor = 1.0)
    #         if not hasattr(trade, 'custom_data') or trade.custom_data is None:
    #             trade.custom_data = {'stop_loss': atr_upper}
    #         
    #         current_stop = trade.custom_data.get('stop_loss', atr_upper)
    #         
    #         # RATCHET LOGIC: Tighten when price moves favorably
    #         ratchet_stop = current_stop
    #         if close <= bb_middle:
    #             # Check if ATRUpper is tighter and below bb_middle
    #             if atr_upper <= bb_middle and atr_upper <= current_stop:
    #                 ratchet_stop = atr_upper
    #             # Otherwise check if bb_middle is tighter
    #             elif bb_middle <= current_stop:
    #                 ratchet_stop = bb_middle
    #         
    #         # TRAILING TAKE-PROFIT: If profit >= 5%, start trailing
    #         trailing_stop = current_stop
    #         if current_profit >= trailing_offset:
    #             # Calculate trailing stop: current_rate + trailing_distance
    #             trailing_stop_price = current_rate * (1 + trailing_distance)
    #             # Only tighten (for shorts, lower stop = tighter)
    #             if trailing_stop_price < current_stop:
    #                 trailing_stop = trailing_stop_price
    #         
    #         # Use the TIGHTER of ratchet stop or trailing stop
    #         new_stop = min(ratchet_stop, trailing_stop)
    #         
    #         # Update stop (only if tighter)
    #         if new_stop <= current_stop:
    #             trade.custom_data['stop_loss'] = new_stop
    #             current_stop = new_stop
    #         
    #         # Calculate stop as a ratio for short
    #         # For shorts, positive ratio means stop above entry
    #         stop_ratio = (current_stop - trade.open_rate) / trade.open_rate
    #         return stop_ratio
    #         
    #     else:
    #         # LONG POSITION
    #         # Initial stop: ATRLower (now tighter with atr_risk_factor = 1.0)
    #         if not hasattr(trade, 'custom_data') or trade.custom_data is None:
    #             trade.custom_data = {'stop_loss': atr_lower}
    #         
    #         current_stop = trade.custom_data.get('stop_loss', atr_lower)
    #         
    #         # RATCHET LOGIC: Tighten when price moves favorably
    #         ratchet_stop = current_stop
    #         if close >= bb_middle:
    #             # Check if ATRLower is tighter and above bb_middle
    #             if atr_lower >= bb_middle and atr_lower >= current_stop:
    #                 ratchet_stop = atr_lower
    #             # Otherwise check if bb_middle is tighter
    #             elif bb_middle >= current_stop:
    #                 ratchet_stop = bb_middle
    #         
    #         # TRAILING TAKE-PROFIT: If profit >= 5%, start trailing
    #         trailing_stop = current_stop
    #         if current_profit >= trailing_offset:
    #             # Calculate trailing stop: current_rate - trailing_distance
    #             trailing_stop_price = current_rate * (1 - trailing_distance)
    #             # Only tighten (for longs, higher stop = tighter)
    #             if trailing_stop_price > current_stop:
    #                 trailing_stop = trailing_stop_price
    #         
    #         # Use the TIGHTER of ratchet stop or trailing stop
    #         new_stop = max(ratchet_stop, trailing_stop)
    #         
    #         # Update stop (only if tighter)
    #         if new_stop >= current_stop:
    #             trade.custom_data['stop_loss'] = new_stop
    #             current_stop = new_stop
    #         
    #         # Calculate stop as a ratio for long
    #         # For longs, negative ratio means stop below entry
    #         stop_ratio = (current_stop - trade.open_rate) / trade.open_rate
    #         return stop_ratio
    
    # ===========================
    # CUSTOM ENTRY PRICE (Optional)
    # ===========================
    
    def custom_entry_price(self, pair: str, current_time: datetime, proposed_rate: float,
                          entry_tag: Optional[str], side: str, **kwargs) -> float:
        """
        Custom entry price - use market price
        """
        return proposed_rate
    
    # ===========================
    # INFORMATIVE PAIRS (Optional)
    # ===========================
    
    def informative_pairs(self):
        """
        Define additional pairs to download data for
        """
        return []
    
    # ===========================
    # TRADE MANAGEMENT
    # ===========================
    
    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, 
                           rate: float, time_in_force: str, current_time: datetime,
                           entry_tag: Optional[str], side: str, **kwargs) -> bool:
        """
        Confirm trade entry - can add additional filters here
        """
        return True
    
    def confirm_trade_exit(self, pair: str, trade: Trade, order_type: str, amount: float,
                          rate: float, time_in_force: str, exit_reason: str,
                          current_time: datetime, **kwargs) -> bool:
        """
        Confirm trade exit
        """
        return True
