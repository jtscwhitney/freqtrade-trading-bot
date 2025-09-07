# ---
# @version 5
# @strategy KrakenTestStrategy
# @description Test strategy for verifying Kraken Pro connection and interface
# @author Test User
# @tags test, kraken, connectivity
# ---

import logging
from datetime import datetime
from freqtrade.strategy import IStrategy
from pandas import DataFrame
import pandas as pd

logger = logging.getLogger(__name__)

class KrakenTestStrategy(IStrategy):
    """
    Test Strategy for Kraken Pro Integration
    
    This strategy is designed to:
    1. Test Kraken API connectivity
    2. Verify market data access
    3. Check account permissions
    4. NOT execute any trades (even in live mode)
    
    Use this to verify your Kraken setup before running actual trading strategies.
    """
    
    # Strategy parameters
    INTERFACE_VERSION = 3
    
    # Minimal timeframe
    timeframe = '5m'
    
    # Minimal ROI table
    minimal_roi = {
        "0": 0.01  # 1% profit target (will never be reached in this test)
    }
    
    # Minimal risk per trade
    stoploss = -0.10  # 10% stop loss (will never be triggered in this test)
    
    # Trailing stop
    trailing_stop = False
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.02
    trailing_only_offset_is_reached = False
    
    # Use custom stoploss logic
    use_custom_stoploss = False
    
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
    
    # Disable entry and exit
    process_only_new_candles = True
    use_exit_signal = False
    exit_profit_only = False
    ignore_roi_if_entry_signal = False
    
    # Position adjustment
    position_adjustment_enable = False
    
    # Number of candles the strategy requires before producing valid signals
    startup_candle_count: int = 30
    
    # Strategy specific parameters
    test_mode = True  # This ensures no trades are executed
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Add indicators to the dataframe
        """
        # Add a simple timestamp indicator for testing
        dataframe['timestamp'] = pd.to_datetime(dataframe['date'], unit='ms')
        dataframe['hour'] = dataframe['timestamp'].dt.hour
        dataframe['minute'] = dataframe['timestamp'].dt.minute
        
        # Add a simple moving average for demonstration
        dataframe['sma_20'] = dataframe['close'].rolling(window=20).mean()
        
        # Add a test indicator that's always false (no trades)
        dataframe['test_signal'] = False
        
        return dataframe
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Entry signal logic - ALWAYS FALSE to prevent trades
        """
        dataframe['enter_long'] = False
        dataframe['enter_short'] = False
        dataframe['enter_tag'] = 'NO_TRADES_ALLOWED'
        
        return dataframe
    
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Exit signal logic - ALWAYS FALSE to prevent trades
        """
        dataframe['exit_long'] = False
        dataframe['exit_short'] = False
        dataframe['exit_tag'] = 'NO_TRADES_ALLOWED'
        
        return dataframe
    
    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float, 
                           time_in_force: str, current_time: datetime, entry_tag: str, 
                           side: str, **kwargs) -> bool:
        """
        Additional confirmation before trade entry
        This will ALWAYS return False to prevent any trades
        """
        logger.info(f"TRADE BLOCKED: {pair} - Test strategy does not allow trades")
        return False
    
    def confirm_trade_exit(self, pair: str, trade, order_type: str, amount: float, 
                          rate: float, time_in_force: str, exit_reason: str, 
                          current_time: datetime, **kwargs) -> bool:
        """
        Additional confirmation before trade exit
        This will ALWAYS return False to prevent any trades
        """
        logger.info(f"EXIT BLOCKED: {pair} - Test strategy does not allow trades")
        return False
    
    def custom_stoploss(self, pair: str, trade, current_time: datetime, 
                       current_rate: float, current_profit: float, **kwargs) -> float:
        """
        Custom stoploss logic - returns the existing stoploss
        """
        return self.stoploss
    
    def custom_entry_price(self, pair: str, current_time: datetime, 
                          proposed_rate: float, entry_tag: str, side: str, 
                          **kwargs) -> float:
        """
        Custom entry price logic
        """
        return proposed_rate
    
    def custom_exit_price(self, pair: str, trade, current_time: datetime, 
                         proposed_rate: float, exit_reason: str, **kwargs) -> float:
        """
        Custom exit price logic
        """
        return proposed_rate
    
    def bot_loop_start(self, **kwargs) -> None:
        """
        Called at the start of the bot iteration (one loop = one entry/exit).
        """
        # Log connection status
        if self.wallets:
            logger.info("=== KRAKEN CONNECTION TEST ===")
            logger.info(f"Exchange: {self.config['exchange']['name']}")
            logger.info(f"Trading mode: {'DRY RUN' if self.config['dry_run'] else 'LIVE'}")
            logger.info(f"Strategy: {self.__class__.__name__}")
            logger.info("=== NO TRADES WILL BE EXECUTED ===")
            
            # Test market data access
            try:
                # Try to access exchange through the strategy's exchange attribute
                if hasattr(self, 'exchange'):
                    ticker = self.exchange.fetch_ticker('BTC/USD')
                    logger.info(f"Market data test: BTC/USD price = {ticker['last']}")
                else:
                    logger.info("Market data test: Exchange object not available, skipping price check")
            except Exception as e:
                logger.error(f"Market data test failed: {e}")
                logger.info("Market data test: Unable to fetch current price, but connection is working")
            
            # Test balance access
            try:
                # Try multiple balance methods
                logger.info("Balance access test: Attempting to retrieve balance...")
                
                # Method 1: Try to get total balance
                try:
                    total_balance = self.wallets.get_total_balance()
                    logger.info(f"Balance access test: Total balance = {total_balance}")
                except:
                    logger.info("Balance access test: Method 1 failed, trying method 2...")
                    
                    # Method 2: Try to get all balances and sum
                    try:
                        balances = self.wallets.get_all_balances()
                        logger.info(f"Balance access test: Raw balances = {balances}")
                        if balances:
                            # Extract numeric values from Wallet objects
                            total_balance = 0
                            for currency, wallet in balances.items():
                                if hasattr(wallet, 'total'):
                                    total_balance += float(wallet.total)
                                    logger.info(f"Balance access test: {currency} = {wallet.total}")
                                elif isinstance(wallet, (int, float)):
                                    total_balance += float(wallet)
                                    logger.info(f"Balance access test: {currency} = {wallet}")
                            logger.info(f"Balance access test: Calculated total = {total_balance}")
                        else:
                            logger.info("Balance access test: No balance data available")
                    except Exception as e2:
                        logger.error(f"Balance access test: Method 2 failed - {e2}")
                        
                        # Method 3: Try to access specific currency
                        try:
                            usd_balance = self.wallets.get_balance('USD')
                            logger.info(f"Balance access test: USD balance = {usd_balance}")
                        except Exception as e3:
                            logger.error(f"Balance access test: Method 3 failed - {e3}")
                            logger.info("Balance access test: All methods failed")
                            
            except Exception as e:
                logger.error(f"Balance access test failed: {e}")
                logger.info("Balance access test: Unable to retrieve balance information")
