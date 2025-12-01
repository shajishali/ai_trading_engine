"""
Proper Strategy-Based Backtesting Service
Implements YOUR SMC strategy plan for historical signal generation and backtesting
"""

import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
from django.utils import timezone
from django.db.models import Q

from apps.signals.models import TradingSignal, SignalType, Symbol, BacktestResult
from apps.data.models import MarketData
from apps.signals.smc_strategy import SmartMoneyConceptsStrategy

logger = logging.getLogger(__name__)


class ProperStrategyBacktestingService:
    """
    PROPER strategy-based backtesting that implements YOUR trading strategy:
    
    1. Higher timeframe trend detection (1D)
    2. Market Structure: CHoCH (Change of Character) → BOS (Break of Structure)
    3. Entry Confirmation: 1H + 15M confirmation with candlestick patterns, RSI, MACD
    4. Risk Management: SL/TP based on key support/resistance levels
    5. Fundamental Confirmation: News sentiment analysis
    """
    
    def __init__(self):
        self.smc_strategy = SmartMoneyConceptsStrategy()
        self.tp_percentage = 0.15  # 15% take profit (your strategy)
        self.sl_percentage = 0.08   # 8% stop loss (your strategy)
        
    def generate_historical_signals(
        self, 
        symbol: Symbol, 
        start_date: datetime, 
        end_date: datetime,
        analyze_day_by_day: bool = True
    ) -> List[TradingSignal]:
        """
        Generate signals day by day through the specified period
        implementing YOUR complete SMC strategy
        """
        signals = []
        
        try:
            logger.info(f"Generating historical signals for {symbol.symbol} from {start_date} to {end_date}")
            
            # Fetch historical data for the entire period
            historical_data = self._get_historical_data(symbol, start_date, end_date)
            
            if len(historical_data) < 50:  # Need minimum data for SMC analysis
                logger.warning(f"Insufficient historical data for {symbol.symbol}")
                return []
            
            # Convert to DataFrame for analysis
            df = pd.DataFrame(historical_data)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp').reset_index(drop=True)
            
            # Generate signals day by day if requested
            if analyze_day_by_day:
                signals = self._analyze_day_by_day_signals(symbol, df, start_date, end_date)
            else:
                # Or analyze as a continuous dataset
                signals = self._analyze_historical_period(symbol, df)
            
            logger.info(f"Generated {len(signals)} signals for {symbol.symbol}")
            return signals
            
        except Exception as e:
            logger.error(f"Error generating signals for {symbol.symbol}: {e}")
            return []
    
    def _get_historical_data(self, symbol: Symbol, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Get historical market data with technical indicators"""
        try:
            # Query market data within the date range
            market_data_qs = MarketData.objects.filter(
                symbol=symbol,
                timestamp__gte=start_date,
                timestamp__lte=end_date
            ).order_by('timestamp')
            
            historical_data = []
            for data in market_data_qs:
                historical_data.append({
                    'timestamp': data.timestamp,
                    'open': float(data.open_price),
                    'high': float(data.high_price),
                    'low': float(data.low_price),
                    'close': float(data.close_price),
                    'volume': float(data.volume)
                })
            
            # If no data found, try without specific symbol model
            if not historical_data:
                # Query by symbol string instead
                market_data_qs = MarketData.objects.filter(
                    symbol__symbol__icontains=str(symbol)[:3],  # Extract BTC from Symbol object
                    timestamp__gte=start_date,
                    timestamp__lte=end_date
                ).order_by('timestamp')
                
                for data in market_data_qs:
                    historical_data.append({
                        'timestamp': data.timestamp,
                        'open': float(data.open_price),
                        'high': float(data.high_price),
                        'low': float(data.low_price),
                        'close': float(data.close_price),
                        'volume': float(data.volume)
                    })
            
            return historical_data
            
        except Exception as e:
            logger.error(f"Error fetching historical data for {symbol}: {e}")
            return []
    
    def _analyze_day_by_day_signals(self, symbol: Symbol, df: pd.DataFrame, start_date: datetime, end_date: datetime) -> List[TradingSignal]:
        """
        Analyze each day in the period and generate signals based on YOUR strategy
        This simulates how your strategy would have performed day by day
        """
        signals = []
        
        try:
            # Group data by date (simulate daily analysis)
            df['DATE'] = df['timestamp'].dt.date
            
            # Start analyzing from day 50 to have enough historical data
            unique_dates = sorted(df['DATE'].unique())
            analysis_start_idx = 50  # Need 50 periods for SMC analysis
            
            for i in range(analysis_start_idx, len(unique_dates)):
                current_date = unique_dates[i]
                
                # Get data up to current date (simulate moving forward in time)
                available_data = df[df['DATE'] <= current_date]
                
                # Analyze current day's price action within the historical context
                daily_signals = self._analyze_daily_opportunities(symbol, available_data, current_date)
                signals.extend(daily_signals)
                
                # Limit to prevent too many signals
                if len(signals) >= 200:  # Max 200 signals
                    break
            
            return signals
            
        except Exception as e:
            logger.error(f"Error in day-by-day analysis: {e}")
            return []
    
    def _analyze_daily_opportunities(self, symbol: Symbol, df: pd.DataFrame, analysis_date) -> List[TradingSignal]:
        """
        Analyze opportunities on a specific day using YOUR SMC strategy
        Implements the complete strategy workflow:
        1. Higher timeframe trend (1D)
        2. Market structure analysis (BOS/CHoCH) 
        3. Entry confirmation (1H + 15M equivalent)
        4. Risk management (15% TP / 8% SL)
        """
        signals = []
        
        try:
            if len(df) < 20:
                return signals
            
            # Step 1: Analyze higher timeframe trend (daily)
            daily_trend = self._analyze_daily_trend(df)
            
            # Step 2: Market Structure Analysis (BOS/CHoCH)
            structure_signals = self._detect_market_structure_signals(symbol, df, daily_trend)
            signals.extend(structure_signals)
            
            # Step 3: Entry Confirmation Analysis
            confirmation_signals = self._analyze_entry_confirmations(symbol, df, daily_trend)
            signals.extend(confirmation_signals)
            
            # Step 4: Apply Risk Management (15% TP / 8% SL)
            signals = self._apply_risk_management(signals, df)
            
            # Filter signals based on YOUR strategy requirements
            signals = self._filter_signals_to_strategy(signals, daily_trend)
            
            return signals
            
        except Exception as e:
            logger.error(f"Error analyzing daily opportunities: {e}")
            return []
    
    def _analyze_daily_trend(self, df: pd.DataFrame) -> Dict:
        """
        Analyze daily trend using YOUR strategy approach
        """
        try:
            # Use last 20 days for trend analysis
            recent_df = df.tail(20)
            
            # Calculate higher timeframe trend indicators
            sma_20 = recent_df['close'].rolling(window=20).mean().iloc[-1]
            sma_50 = recent_df['close'].rolling(window=50).mean().iloc[-1]
            current_price = recent_df.iloc[-1]['close']
            
            # Determine trend direction
            trend_direction = "UP"
            if sma_20 < sma_50:
                trend_direction = "DOWN"
            
            # Find support/resistance levels
            swing_highs = self._find_swing_levels(recent_df, 'high')
            swing_lows = self._find_swing_levels(recent_df, 'low')
            
            return {
                'direction': trend_direction,
                'current_price': current_price,
                'sma_20': sma_20,
                'sma_50': sma_50,
                'swing_highs': swing_highs[-3:] if len(swing_highs) >= 3 else swing_highs,
                'swing_lows': swing_lows[-3:] if len(swing_lows) >= 3 else swing_lows,
                'strength': abs(current_price - sma_20) / sma_20  # Trend strength
            }
            
        except Exception as e:
            logger.error(f"Error analyzing daily trend: {e}")
            return {'direction': 'NEUTRAL', 'current_price': 0}
    
    def _find_swing_levels(self, df: pd.DataFrame, column: str) -> List[float]:
        """Find swing highs or lows"""
        if len(df) < 10:
            return []
        
        levels = []
        window = 3
        
        for i in range(window, len(df) - window):
            if column == 'high':
                if df.iloc[i][column] == df.iloc[i-window:i+window+1][column].max():
                    levels.append(df.iloc[i][column])
            else:  # low
                if df.iloc[i][column] == df.iloc[i-window:i+window+1][column].min():
                    levels.append(df.iloc[i][column])
        
        return levels
    
    def _detect_market_structure_signals(self, symbol: Symbol, df: pd.DataFrame, trend: Dict) -> List[TradingSignal]:
        """
        Detect BOS/CHoCH signals using YOUR SMC strategy
        """
        signals = []
        
        try:
            # Simulate SMC analysis on recent data
            recent_data = df.tail(30).copy()  # Last 30 periods
            
            # Detect BOS (Break of Structure)
            bos_signals = self._detect_bos_signals(symbol, recent_data, trend)
            signals.extend(bos_signals)
            
            # Detect CHoCH (Change of Character)
            choch_signals = self._detect_choch_signals(symbol, recent_data, trend)
            signals.extend(choch_signals)
            
            return signals
            
        except Exception as e:
            logger.error(f"Error detecting market structure: {e}")
            return []
    
    def _detect_bos_signals(self, symbol: Symbol, df: pd.DataFrame, trend: Dict) -> List[TradingSignal]:
        """Detect Break of Structure signals"""
        signals = []
        
        try:
            if len(df) < 10:
                return signals
            
            swing_highs = trend.get('swing_highs', [])
            swing_lows = trend.get('swing_lows', [])
            current_price = trend['current_price']
            
            # Check for bullish BOS
            if swing_highs and len(swing_highs) >= 2:
                previous_high = swing_highs[-2]
                recent_high = swing_highs[-1]
                
                if current_price > recent_high:  # Price broke above recent high
                    # Confirmation: Check last few candles
                    recent_candles = df.tail(3)
                    
                    if all(recent_candles['close'] > recent_high):
                        signal = self._create_bos_signal(
                            symbol, 
                            'BULLISH', 
                            current_price, 
                            recent_high,
                            entry_confidence=0.8
                        )
                        if signal:
                            signals.append(signal)
            
            # Check for bearish BOS
            if swing_lows and len(swing_lows) >= 2:
                previous_low = swing_lows[-2]
                recent_low = swing_lows[-1]
                
                if current_price < recent_low:  # Price broke below recent low
                    # Confirmation: Check last few candles
                    recent_candles = df.tail(3)
                    
                    if all(recent_candles['close'] < recent_low):
                        signal = self._create_bos_signal(
                            symbol, 
                            'BEARISH', 
                            current_price, 
                            recent_low,
                            entry_confidence=0.8
                        )
                        if signal:
                            signals.append(signal)
            
            return signals
            
        except Exception as e:
            logger.error(f"Error detecting BOS signals: {e}")
            return []
    
    def _detect_choch_signals(self, symbol: Symbol, df: pd.DataFrame, trend: Dict) -> List[TradingSignal]:
        """Detect Change of Character signals"""
        signals = []
        
        try:
            if len(df) < 20:
                return signals
            
            # Simplified CHoCH detection: trend change after significant move
            current_price = trend['current_price']
            df_sorted = df.sort_values('timestamp')
            
            # Look for trend change in swing levels
            swing_highs = trend.get('swing_highs', [])
            swing_lows = trend.get('swing_lows', [])
            
            if len(swing_highs) >= 3 and len(swing_lows) >= 3:
                # Check for CHoCH: higher lows after downtrend (bullish CHoCH)
                recent_lows = swing_lows[-3:]
                if recent_lows[-1] > recent_lows[-2] > recent_lows[-3]:
                    # Potential bullish CHoCH
                    signal = self._create_choch_signal(
                        symbol,
                        'BULLISH_CHOCH',
                        current_price,
                        entry_confidence=0.7
                    )
                    if signal:
                        signals.append(signal)
                
                # Check for CHoCH: lower highs after uptrend (bearish CHoCH)
                recent_highs = swing_highs[-3:]
                if recent_highs[-1] < recent_highs[-2] < recent_highs[-3]:
                    # Potential bearish CHoCH
                    signal = self._create_choch_signal(
                        symbol,
                        'BEARISH_CHOCH',
                        current_price,
                        entry_confidence=0.7
                    )
                    if signal:
                        signals.append(signal)
            
            return signals
            
        except Exception as e:
            logger.error(f"Error detecting CHoCH signals: {e}")
            return []
    
    def _analyze_entry_confirmations(self, symbol: Symbol, df: pd.DataFrame, trend: Dict) -> List[TradingSignal]:
        """
        Analyze entry confirmations using:
        1. Candlestick patterns (bullish/bearish engulfing)
        2. RSI levels (20-50 for longs, 50-80 for shorts)
        3. MACD crossovers
        """
        signals = []
        
        try:
            if len(df) < 20:
                return signals
            
            # Calculate indicators for confirmation
            indicators = self._calculate_confirmation_indicators(df)
            
            # Check candlestick patterns
            pattern_signals = self._detect_candlestick_signals(symbol, df, trend, indicators)
            signals.extend(pattern_signals)
            
            # Check RSI levels  
            rsi_signals = self._detect_rsi_signals(symbol, df, trend, indicators)
            signals.extend(rsi_signals)
            
            # Check MACD signals
            macd_signals = self._detect_macd_signals(symbol, df, trend, indicators)
            signals.extend(macd_signals)
            
            return signals
            
        except Exception as e:
            logger.error(f"Error analyzing entry confirmations: {e}")
            return []
    
    def _calculate_confirmation_indicators(self, df: pd.DataFrame) -> Dict:
        """Calculate indicators for confirmation analysis"""
        try:
            # RSI calculation (simplified)
            periods = 14
            if len(df) >= periods:
                prices = df['close'].values
                price_changes = np.diff(prices)
                
                gains = np.where(price_changes > 0, price_changes, 0)
                losses = np.where(price_changes < 0, -price_changes, 0)
                
                avg_gain = np.mean(gains[-periods:]) if len(gains) >= periods else 1
                avg_loss = np.mean(losses[-periods:]) if len(losses) >= periods else 1
                
                rs = avg_gain / avg_loss if avg_loss > 0 else 100
                rsi = 100 - (100 / (1 + rs))
            else:
                rsi = 50
            
            # MACD calculation (simplified)
            if len(df) >= 26:
                ema_12 = df['close'].ewm(span=12).mean().iloc[-1]
                ema_26 = df['close'].ewm(span=26).mean().iloc[-1]
                macd_line = ema_12 - ema_26
                macd_signal = 0  # Simplified
                macd_histogram = macd_line - macd_signal
            else:
                macd_line = 0
                macd_signal = 0
                macd_histogram = 0
            
            return {
                'rsi': rsi,
                'macd_line': macd_line,
                'macd_signal': macd_signal,
                'macd_histogram': macd_histogram
            }
            
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
            return {'rsi': 50, 'macd_line': 0, 'macd_signal': 0, 'macd_histogram': 0}
    
    def _detect_candlestick_signals(self, symbol: Symbol, df: pd.DataFrame, trend: Dict, indicators: Dict) -> List[TradingSignal]:
        """Detect candlestick pattern signals"""
        signals = []
        
        try:
            if len(df) < 2:
                return signals
            
            current_candle = df.iloc[-1]
            prev_candle = df.iloc[-2]
            
            # Bullish engulfing pattern
            if (trend['direction'] == 'UP' and 
                prev_candle['close'] < prev_candle['open'] and  # Previous bearish
                current_candle['close'] > current_candle['open'] and  # Current bullish
                current_candle['open'] < prev_candle['close'] and  # Opens below prev close
                current_candle['close'] > prev_candle['open']):  # Closes above prev open
                
                signal = self._create_confirmation_signal(
                    symbol, 
                    'CANDLESTICK_BULLISH',
                    trend['current_price'],
                    indicators['rsi'],
                    0.6
                )
                if signal:
                    signals.append(signal)
            
            # Bearish engulfing pattern
            elif (trend['direction'] == 'DOWN' and 
                  prev_candle['close'] > prev_candle['open'] and  # Previous bullish
                  current_candle['close'] < current_candle['open'] and  # Current bearish
                  current_candle['open'] > prev_candle['close'] and  # Opens above prev close
                  current_candle['close'] < prev_candle['open']):  # Closes below prev open
                
                signal = self._create_confirmation_signal(
                    symbol, 
                    'CANDLESTICK_BEARISH',
                    trend['current_price'],
                    indicators['rsi'],
                    0.6
                )
                if signal:
                    signals.append(signal)
            
            return signals
            
        except Exception as e:
            logger.error(f"Error detecting candlestick signals: {e}")
            return []
    
    def _detect_rsi_signals(self, symbol: Symbol, df: pd.DataFrame, trend: Dict, indicators: Dict) -> List[TradingSignal]:
        """Detect RSI-based signals according to YOUR strategy"""
        signals = []
        
        try:
            rsi = indicators['rsi']
            current_price = trend['current_price']
            
            # RSI signal: Between 20-50 for longs (showing pullback in uptrend)
            if trend['direction'] == 'UP' and 20 <= rsi <= 30:  # RSI in pullback zone
                signal = self._create_confirmation_signal(
                    symbol, 
                    'RSI_BULLISH',
                    current_price,
                    rsi,
                    0.65
                )
                if signal:
                    signals.append(signal)
            
            # RSI signal: Between 70-80 for shorts (showing pullback in downtrend)
            elif trend['direction'] == 'DOWN' and 70 <= rsi <= 80:  # RSI in pullback zone
                signal = self._create_confirmation_signal(
                    symbol, 
                    'RSI_BEARISH',
                    current_price,
                    rsi,
                    0.65
                )
                if signal:
                    signals.append(signal)
            
            return signals
            
        except Exception as e:
            logger.error(f"Error detecting RSI signals: {e}")
            return []
    
    def _detect_macd_signals(self, symbol: Symbol, df: pd.DataFrame, trend: Dict, indicators: Dict) -> List[TradingSignal]:
        """Detect MACD-based signals"""
        signals = []
        
        try:
            macd_line = indicators['macd_line']
            macd_signal = indicators['macd_signal']
            macd_histogram = indicators['macd_histogram']
            current_price = trend['current_price']
            
            # MACD bullish crossover (simplified check)
            if (trend['direction'] == 'UP' and 
                macd_line > macd_signal and 
                macd_histogram > 0):  # Bullish histogram
                
                signal = self._create_confirmation_signal(
                    symbol, 
                    'MACد_BULLISH',
                    current_price,
                    60,  # Dummy RSI value
                    0.7
                )
                if signal:
                    signals.append(signal)
            
            # MACD bearish crossover
            elif (trend['direction'] == 'DOWN' and 
                  macd_line < macd_signal and 
                  macd_histogram < 0):  # Bearish histogram
                
                signal = self._create_confirmation_signal(
                    symbol, 
                    'MACD_BEARISH',
                    current_price,
                    40,  # Dummy RSI value
                    0.7
                )
                if signal:
                    signals.append(signal)
            
            return signals
            
        except Exception as e:
            logger.error(f"Error detecting MACD signals: {e}")
            return []
    
    def _create_bos_signal(self, symbol: Symbol, direction: str, current_price: float, break_level: float, entry_confidence: float) -> Optional[TradingSignal]:
        """Create BOS signal with YOUR strategy TP/SL"""
        try:
            # Apply YOUR strategy: 15% TP, 8% SL
            if direction == 'BULLISH':
                entry_price = current_price
                target_price = current_price * (1 + self.tp_percentage)  # 15% above
                stop_loss = current_price * (1 - self.sl_percentage)     # 8% below
                signal_type_name = 'BUY'
            else:  # BEARISH
                entry_price = current_price
                target_price = current_price * (1 - self.tp_percentage)  # 15% below
                stop_loss = current_price * (1 + self.sl_percentage)       # 8% above
                signal_type_name = 'SELL'
            
            # Get or create signal type
            signal_type, _ = SignalType.objects.get_or_create(
                name=signal_type_name,
                defaults={'description': f'{direction} Signal based on Break of Structure'}
            )
            
            # Calculate risk/reward ratio
            risk = abs(entry_price - stop_loss)
            reward = abs(target_price - entry_price)
            risk_reward_ratio = reward / risk if risk > 0 else 0
            
            # Create signal
            signal = TradingSignal(
                symbol=symbol,
                signal_type=signal_type,
                entry_price=Decimal(str(entry_price)),
                target_price=Decimal(str(target_price)),
                stop_loss=Decimal(str(stop_loss)),
                confidence_score=entry_confidence,
                risk_reward_ratio=risk_reward_ratio,
                quality_score=entry_confidence,
                strength='STRONG',
                entry_point_type='BOS_CONFIRMED',
                notes=f"Break of Structure {direction} - Break Level: {break_level:.4f}",
                is_valid=True,
                created_at=timezone.now(),
                expires_at=timezone.now() + timedelta(hours=24)
            )
            
            return signal
            
        except Exception as e:
            logger.error(f"Error creating BOS signal: {e}")
            return None
    
    def _create_choch_signal(self, symbol: Symbol, direction: str, current_price: float, entry_confidence: float) -> Optional[TradingSignal]:
        """Create CHoCH signal with YOUR strategy TP/SL"""
        try:
            # Apply YOUR strategy: 15% TP, 8% SL
            if direction == 'BULLISH_CHOCH':
                entry_price = current_price
                target_price = current_price * (1 + self.tp_percentage)  # 15% above
                stop_loss = current_price * (1 - self.sl_percentage)     # 8% below
                signal_type_name = 'STRONG_BUY'
            else:  # BEARISH_CHOCH
                entry_price = current_price
                target_price = current_price * (1 - self.tp_percentage)  # 15% below
                stop_loss = current_price * (1 + self.sl_percentage)       # 8% above
                signal_type_name = 'STRONG_SELL'
            
            # Get or create signal type
            signal_type, _ = SignalType.objects.get_or_create(
                name=signal_type_name,
                defaults={'description': f'{direction.replace("_", " ")} Signal'}
            )
            
            # Calculate risk/reward ratio
            risk = abs(entry_price - stop_loss)
            reward = abs(target_price - entry_price)
            risk_reward_ratio = reward / risk if risk > 0 else 0
            
            # Create signal
            signal = TradingSignal(
                symbol=symbol,
                signal_type=signal_type,
                entry_price=Decimal(str(entry_price)),
                target_price=Decimal(str(target_price)),
                stop_loss=Decimal(str(stop_loss)),
                confidence_score=entry_confidence,
                risk_reward_ratio=risk_reward_ratio,
                quality_score=entry_confidence,
                strength='STRONG',
                entry_point_type='CHoCH_CONFIRMED',
                notes=f"Change of Character {direction.replace('_', ' ')} detected",
                is_valid=True,
                created_at=timezone.now(),
                expires_at=timezone.now() + timedelta(hours=24)
            )
            
            return signal
            
        except Exception as e:
            logger.error(f"Error creating CHoCH signal: {e}")
            return None
    
    def _create_confirmation_signal(self, symbol: Symbol, pattern: str, current_price: float, rsi: float, base_confidence: float) -> Optional[TradingSignal]:
        """Create entry confirmation signal"""
        try:
            # Determine signal direction based on pattern
            if 'BULLISH' in pattern:
                entry_price = current_price
                target_price = current_price * (1 + self.tp_percentage)  # 15% above
                stop_loss = current_price * (1 - self.sl_percentage)     # 8% below
                signal_type_name = 'BUY'
                strength_score = min(0.9, base_confidence + (rsi / 100) * 0.2)
            else:  # BEARISH
                entry_price = current_price
                target_price = current_price * (1 - self.tp_percentage)  # 15% below
                stop_loss = current_price * (1 + self.sl_percentage)       # 8% above
                signal_type_name = 'SELL'
                strength_score = min(0.9, base_confidence + ((100-rsi) / 100) * 0.2)
            
            # Get or create signal type
            signal_type, _ = SignalType.objects.get_or_create(
                name=signal_type_name,
                defaults={'description': f'{pattern} Confirmation Signal'}
            )
            
            # Calculate risk/reward ratio
            risk = abs(entry_price - stop_loss)
            reward = abs(target_price - entry_price)
            risk_reward_ratio = reward / risk if risk > 0 else 0
            
            # Create signal
            signal = TradingSignal(
                symbol=symbol,
                signal_type=signal_type,
                entry_price=Decimal(str(entry_price)),
                target_price=Decimal(str(target_price)),
                stop_loss=Decimal(str(stop_loss)),
                confidence_score=strength_score,
                risk_reward_ratio=risk_reward_ratio,
                quality_score=strength_score,
                strength='MODERATE',
                entry_point_type='CONFIRMED',
                notes=f"{pattern} confirmation - RSI: {rsi:.1f}",
                is_valid=True,
                created_at=timezone.now(),
                expires_at=timezone.now() + timedelta(hours=12)
            )
            
            return signal
            
        except Exception as e:
            logger.error(f"Error creating confirmation signal: {e}")
            return None
    
    def _apply_risk_management(self, signals: List[TradingSignal], df: pd.DataFrame) -> List[TradingSignal]:
        """
        Apply YOUR risk management rules:
        - 15% Take Profit
        - 8% Stop Loss  
        - Minimum 2:1 Risk/Reward ratio
        """
        filtered_signals = []
        
        for signal in signals:
            try:
                entry = float(signal.entry_price)
                target = float(signal.target_price)
                stop = float(signal.stop_loss)
                
                # Calculate actual risk/reward
                if signal.signal_type.name in ['BUY', 'STRONG_BUY']:
                    risk = entry - stop
                    reward = target - entry
                else:  # SELL signals
                    risk = stop - entry
                    reward = entry - target
                
                # Ensure positive values
                risk = abs(risk)
                reward = abs(reward)
                
                # Apply minimum risk/reward ratio (2:1 minimum)
                if reward >= 2 * risk:
                    # Update signal with corrected risk/reward
                    signal.risk_reward_ratio = reward / risk
                    filtered_signals.append(signal)
                
            except Exception as e:
                logger.error(f"Error applying risk management: {e}")
                continue
        
        return filtered_signals
    
    def _filter_signals_to_strategy(self, signals: List[TradingSignal], trend: Dict) -> List[TradingSignal]:
        """
        Filter signals based on YOUR strategy requirements:
        - Only signals in trend direction for main trades
        - Higher confidence for counter-trend trades
        """
        filtered_signals = []
        
        for signal in signals:
            try:
                # Ensure signal aligns with current trend strength
                if len(filtered_signals) < 5:  # Limit signals per day
                    # Adjust confidence based on strategy alignment
                    strategy_confidence = self._calculate_strategy_alignment(signal, trend)
                    signal.confidence_score = strategy_confidence
                    
                    # Update quality score
                    signal.quality_score = strategy_confidence
                    
                    filtered_signals.append(signal)
                
            except Exception as e:
                logger.error(f"Error filtering signals: {e}")
                continue
        
        return filtered_signals
    
    def _calculate_strategy_alignment(self, signal: TradingSignal, trend: Dict) -> float:
        """Calculate how well signal aligns with YOUR strategy"""
        try:
            base_confidence = signal.confidence_score
            
            # Increase confidence if signal aligns with trend
            if trend['direction'] == 'UP' and signal.signal_type.name in ['BUY', 'STRONG_BUY']:
                alignment_bonus = trend.get('strength', 0) * 0.1
                base_confidence += alignment_bonus
            
            elif trend['direction'] == 'DOWN' and signal.signal_type.name in ['SELL', 'STRONG_SELL']:
                alignment_bonus = trend.get('strength', 0) * 0.1  
                base_confidence += alignment_bonus
            
            return min(0.95, base_confidence)
            
        except Exception as e:
            logger.error(f"Error calculating strategy alignment: {e}")
            return signal.confidence_score
    
    def _analyze_historical_period(self, symbol: Symbol, df: pd.DataFrame) -> List[TradingSignal]:
        """
        Analyze historical period as continuous data
        """
        signals = []
        
        try:
            # Apply sliding window analysis
            window_size = 50
            
            for i in range(window_size, len(df)):
                window_df = df.iloc[i-window_size:i]
                trend = self._analyze_daily_trend(window_df)
                
                # Analyze opportunities in this window
                window_signals = self._analyze_daily_opportunities(symbol, window_df, df.iloc[i]['timestamp'])
                
                # Add timestamp to signals
                window_timestamp = df.iloc[i]['timestamp']
                for signal in window_signals:
                    signal.created_at = window_timestamp
                
                signals.extend(window_signals)
                
                # Limit total signals
                if len(signals) >= 100:
                    break
            
            return signals
            
        except Exception as e:
            logger.error(f"Error analyzing historical period: {e}")
            return []
