import logging
from functools import reduce
from freqtrade.strategy import IStrategy, IntParameter
from freqtrade.persistence import Trade
from pandas import DataFrame
import talib.abstract as ta
import pandas as pd
import numpy as np
from freqtrade.strategy import DecimalParameter, IntParameter
from typing import Dict, List
from freqtrade.exchange import timeframe_to_minutes

logger = logging.getLogger(__name__)

class RSIStrategy(IStrategy):
    """
    RSI Strategy
    
    This strategy uses RSI (Relative Strength Index) to identify overbought and oversold conditions.
    It enters long positions when RSI is below 30 (oversold) and exits when RSI goes above 70 (overbought).
    """
    
    # Strategy parameters
    minimal_roi = {
        "0": 0.05,      # 5% profit target
        "30": 0.025,    # 2.5% profit target after 30 minutes
        "60": 0.015,    # 1.5% profit target after 60 minutes
        "120": 0.01     # 1% profit target after 120 minutes
    }
    
    stoploss = -0.025  # 2.5% stop loss
    
    # Timeframe for the strategy
    timeframe = '5m'
    
    # RSI parameters
    rsi_period = IntParameter(10, 25, default=14, space="buy")
    rsi_oversold = IntParameter(20, 35, default=30, space="buy")
    rsi_overbought = IntParameter(65, 80, default=70, space="sell")
    
    # Volume parameters
    volume_check = True
    min_volume = 1000000  # Minimum 24h volume in USDT
    
    # Trailing stop parameters
    trailing_stop = True
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.02
    trailing_only_offset_is_reached = True
    
    # Order types
    order_types = {
        'entry': 'limit',
        'exit': 'limit',
        'stoploss': 'market',
        'stoploss_on_exchange': False,
        'stoploss_on_exchange_interval': 60,
    }
    
    # Order time in force
    order_time_in_force = {
        'entry': 'gtc',
        'exit': 'gtc',
    }
    
    # Unfilled order timeout
    unfilledtimeout = {
        'entry': 10,
        'exit': 10,
        'exit_timeout_count': 0,
        'unit': 'minutes'
    }
    
    # Use custom entry/exit prices
    use_entry_price_filter = True
    use_exit_price_filter = True
    
    # Entry price filter
    entry_pricing = {
        'price_side': 'same',
        'use_order_book': True,
        'order_book_top': 1,
    }
    
    # Exit price filter
    exit_pricing = {
        'price_side': 'same',
        'use_order_book': True,
        'order_book_top': 1,
    }
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Add technical indicators to the dataframe
        """
        # RSI
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=self.rsi_period.value)
        
        # Bollinger Bands
        bollinger = ta.BBANDS(dataframe, timeperiod=20, nbdevup=2.0, nbdevdn=2.0, matype=0)
        dataframe['bb_lowerband'] = bollinger['lowerband']
        dataframe['bb_middleband'] = bollinger['middleband']
        dataframe['bb_upperband'] = bollinger['upperband']
        dataframe['bb_width'] = ((dataframe['bb_upperband'] - dataframe['bb_lowerband']) / dataframe['bb_middleband'])
        
        # MACD
        macd = ta.MACD(dataframe['close'], fastperiod=12, slowperiod=26, signalperiod=9)
        dataframe['macd'] = macd[0]  # MACD line
        dataframe['macdsignal'] = macd[1]  # Signal line
        dataframe['macdhist'] = macd[2]  # Histogram
        
        # Volume indicators
        dataframe['volume_mean'] = dataframe['volume'].rolling(window=20).mean()
        dataframe['volume_ratio'] = dataframe['volume'] / dataframe['volume_mean']
        
        # Price change
        dataframe['price_change'] = (dataframe['close'] - dataframe['close'].shift(1)) / dataframe['close'].shift(1)
        
        # Volatility
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)
        dataframe['atr_ratio'] = dataframe['atr'] / dataframe['close']
        
        return dataframe
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Define entry signal for the given dataframe
        """
        conditions = []
        
        # RSI oversold condition
        conditions.append(dataframe['rsi'] < self.rsi_oversold.value)
        
        # Volume condition
        if self.volume_check:
            conditions.append(dataframe['volume_ratio'] > 1.2)
        
        # Bollinger Band condition (price near lower band)
        conditions.append(dataframe['close'] <= dataframe['bb_lowerband'] * 1.02)
        
        # MACD condition (MACD line above signal line)
        conditions.append(dataframe['macd'] > dataframe['macdsignal'])
        
        # Volatility condition (not too volatile)
        conditions.append(dataframe['atr_ratio'] < 0.05)
        
        # Combine all conditions
        if conditions:
            dataframe.loc[
                reduce(lambda x, y: x & y, conditions),
                'enter_long'] = 1
        
        return dataframe
    
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Define exit signal for the given dataframe
        """
        conditions = []
        
        # RSI overbought condition
        conditions.append(dataframe['rsi'] > self.rsi_overbought.value)
        
        # Bollinger Band condition (price near upper band)
        conditions.append(dataframe['close'] >= dataframe['bb_upperband'] * 0.98)
        
        # MACD condition (MACD line below signal line)
        conditions.append(dataframe['macd'] < dataframe['macdsignal'])
        
        # Combine all conditions
        if conditions:
            dataframe.loc[
                reduce(lambda x, y: x & y, conditions),
                'exit_long'] = 1
        
        return dataframe
    
    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: 'datetime', current_rate: float,
                       current_profit: float, **kwargs) -> float:
        """
        Custom stoploss logic, returning the new distance relative to current_rate
        """
        # Dynamic stoploss based on profit
        if current_profit > 0.05:  # 5% profit
            return -0.01  # Tight stoploss
        elif current_profit > 0.02:  # 2% profit
            return -0.015  # Medium stoploss
        else:
            return self.stoploss  # Default stoploss
    
    def custom_entry_price(self, pair: str, current_time: 'datetime', proposed_rate: float,
                          entry_tag: str, side: str, **kwargs) -> float:
        """
        Custom entry price logic
        """
        # Enter slightly below current price for better fill rates
        return proposed_rate * 0.998
    
    def custom_exit_price(self, pair: str, current_time: 'datetime', proposed_rate: float,
                         exit_tag: str, side: str, **kwargs) -> float:
        """
        Custom exit price logic
        """
        # Exit slightly above current price for better fill rates
        return proposed_rate * 1.002
    
    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                           time_in_force: str, current_time: 'datetime', entry_tag: str,
                           side: str, **kwargs) -> bool:
        """
        Additional confirmation before entering a trade
        """
        # Get current dataframe
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = df.iloc[-1].squeeze()
        
        # Additional checks
        if last_candle['volume_ratio'] < 0.8:  # Low volume
            return False
        
        if last_candle['atr_ratio'] > 0.08:  # Too volatile
            return False
        
        return True
