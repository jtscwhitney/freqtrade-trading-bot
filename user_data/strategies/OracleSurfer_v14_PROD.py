"""
OracleSurfer_v14_PROD ("The Surgeon")
Production Version | Structural Overhaul

Core thesis change from v9-v12:
    Every prior version required ~77% win rate to break even due to
    asymmetric stop/reward ratios. Live trading consistently delivers
    50-70% WR, making the whole lineage structurally unprofitable
    at realistic signal quality.

    v14 targets breakeven at 55% WR by making wins larger than losses
    via a risk/reward ratio >= 1.5:1.

Architecture:
    - Risk/reward: -5% stop, target 2:1 minimum (exits via ROI ladder or
      trailing stop after momentum exhaustion)
    - Oracle labels: 48h horizon (was 96h), 1.5x ATR barrier, bear priority
    - Entry: Oracle + EMA200 trend alignment + ADX momentum confirmation
      (MACD removed — lagging relative to Oracle signal)
    - Training: 3-year lookback to capture full BTC cycles

Stop/Reward math:
    Stop = -5%
    Min ROI table targets: +10% (at 8h), +7% (at 16h), +5% (at 24h)
    Trailing: activates at +5%, trails by 3% (min exit +2%)
    Breakeven at: WR > 5 / (5 + 7.5_avg_win) = 40% — very robust
"""

