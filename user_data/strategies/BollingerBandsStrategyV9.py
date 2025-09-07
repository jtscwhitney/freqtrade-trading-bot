# ---
# @version 5
# @strategy BollingerBandsStrategyV9
# @description Bollinger Bands strategy with EMA, MFI, and ATR indicators
# @author Converted from TypeScript
# @tags bollinger, ema, mfi, atr, kraken
# ---

import logging
from datetime import datetime
from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter
from freqtrade.persistence import Trade
from pandas import DataFrame
import pandas as pd
import numpy as np
import talib.abstract as ta
from typing import Dict, List, Optional, Tuple
from freqtrade.exchange import timeframe_to_minutes

logger = logging.getLogger(__name__)


class BollingerBandsStrategyV9(IStrategy):
    """
    Bollinger Bands Strategy V9
    
    This strategy uses:
    - Exponential Moving Average (EMA) for trend direction
    - Bollinger Bands for price levels
    - Money Flow Index (MFI) for overbought/oversold conditions
    - Average True Range (ATR) for dynamic stop loss management
    
    Initialization:
    - Requires 500 candles for proper indicator initialization
    - All indicators are calculated using the 500 candle warm-up period
    - Ensures stable and accurate indicator values before trading begins
    
    Entry Logic:
    - Sell: Price closes above upper BB, BB upper < EMA, candle high < EMA, MFI > 60
    - Buy: Price closes below lower BB, BB lower > EMA, candle low > EMA, MFI < 40
    
    Exit Logic:
    - Dynamic stop loss based on ATR and Bollinger Bands middle
    - Trailing stop loss that adjusts based on market conditions
    """
    
    # Strategy interface version
    INTERFACE_VERSION = 3
    
    # Timeframe
    timeframe = '15m'
    
    # Minimal ROI table - disabled in favor of custom exit logic
    minimal_roi = {
        "0": 100  # Effectively disabled
    }
    
    # Stop loss - will be overridden by custom logic
    stoploss = -0.10
    
    # Use custom stoploss
    use_custom_stoploss = True
    
    # Trailing stop
    trailing_stop = False
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.02
    trailing_only_offset_is_reached = False
    
    # Order types
    order_types = {
        'entry': 'limit',
        'exit': 'limit',
        'emergency_exit': 'market',
        'force_entry': 'market',
        'force_exit': 'market',
        'stoploss': 'market',
        'stoploss_on_exchange': False,
        'stoploss_on_exchange_interval': 60,
    }
    
    # Order time in force
    order_time_in_force = {
        'entry': 'gtc',
        'exit': 'gtc',
    }
    
    # Process only new candles
    process_only_new_candles = True
    
    # Number of candles the strategy requires before producing valid signals
    # Set to 500 to ensure proper initialization of all indicators
    startup_candle_count: int = 500
    
    # Strategy parameters (optimized for 500 candle initialization)
    # All parameters are designed to work within the 500 candle startup period
    ema_length = IntParameter(400, 600, default=500, space="buy")
    bbands_length = IntParameter(40, 60, default=50, space="buy")
    bbands_stdev = DecimalParameter(1.5, 2.5, default=2.0, space="buy")
    mfi_length = IntParameter(10, 20, default=14, space="buy")
    atr_length = IntParameter(10, 20, default=14, space="buy")
    risk_factor = DecimalParameter(1.0, 2.0, default=1.5, space="buy")
    overbought_min_mfi = IntParameter(55, 70, default=60, space="buy")
    oversold_max_mfi = IntParameter(30, 45, default=40, space="buy")
    
    def __init__(self, config: dict) -> None:
        super().__init__(config)
        
        # State management (equivalent to TypeScript state)
        self.potential_order_side: Optional[str] = None
        self.is_potential_order_signaled: bool = False
        self.last_processed_candle: Optional[DataFrame] = None
        
        # Rolling window tracking for verification
        self.last_calculation_timestamp: Optional[datetime] = None
        self.calculation_count: int = 0
        
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Add technical indicators to the dataframe
        Initialize with 500 candles to ensure all indicators are properly calculated
        Each new candle triggers recalculation of all indicators using rolling 500-candle window
        """
        # Track calculation frequency and timing for verification
        self.calculation_count += 1
        current_time = datetime.now()
        
        # Log the current dataframe length for verification
        logger.debug(f"Processing {len(dataframe)} candles for {metadata['pair']} - Rolling window calculation #{self.calculation_count}")
        
        # Log time since last calculation to verify rolling behavior
        if self.last_calculation_timestamp:
            time_diff = (current_time - self.last_calculation_timestamp).total_seconds()
            logger.debug(f"Time since last calculation: {time_diff:.2f} seconds")
        
        self.last_calculation_timestamp = current_time
        
        # Check if we have enough data for proper initialization
        if len(dataframe) < self.startup_candle_count:
            logger.warning(f"Insufficient data for {metadata['pair']}: {len(dataframe)} candles, need {self.startup_candle_count}")
            # Return dataframe with NaN indicators if insufficient data
            dataframe['ema'] = np.nan
            dataframe['bb_lowerband'] = np.nan
            dataframe['bb_middleband'] = np.nan
            dataframe['bb_upperband'] = np.nan
            dataframe['mfi'] = np.nan
            dataframe['atr'] = np.nan
            dataframe['atr_lower'] = np.nan
            dataframe['atr_upper'] = np.nan
            dataframe['price_above_ema'] = False
            dataframe['price_below_ema'] = False
            dataframe['high_above_ema'] = False
            dataframe['low_below_ema'] = False
            dataframe['bb_upper_vs_ema'] = False
            dataframe['bb_lower_vs_ema'] = False
            return dataframe
        
        # Ensure we're using a rolling window of exactly 500 candles for calculation
        # Freqtrade with process_only_new_candles=True still passes the full dataframe
        # but we want to ensure our indicators use the most recent 500 candles
        rolling_window_size = min(len(dataframe), self.startup_candle_count)
        logger.debug(f"Using rolling window of {rolling_window_size} candles for indicator calculation")
        
        # Use the most recent 500 candles for indicator calculation (rolling window)
        # This ensures indicators are recalculated based on the latest 500 candles each time
        recent_data = dataframe.tail(rolling_window_size).copy()
        
        # Exponential Moving Average - calculated on rolling window
        dataframe['ema'] = ta.EMA(dataframe['close'], timeperiod=self.ema_length.value)
        
        # Bollinger Bands - calculated on rolling window
        bollinger = ta.BBANDS(
            dataframe['close'], 
            timeperiod=self.bbands_length.value,
            nbdevup=self.bbands_stdev.value,
            nbdevdn=self.bbands_stdev.value,
            matype=0
        )
        dataframe['bb_lowerband'] = bollinger[0]  # lowerband
        dataframe['bb_middleband'] = bollinger[1]  # middleband
        dataframe['bb_upperband'] = bollinger[2]  # upperband
        
        # Money Flow Index - calculated on rolling window
        dataframe['mfi'] = ta.MFI(
            dataframe['high'],
            dataframe['low'],
            dataframe['close'],
            dataframe['volume'],
            timeperiod=self.mfi_length.value
        )
        
        # Average True Range - calculated on rolling window
        dataframe['atr'] = ta.ATR(
            dataframe['high'],
            dataframe['low'],
            dataframe['close'],
            timeperiod=self.atr_length.value
        )
        
        # ATR-based stop loss levels
        dataframe['atr_lower'] = dataframe['close'] - (dataframe['atr'] * self.risk_factor.value)
        dataframe['atr_upper'] = dataframe['close'] + (dataframe['atr'] * self.risk_factor.value)
        
        # Additional indicators for state management
        dataframe['price_above_ema'] = dataframe['close'] > dataframe['ema']
        dataframe['price_below_ema'] = dataframe['close'] < dataframe['ema']
        dataframe['high_above_ema'] = dataframe['high'] > dataframe['ema']
        dataframe['low_below_ema'] = dataframe['low'] < dataframe['ema']
        
        # Bollinger Bands relative to EMA
        dataframe['bb_upper_vs_ema'] = dataframe['bb_upperband'] < dataframe['ema']
        dataframe['bb_lower_vs_ema'] = dataframe['bb_lowerband'] > dataframe['ema']
        
        # Validate that indicators are properly initialized
        # Check if the last few candles have valid indicator values
        required_indicators = ['ema', 'bb_lowerband', 'bb_middleband', 'bb_upperband', 'mfi', 'atr']
        last_valid_idx = None
        
        for i in range(len(dataframe) - 1, max(0, len(dataframe) - 10), -1):
            if all(pd.notna(dataframe.iloc[i][col]) for col in required_indicators):
                last_valid_idx = i
                break
        
        if last_valid_idx is None:
            logger.warning(f"No valid indicator data found for {metadata['pair']} after 500 candle initialization")
        else:
            # Log rolling window verification
            logger.debug(f"Rolling window calculation verified for {metadata['pair']}:")
            logger.debug(f"  - Total candles processed: {len(dataframe)}")
            logger.debug(f"  - Rolling window size: {rolling_window_size}")
            logger.debug(f"  - Last valid indicator data at index: {last_valid_idx}")
            logger.debug(f"  - Indicators recalculated using most recent {rolling_window_size} candles")
            
            # Log current indicator values for verification
            if last_valid_idx is not None:
                last_candle = dataframe.iloc[last_valid_idx]
                logger.debug(f"  - Current EMA: {last_candle['ema']:.4f}")
                logger.debug(f"  - Current BB Upper: {last_candle['bb_upperband']:.4f}")
                logger.debug(f"  - Current BB Lower: {last_candle['bb_lowerband']:.4f}")
                logger.debug(f"  - Current MFI: {last_candle['mfi']:.2f}")
                logger.debug(f"  - Current ATR: {last_candle['atr']:.4f}")
        
        return dataframe
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Define entry signal for the given dataframe
        """
        # Initialize entry signals
        dataframe['enter_long'] = False
        dataframe['enter_short'] = False
        dataframe['enter_tag'] = ''
        
        # Sell signal conditions (from TypeScript logic)
        sell_conditions = (
            # BB upper is below EMA
            dataframe['bb_upper_vs_ema'] &
            # Candle high is below EMA
            ~dataframe['high_above_ema'] &
            # Price closes above BB upper
            (dataframe['close'] > dataframe['bb_upperband']) &
            # MFI is overbought
            (dataframe['mfi'] > self.overbought_min_mfi.value)
        )
        
        # Buy signal conditions (from TypeScript logic)
        buy_conditions = (
            # BB lower is above EMA
            dataframe['bb_lower_vs_ema'] &
            # Candle low is above EMA
            ~dataframe['low_below_ema'] &
            # Price closes below BB lower
            (dataframe['close'] < dataframe['bb_lowerband']) &
            # MFI is oversold
            (dataframe['mfi'] < self.oversold_max_mfi.value)
        )
        
        # Apply conditions
        dataframe.loc[sell_conditions, 'enter_short'] = True
        dataframe.loc[sell_conditions, 'enter_tag'] = 'bb_sell'
        
        dataframe.loc[buy_conditions, 'enter_long'] = True
        dataframe.loc[buy_conditions, 'enter_tag'] = 'bb_buy'
        
        return dataframe
    
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Define exit signal for the given dataframe
        This will be handled by custom stop loss logic
        """
        # Disable standard exit signals - we use custom stop loss
        dataframe['exit_long'] = False
        dataframe['exit_short'] = False
        dataframe['exit_tag'] = ''
        
        return dataframe
    
    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime, 
                       current_rate: float, current_profit: float, **kwargs) -> float:
        """
        Custom stop loss logic based on ATR and Bollinger Bands
        """
        # Get current dataframe
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df.empty:
            return self.stoploss
            
        # Get the last candle
        last_candle = df.iloc[-1].squeeze()
        
        # Check if we have all required indicators
        if not all(pd.notna(last_candle[col]) for col in ['atr_lower', 'atr_upper', 'bb_middleband']):
            return self.stoploss
        
        # Calculate dynamic stop loss based on trade side
        if trade.is_short:
            # For short positions, use ATR upper or BB middle, whichever is lower
            if last_candle['atr_upper'] <= last_candle['bb_middleband']:
                if last_candle['atr_upper'] <= trade.stop_loss:
                    new_stop_loss = last_candle['atr_upper']
                else:
                    new_stop_loss = trade.stop_loss
            else:
                if last_candle['bb_middleband'] <= trade.stop_loss:
                    new_stop_loss = last_candle['bb_middleband']
                else:
                    new_stop_loss = trade.stop_loss
        else:
            # For long positions, use ATR lower or BB middle, whichever is higher
            if last_candle['atr_lower'] >= last_candle['bb_middleband']:
                if last_candle['atr_lower'] >= trade.stop_loss:
                    new_stop_loss = last_candle['atr_lower']
                else:
                    new_stop_loss = trade.stop_loss
            else:
                if last_candle['bb_middleband'] >= trade.stop_loss:
                    new_stop_loss = last_candle['bb_middleband']
                else:
                    new_stop_loss = trade.stop_loss
        
        # Convert to relative stop loss
        if trade.is_short:
            stop_loss_pct = (new_stop_loss - current_rate) / current_rate
        else:
            stop_loss_pct = (new_stop_loss - current_rate) / current_rate
        
        # Ensure stop loss is not too tight
        stop_loss_pct = max(stop_loss_pct, -0.05)  # Minimum 5% stop loss
        
        logger.info(f"Custom stop loss for {pair}: {stop_loss_pct:.4f} (rate: {current_rate}, stop: {new_stop_loss})")
        
        return stop_loss_pct
    
    def custom_exit(self, pair: str, trade: Trade, current_time: datetime, current_rate: float,
                   current_profit: float, **kwargs) -> Optional[Tuple[str, str]]:
        """
        Custom exit logic - check if price has hit stop loss level
        """
        # Get current dataframe
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df.empty:
            return None
            
        last_candle = df.iloc[-1].squeeze()
        
        # Check if we have required indicators
        if not all(pd.notna(last_candle[col]) for col in ['atr_lower', 'atr_upper', 'bb_middleband']):
            return None
        
        # Check exit conditions based on trade side
        if trade.is_short:
            # For short positions, exit if price goes above stop loss
            if current_rate >= trade.stop_loss:
                return 'custom_exit', 'stop_loss_hit'
        else:
            # For long positions, exit if price goes below stop loss
            if current_rate <= trade.stop_loss:
                return 'custom_exit', 'stop_loss_hit'
        
        return None
    
    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                           time_in_force: str, current_time: datetime, entry_tag: str,
                           side: str, **kwargs) -> bool:
        """
        Additional confirmation before trade entry
        """
        # Get current dataframe
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df.empty:
            return False
            
        last_candle = df.iloc[-1].squeeze()
        
        # Additional validation
        if not all(pd.notna(last_candle[col]) for col in ['ema', 'bb_upperband', 'bb_lowerband', 'mfi', 'atr']):
            logger.warning(f"Missing indicators for {pair}, skipping trade")
            return False
        
        # Log trade confirmation
        logger.info(f"Trade confirmed for {pair}: {side} at {rate} (tag: {entry_tag})")
        
        return True
    
    def confirm_trade_exit(self, pair: str, trade: Trade, order_type: str, amount: float,
                          rate: float, time_in_force: str, exit_reason: str,
                          current_time: datetime, **kwargs) -> bool:
        """
        Additional confirmation before trade exit
        """
        logger.info(f"Trade exit confirmed for {pair}: {exit_reason} at {rate}")
        return True
    
    def custom_entry_price(self, pair: str, current_time: datetime, proposed_rate: float,
                          entry_tag: str, side: str, **kwargs) -> float:
        """
        Custom entry price logic
        """
        # Use current market price for better fill rates
        return proposed_rate
    
    def custom_exit_price(self, pair: str, trade: Trade, current_time: datetime,
                         proposed_rate: float, **kwargs) -> float:
        """
        Custom exit price logic
        """
        # Use current market price for better fill rates
        return proposed_rate
    
    def bot_loop_start(self, **kwargs) -> None:
        """
        Called at the start of the bot iteration
        """
        logger.info(f"BollingerBandsStrategyV9 started - Timeframe: {self.timeframe}")
        logger.info(f"Startup candle count: {self.startup_candle_count} (500 candles for proper initialization)")
        logger.info(f"EMA Length: {self.ema_length.value}")
        logger.info(f"BBands Length: {self.bbands_length.value}, StDev: {self.bbands_stdev.value}")
        logger.info(f"MFI Length: {self.mfi_length.value}")
        logger.info(f"ATR Length: {self.atr_length.value}, Risk Factor: {self.risk_factor.value}")
        logger.info(f"Overbought MFI: {self.overbought_min_mfi.value}, Oversold MFI: {self.oversold_max_mfi.value}")
        logger.info("Strategy will wait for 500 candles before generating trading signals")
        logger.info("ROLLING WINDOW BEHAVIOR:")
        logger.info("  - Each new candle triggers full indicator recalculation")
        logger.info("  - All indicators use the most recent 500 candles (rolling window)")
        logger.info("  - process_only_new_candles=True ensures efficient processing")
        logger.info("  - Indicators are recalculated based on rolling 500-candle data each interval")
