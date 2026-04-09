"""
VasilyMTF — порт стратегии Василия для Freqtrade бэктестинга.

Логика:
- Multi-Timeframe Confluence: 1h (основной) + informative 4h
- TA Score: RSI, MACD, EMA(20/50), Bollinger, ADX, StochRSI, Volume
- Вход при abs(weighted_score) >= 50
- SL 2%, TP 4%, leverage 5x
- Динамическая позиция: 10% при score 50-69, 20% при ≥70
"""

from freqtrade.strategy.interface import IStrategy
from freqtrade.strategy import (DecimalParameter, IntParameter,
                                 informative)
import talib.abstract as ta
from pandas import DataFrame
import numpy as np


class VasilyMTF(IStrategy):
    """Vasily Multi-Timeframe Confluence Strategy."""

    # ─── Базовые параметры ─────────────────────────────────────────
    INTERFACE_VERSION = 2

    minimal_roi = {
        "0": 0.04,   # 4% TP (аналог нашего TP_PCT)
        "1440": 0.0  # через 24h — закрыть по любой цене (MAX_HOLD_HOURS)
    }

    stoploss = -0.02  # 2% SL (аналог SL_PCT)

    # Таймфрейм
    timeframe = '1h'
    informative_timeframe = '4h'

    # Cooldown — минимум 2 свечи (2h на 1h таймфрейме)
    process_only_new_candles = True

    # Не продавать при убытке (SL делает свою работу)
    use_sell_signal = True
    sell_profit_only = False
    ignore_roi_if_buy_signal = False

    # Порог net_score
    net_score_threshold = 50
    net_score_high = 70

    # ─── Informative pairs (4h) ────────────────────────────────────
    def informative_pairs(self):
        pairs = self.dp.current_whitelist()
        return [(pair, '4h') for pair in pairs]

    # ─── Индикаторы ────────────────────────────────────────────────
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """Рассчитываем все индикаторы из нашего technical_analysis.py."""

        # === 1h indicators ===

        # RSI (вклад: -15..+15)
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)

        # MACD (вклад: -25..+25)
        macd = ta.MACD(dataframe, fastperiod=12, slowperiod=26, signalperiod=9)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        dataframe['macdhist'] = macd['macdhist']

        # EMA 20, 50 (вклад: -25..+25)
        dataframe['ema20'] = ta.EMA(dataframe, timeperiod=20)
        dataframe['ema50'] = ta.EMA(dataframe, timeperiod=50)

        # Bollinger Bands (вклад: -15..+15)
        bb = ta.BBANDS(dataframe, timeperiod=20, nbdevup=2.0, nbdevdn=2.0)
        dataframe['bb_upper'] = bb['upperband']
        dataframe['bb_middle'] = bb['middleband']
        dataframe['bb_lower'] = bb['lowerband']
        dataframe['bb_width'] = (dataframe['bb_upper'] - dataframe['bb_lower']) / dataframe['bb_middle'] * 100
        bb_range = dataframe['bb_upper'] - dataframe['bb_lower']
        dataframe['bb_position'] = np.where(
            bb_range > 0,
            (dataframe['close'] - dataframe['bb_lower']) / bb_range,
            0.5
        )

        # ADX (вклад: -15..+15)
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=14)
        dataframe['plus_di'] = ta.PLUS_DI(dataframe, timeperiod=14)
        dataframe['minus_di'] = ta.MINUS_DI(dataframe, timeperiod=14)

        # Stochastic RSI (вклад: -10..+10 за зону + -10..+10 за кросс)
        stochrsi = ta.STOCHRSI(dataframe, timeperiod=14, fastk_period=14,
                                fastd_period=3, fastd_matype=0)
        dataframe['stochrsi_k'] = stochrsi['fastk']
        dataframe['stochrsi_d'] = stochrsi['fastd']

        # Volume analysis (вклад: -15..+15)
        dataframe['vol_sma20'] = ta.SMA(dataframe['volume'], timeperiod=20)
        dataframe['vol_sma5'] = ta.SMA(dataframe['volume'], timeperiod=5)

        # === Скоринг 1h ===
        dataframe['score_1h'] = self._calc_score(dataframe)

        # === 4h indicators (informative) ===
        inf_df = self.dp.get_pair_dataframe(
            pair=metadata['pair'], timeframe='4h'
        )
        if len(inf_df) > 0:
            inf_df['rsi_4h'] = ta.RSI(inf_df, timeperiod=14)

            macd_4h = ta.MACD(inf_df, fastperiod=12, slowperiod=26, signalperiod=9)
            inf_df['macd_4h'] = macd_4h['macd']
            inf_df['macdhist_4h'] = macd_4h['macdhist']

            inf_df['ema20_4h'] = ta.EMA(inf_df, timeperiod=20)
            inf_df['ema50_4h'] = ta.EMA(inf_df, timeperiod=50)

            bb_4h = ta.BBANDS(inf_df, timeperiod=20, nbdevup=2.0, nbdevdn=2.0)
            inf_df['bb_upper_4h'] = bb_4h['upperband']
            inf_df['bb_lower_4h'] = bb_4h['lowerband']
            inf_df['bb_middle_4h'] = bb_4h['middleband']
            bb_range_4h = inf_df['bb_upper_4h'] - inf_df['bb_lower_4h']
            inf_df['bb_position_4h'] = np.where(
                bb_range_4h > 0,
                (inf_df['close'] - inf_df['bb_lower_4h']) / bb_range_4h,
                0.5
            )

            inf_df['adx_4h'] = ta.ADX(inf_df, timeperiod=14)
            inf_df['plus_di_4h'] = ta.PLUS_DI(inf_df, timeperiod=14)
            inf_df['minus_di_4h'] = ta.MINUS_DI(inf_df, timeperiod=14)

            stochrsi_4h = ta.STOCHRSI(inf_df, timeperiod=14, fastk_period=14,
                                       fastd_period=3, fastd_matype=0)
            inf_df['stochrsi_k_4h'] = stochrsi_4h['fastk']
            inf_df['stochrsi_d_4h'] = stochrsi_4h['fastd']

            inf_df['vol_sma20_4h'] = ta.SMA(inf_df['volume'], timeperiod=20)
            inf_df['vol_sma5_4h'] = ta.SMA(inf_df['volume'], timeperiod=5)

            # Скоринг 4h
            inf_df['score_4h'] = self._calc_score_4h(inf_df)

            # Merge 4h в 1h
            dataframe = self._merge_informative(dataframe, inf_df)

        if 'score_4h' not in dataframe.columns:
            dataframe['score_4h'] = 0

        # === Weighted MTF Score ===
        # Веса: 1h = 1, 4h = 2 (аналог нашего analyze_multi_timeframe)
        dataframe['weighted_score'] = (
            dataframe['score_1h'] * 1 + dataframe['score_4h'] * 2
        ) / 3

        dataframe['net_score'] = dataframe['weighted_score'].abs()

        return dataframe

    def _calc_score(self, df: DataFrame) -> DataFrame:
        """Рассчитать TA-скор на основе логики full_analysis()."""
        score = np.zeros(len(df))

        # RSI: -15..+15
        score = np.where(df['rsi'] > 70, score - 15, score)
        score = np.where(df['rsi'] < 30, score + 15, score)
        score = np.where((df['rsi'] > 55) & (df['rsi'] <= 70), score + 5, score)
        score = np.where((df['rsi'] < 45) & (df['rsi'] >= 30), score - 5, score)

        # MACD: -25..+25
        prev_hist = df['macdhist'].shift(1)
        score = np.where((df['macdhist'] > 0) & (prev_hist <= 0), score + 25, score)  # bullish cross
        score = np.where((df['macdhist'] < 0) & (prev_hist >= 0), score - 25, score)  # bearish cross
        score = np.where((df['macdhist'] > 0) & (prev_hist > 0), score + 10, score)   # bullish
        score = np.where((df['macdhist'] < 0) & (prev_hist < 0), score - 10, score)   # bearish

        # EMA: -25..+25
        score = np.where(
            (df['close'] > df['ema20']) & (df['ema20'] > df['ema50']),
            score + 15, score
        )
        score = np.where(
            (df['close'] < df['ema20']) & (df['ema20'] < df['ema50']),
            score - 15, score
        )
        # Golden/Death cross
        prev_ema20 = df['ema20'].shift(1)
        prev_ema50 = df['ema50'].shift(1)
        score = np.where((prev_ema20 <= prev_ema50) & (df['ema20'] > df['ema50']), score + 20, score)
        score = np.where((prev_ema20 >= prev_ema50) & (df['ema20'] < df['ema50']), score - 20, score)

        # ADX: -15..+15
        score = np.where(
            (df['adx'] > 25) & (df['plus_di'] > df['minus_di']),
            score + 15, score
        )
        score = np.where(
            (df['adx'] > 25) & (df['minus_di'] > df['plus_di']),
            score - 15, score
        )

        # StochRSI: -10..+10
        score = np.where(df['stochrsi_k'] < 20, score + 10, score)   # oversold
        score = np.where(df['stochrsi_k'] > 80, score - 10, score)   # overbought
        prev_k = df['stochrsi_k'].shift(1)
        prev_d = df['stochrsi_d'].shift(1)
        score = np.where((prev_k <= prev_d) & (df['stochrsi_k'] > df['stochrsi_d']), score + 10, score)
        score = np.where((prev_k >= prev_d) & (df['stochrsi_k'] < df['stochrsi_d']), score - 10, score)

        # Bollinger: -15..+15
        score = np.where(df['bb_position'] < 0.05, score + 15, score)   # oversold
        score = np.where(df['bb_position'] > 0.95, score - 15, score)   # overbought

        # Volume: -15..+15
        vol_ratio = np.where(df['vol_sma20'] > 0, df['vol_sma5'] / df['vol_sma20'], 1)
        # Нужно определить buy volume %
        # Простая аппроксимация: если close > open — buying pressure
        buy_pressure = df['close'] > df['open']
        score = np.where(
            (vol_ratio > 1.5) & buy_pressure,
            score + 15, score
        )
        score = np.where(
            (vol_ratio > 1.5) & ~buy_pressure,
            score - 15, score
        )

        return np.clip(score, -100, 100)

    def _calc_score_4h(self, df: DataFrame) -> DataFrame:
        """Скоринг для 4h — та же логика, другие колонки."""
        score = np.zeros(len(df))

        # RSI
        score = np.where(df['rsi_4h'] > 70, score - 15, score)
        score = np.where(df['rsi_4h'] < 30, score + 15, score)
        score = np.where((df['rsi_4h'] > 55) & (df['rsi_4h'] <= 70), score + 5, score)
        score = np.where((df['rsi_4h'] < 45) & (df['rsi_4h'] >= 30), score - 5, score)

        # MACD
        prev_hist = df['macdhist_4h'].shift(1)
        score = np.where((df['macdhist_4h'] > 0) & (prev_hist <= 0), score + 25, score)
        score = np.where((df['macdhist_4h'] < 0) & (prev_hist >= 0), score - 25, score)
        score = np.where((df['macdhist_4h'] > 0) & (prev_hist > 0), score + 10, score)
        score = np.where((df['macdhist_4h'] < 0) & (prev_hist < 0), score - 10, score)

        # EMA
        score = np.where(
            (df['close'] > df['ema20_4h']) & (df['ema20_4h'] > df['ema50_4h']),
            score + 15, score
        )
        score = np.where(
            (df['close'] < df['ema20_4h']) & (df['ema20_4h'] < df['ema50_4h']),
            score - 15, score
        )

        # ADX
        score = np.where(
            (df['adx_4h'] > 25) & (df['plus_di_4h'] > df['minus_di_4h']),
            score + 15, score
        )
        score = np.where(
            (df['adx_4h'] > 25) & (df['minus_di_4h'] > df['plus_di_4h']),
            score - 15, score
        )

        # StochRSI
        score = np.where(df['stochrsi_k_4h'] < 20, score + 10, score)
        score = np.where(df['stochrsi_k_4h'] > 80, score - 10, score)

        # Bollinger
        score = np.where(df['bb_position_4h'] < 0.05, score + 15, score)
        score = np.where(df['bb_position_4h'] > 0.95, score - 15, score)

        return np.clip(score, -100, 100)

    def _merge_informative(self, dataframe: DataFrame, inf_df: DataFrame) -> DataFrame:
        """Merge 4h score into 1h dataframe."""
        inf_df = inf_df[['date', 'score_4h']].copy()
        inf_df.columns = ['date_4h', 'score_4h']

        # Forward-fill: каждая 4h свеча покрывает 4 свечи 1h
        dataframe = dataframe.copy()
        dataframe['date_4h'] = dataframe['date'].dt.floor('4h')
        inf_df['date_4h'] = inf_df['date_4h'].dt.floor('4h')

        dataframe = dataframe.merge(inf_df, on='date_4h', how='left', suffixes=('', '_inf'))
        dataframe['score_4h'] = dataframe['score_4h'].fillna(0)
        dataframe.drop(columns=['date_4h'], inplace=True, errors='ignore')

        return dataframe

    # ─── Вход: BUY ─────────────────────────────────────────────────
    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Вход в LONG:
        - weighted_score > 0 (бычий сигнал)
        - net_score >= 50 (порог)
        - ADX не блокирует (если ADX > 30 и тренд вниз — не покупать)
        - StochRSI < 80 (не перекуплен)
        """
        dataframe.loc[
            (
                (dataframe['weighted_score'] > 0) &
                (dataframe['net_score'] >= self.net_score_threshold) &
                # ADX blocker: не лонговать при сильном даунтренде
                ~((dataframe['adx'] > 30) & (dataframe['minus_di'] > dataframe['plus_di'])) &
                # StochRSI: не лонговать при перекупленности
                (dataframe['stochrsi_k'] < 80) &
                (dataframe['volume'] > 0)
            ),
            'buy'] = 1

        return dataframe

    # ─── Выход: SELL ───────────────────────────────────────────────
    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Выход из LONG:
        - weighted_score переворачивается в сильный SHORT (< -50)
        - Или ROI/SL сработает автоматически
        """
        dataframe.loc[
            (
                (dataframe['weighted_score'] < -self.net_score_threshold) &
                (dataframe['volume'] > 0)
            ),
            'sell'] = 1

        return dataframe

    # ─── Кастомный стейкинг (динамическая позиция) ─────────────────
    def custom_stake_amount(self, pair: str, current_time, current_rate: float,
                           proposed_stake: float, min_stake, max_stake,
                           entry_tag, **kwargs) -> float:
        """
        Динамическая позиция:
        - net_score >= 70 → 20% баланса
        - net_score 50-69 → 10% баланса
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if len(dataframe) > 0:
            last = dataframe.iloc[-1]
            net_score = abs(last.get('weighted_score', 0))
            if net_score >= self.net_score_high:
                return proposed_stake * 2  # удвоить стандартный размер
        return proposed_stake

    # ─── Leverage ──────────────────────────────────────────────────
    def leverage(self, pair: str, current_time, current_rate: float,
                 proposed_leverage: float, max_leverage: float,
                 side: str, **kwargs) -> float:
        """Фиксированное плечо 5x."""
        return 5.0