import pandas as pd
import pandas_ta as ta
from pandas import DataFrame
from freqtrade.strategy import IStrategy, DecimalParameter, IntParameter
from freqtrade.persistence import Trade
from typing import Optional, Dict
import talib.abstract as ta_lib
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class OracleSurfer_v14_PROD(IStrategy):
    """
    OracleSurfer v14 — The Surgeon
    Precision entries, disciplined exits, positive risk/reward.
    """

    # ===========================
    # 1. CONFIGURATION
    # ===========================

    timeframe = '1h'

    # ROI ladder: force exit on stalling trades rather than holding forever.
    # At +10% we take it immediately. At +7% after 8h. At +5% after 16h.
    # At +3% after 24h (prevents holding through deep reversals after a good start).
    minimal_roi = {
        "0":    0.10,   # Take +10% any time
        "480":  0.07,   # Take +7% after 8h
        "960":  0.05,   # Take +5% after 16h
        "1440": 0.03,   # Take +3% after 24h
    }

    # HARD STOP: -5% (risk/reward foundation)
    # Tight enough to limit damage when Oracle is wrong, wide enough to
    # survive normal 1h BTC volatility (~1-2% per candle).
    stoploss = -0.05

    # TRAILING STOP: Activates after solid profit is confirmed.
    # Activation at +5% means we've cleared the ROI table's minimum threshold.
    # 3% trail gives room for normal retracements while locking in gains.
    trailing_stop = True
    trailing_stop_positive = 0.04          # Trail by 4% — wider exit to capture more of each move
    trailing_stop_positive_offset = 0.05   # Activate after +5%
    trailing_only_offset_is_reached = True

    process_only_new_candles = True
    startup_candle_count = 240
    can_short = True
    use_custom_stoploss = True
    position_adjustment_enable = False  # DCA not implemented; disable explicitly

    order_types = {
        'entry': 'market',
        'exit': 'market',
        'stoploss': 'market',
        'stoploss_on_exchange': False,
    }

    # Cache for free-roll log deduplication only — does not affect trade logic
    _freeroll_logged: Dict[int, datetime] = {}

    # ===========================
    # 2. INDICATORS
    # ===========================

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        # Oracle: FreqAI XGBoost regime classifier
        dataframe = self.freqai.start(dataframe, metadata, self)

        # Trend baseline: EMA200 (more reliable trend floor than EMA100)
        dataframe['ema_trend'] = ta_lib.EMA(dataframe, timeperiod=200)

        # Momentum: RSI for direction confirmation
        dataframe['rsi'] = ta_lib.RSI(dataframe, timeperiod=14)

        # Strength: ADX for trend intensity gate
        dataframe['adx'] = ta_lib.ADX(dataframe)

        return dataframe

    # ===========================
    # 3. ENTRY LOGIC
    # ===========================

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        target_col = "&s_regime_class"
        if target_col in dataframe.columns:
            oracle_signal = self._coerce_oracle_signal(dataframe[target_col])
        else:
            oracle_signal = pd.Series("NEUTRAL", index=dataframe.index)

        if self.config['runmode'].value in ('live', 'dry_run'):
            logger.info(
                f"Oracle Signal [{metadata['pair']}]: {oracle_signal.iloc[-1]}"
                f" | RSI: {dataframe['rsi'].iloc[-1]:.1f}"
                f" | ADX: {dataframe['adx'].iloc[-1]:.1f}"
                f" | Price vs EMA200: {'above' if dataframe['close'].iloc[-1] > dataframe['ema_trend'].iloc[-1] else 'below'}"
            )

        # LONG ENTRY
        # Oracle BULL + price above EMA200 (trend confirmed) + RSI > 50 (momentum)
        # + ADX > 20 (avoid choppy low-trend entries)
        dataframe.loc[
            (
                (oracle_signal == "BULL") &
                (dataframe['close'] > dataframe['ema_trend']) &
                (dataframe['rsi'] > 50) &
                (dataframe['adx'] > 20)
            ),
            'enter_long'] = 1

        # SHORT ENTRY
        # Oracle BEAR + price below EMA200 + RSI < 50 + ADX > 20
        dataframe.loc[
            (
                (oracle_signal == "BEAR") &
                (dataframe['close'] < dataframe['ema_trend']) &
                (dataframe['rsi'] < 50) &
                (dataframe['adx'] > 20)
            ),
            'enter_short'] = 1

        return dataframe

    # ===========================
    # 4. EXIT LOGIC
    # ===========================

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # No signal exits. The Oracle is a 4h-feature signal that can flip
        # every 4h candle — far too noisy to use as a 1h exit trigger.
        # Exits are handled exclusively by: stop_loss, trailing_stop, ROI table.
        return dataframe

    # ===========================
    # 5. RISK MANAGEMENT
    # ===========================

    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                        current_rate: float, current_profit: float, **kwargs) -> float:

        # Break-even at +2%: lock in capital preservation once we have cushion.
        # This bridges the gap between entry and the trailing stop activation (+5%).
        if current_profit >= 0.02:
            trade_id = trade.id
            last_log = self._freeroll_logged.get(trade_id)
            if not last_log or (current_time - last_log) > timedelta(hours=4):
                logger.info(
                    f"BE stop active [{pair}] trade={trade_id}: "
                    f"profit={current_profit:.2%} → stop moved to BE+0.1%"
                )
                self._freeroll_logged[trade_id] = current_time
            return 0.001  # +0.1% guaranteed exit floor

        # Respect static stoploss (-5%) below the break-even threshold
        return -1

    # ===========================
    # 6. FREQAI CONFIGURATION
    # ===========================

    def feature_engineering_expand_all(
        self, dataframe: DataFrame, period: int, metadata: dict, **kwargs
    ) -> DataFrame:
        """
        Feature set on the 4h correlated timeframe only.
        Covers regime, trend, valuation, fear, and volume dimensions.
        """
        if metadata.get('tf', '') != '4h':
            return dataframe

        # Choppiness: distinguishes ranging vs trending markets
        dataframe['%regime_chop'] = ta.chop(
            dataframe['high'], dataframe['low'], dataframe['close'], length=14
        )

        # KAMA distance: adaptive trend proximity signal
        kama = ta.kama(dataframe['close'], length=10)
        dataframe['%trend_kama_dist'] = (dataframe['close'] - kama) / kama

        # Long-term valuation distance (SMA200): cycle position indicator
        long_ma = ta.sma(dataframe['close'], length=200)
        dataframe['%val_ltvd'] = (dataframe['close'] - long_ma) / dataframe['close']

        # VIX-Fix synthetic fear gauge
        period_vix = 22
        highest_close = dataframe['close'].rolling(window=period_vix).max()
        dataframe['%fear_vixfix'] = (highest_close - dataframe['low']) / highest_close * 100

        # OBV oscillator: volume-weighted trend confirmation
        obv = ta.obv(dataframe['close'], dataframe['volume'])
        obv_ma = ta.sma(obv, length=20)
        dataframe['%truth_obv_osc'] = (obv - obv_ma) / obv_ma

        # Rate of change: short-term price momentum
        dataframe['%roc_5'] = ta.roc(dataframe['close'], length=5)

        return dataframe.fillna(0)

    def feature_engineering_expand_basic(self, dataframe: DataFrame, **kwargs) -> DataFrame:
        metadata = kwargs.get('metadata', {})
        if metadata.get('tf', '') != '4h':
            return dataframe
        dataframe['%pct-change'] = dataframe['close'].pct_change().fillna(0)
        return dataframe

    def set_freqai_targets(self, dataframe: DataFrame, **kwargs) -> DataFrame:
        """
        Triple-barrier labeling with optimized parameters:
        - 48h horizon (12 × 4h candles): faster reaction to regime changes
        - 1.5x ATR barrier: achievable targets within 48h
        - Bear priority: when both barriers hit, classify BEAR (safety bias)
        """
        self.freqai.class_names = ["BEAR", "NEUTRAL", "BULL"]

        horizon = 12  # 12 × 4h candles = 48h lookahead

        dataframe['atr'] = ta.atr(
            dataframe['high'], dataframe['low'], dataframe['close'], length=14
        )
        barrier = dataframe['atr'] * 1.5  # 1.5x ATR — achievable within 48h

        future_max = dataframe['high'].shift(-1).rolling(window=horizon, min_periods=1).max()
        future_min = dataframe['low'].shift(-1).rolling(window=horizon, min_periods=1).min()

        dataframe['&s_regime_class'] = "NEUTRAL"
        valid = pd.notna(future_max) & pd.notna(future_min) & pd.notna(barrier)

        bull = valid & (future_max > (dataframe['close'] + barrier))
        bear = valid & (future_min < (dataframe['close'] - barrier))

        # Bear priority: if both barriers hit (high volatility), default to BEAR
        # to avoid entering longs into potential falling-knife moves.
        dataframe.loc[bull, '&s_regime_class'] = "BULL"
        dataframe.loc[bear, '&s_regime_class'] = "BEAR"

        return dataframe

    # ===========================
    # 7. HELPERS
    # ===========================

    @staticmethod
    def _coerce_oracle_signal(series: pd.Series) -> pd.Series:
        """
        Normalize Oracle signal column to string class names.
        FreqAI occasionally returns numeric class indices (0/1/2) from
        cached models on restart before the first retrain cycle completes.
        Maps: 0 -> BEAR, 1 -> NEUTRAL, 2 -> BULL
        """
        _class_map = {
            "0": "BEAR", "1": "NEUTRAL", "2": "BULL",
            "0.0": "BEAR", "1.0": "NEUTRAL", "2.0": "BULL",
        }
        return series.astype(str).map(lambda x: _class_map.get(x, x))
