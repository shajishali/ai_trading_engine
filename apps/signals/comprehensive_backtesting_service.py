"""
Comprehensive Backtesting Service
Analyzes entire price charts within specified periods to generate ALL possible trading signals
based on various strategies and technical indicators.
"""

import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from decimal import Decimal
from django.utils import timezone
from django.db.models import Q
import talib

from apps.trading.models import Symbol
from apps.data.models import MarketData, TechnicalIndicator
from apps.signals.models import TradingSignal, SignalType
from apps.signals.services import SignalGenerationService

logger = logging.getLogger(__name__)


class ComprehensiveBacktestingService:
    """
    Service for comprehensive backtesting that analyzes entire price charts
    to find ALL possible trading signals within a given period.
    """
    
    def __init__(self):
        self.signal_service = SignalGenerationService()
        self.logger = logging.getLogger(__name__)
        
        # Strategy configurations - prioritizing 30-minute strategy
        self.strategies = {
            'THIRTY_MINUTE_TIMEFRAME': {
                'lookback_periods': 50,  # Look back 50 periods (25 hours) to find levels
                'support_resistance_buffer': 0.02,  # 2% buffer for level validation
                'min_distance_percentage': 0.05,  # At least 5% distance between levels
                'min_confidence': 0.75,  # High confidence for 30-minute strategy
                'strategy_type': 'previous_high_low'
            },
            'SUPPORT_RESISTANCE': {
                'lookback_period': 50,
                'touch_threshold': 0.02,  # 2% threshold
                'min_confidence': 0.75
            },
            'SMA_CROSSOVER': {
                'short_period': 10,
                'long_period': 20,
                'min_confidence': 0.6
            },
            'RSI_OVERSOLD_OVERBOUGHT': {
                'period': 14,
                'oversold': 30,
                'overbought': 70,
                'min_confidence': 0.7
            },
            'MACD_SIGNAL': {
                'fast_period': 12,
                'slow_period': 26,
                'signal_period': 9,
                'min_confidence': 0.65
            },
            'BOLLINGER_BANDS': {
                'period': 20,
                'std_dev': 2,
                'min_confidence': 0.6
            },
            'BREAKOUT_PATTERN': {
                'consolidation_period': 20,
                'volume_threshold': 1.5,
                'min_confidence': 0.8
            },
            'DIVERGENCE_DETECTION': {
                'lookback_period': 30,
                'min_confidence': 0.85
            },
            'CANDLESTICK_PATTERNS': {
                'patterns': ['DOJI', 'HAMMER', 'SHOOTING_STAR', 'ENGULFING'],
                'min_confidence': 0.7
            }
        }
    
    def generate_comprehensive_signals(
        self, 
        symbol: Symbol, 
        start_date: datetime, 
        end_date: datetime,
        strategies: List[str] = None,
        timeframes: List[str] = None,
        min_confidence: float = 0.5
    ) -> List[TradingSignal]:
        """
        Generate comprehensive signals by analyzing the entire chart within the period.
        
        Args:
            symbol: Trading symbol to analyze
            start_date: Start date for analysis
            end_date: End date for analysis
            strategies: List of strategies to use (default: all)
            timeframes: List of timeframes to analyze (default: ['1H', '4H', '1D'])
            min_confidence: Minimum confidence threshold for signals
            
        Returns:
            List of all possible TradingSignal objects found in the period
        """
        try:
            self.logger.info(f"Starting comprehensive signal generation for {symbol.symbol}")
            self.logger.info(f"Period: {start_date} to {end_date}")
            
            # Default strategies and timeframes - prioritize 30-minute strategy
            if strategies is None:
                # Use 30-minute timeframe strategy as primary, plus support/resistance
                strategies = ['THIRTY_MINUTE_TIMEFRAME', 'SUPPORT_RESISTANCE']
            if timeframes is None:
                # Focus on 30-minute timeframe as requested by user
                timeframes = ['30M', '1H']
            
            # Get historical price data
            price_data = self._get_historical_data(symbol, start_date, end_date)
            if price_data.empty:
                self.logger.warning(f"No price data found for {symbol.symbol}")
                return []
            
            self.logger.info(f"Retrieved {len(price_data)} price data points")
            
            all_signals = []
            
            # Analyze each timeframe
            for timeframe in timeframes:
                self.logger.info(f"Analyzing timeframe: {timeframe}")
                
                # Resample data for different timeframes
                resampled_data = self._resample_data(price_data, timeframe)
                if resampled_data.empty:
                    continue
                
                # Apply each strategy
                for strategy_name in strategies:
                    self.logger.info(f"Applying strategy: {strategy_name}")
                    
                    strategy_signals = self._apply_strategy(
                        symbol, 
                        resampled_data, 
                        strategy_name, 
                        timeframe,
                        min_confidence
                    )
                    
                    all_signals.extend(strategy_signals)
                    self.logger.info(f"Generated {len(strategy_signals)} signals from {strategy_name}")
            
            # Remove duplicates and sort by timestamp
            unique_signals = self._deduplicate_signals(all_signals)
            unique_signals.sort(key=lambda x: x.created_at)
            
            self.logger.info(f"Total unique signals generated: {len(unique_signals)}")
            
            # Save signals to database
            if unique_signals:
                self._save_signals_to_database(unique_signals)
            
            return unique_signals
            
        except Exception as e:
            self.logger.error(f"Error in comprehensive signal generation: {e}")
            return []
    
    def _get_historical_data(self, symbol: Symbol, start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """Get historical price data for the symbol and period."""
        try:
            # Try to get real market data first
            market_data = MarketData.objects.filter(
                symbol=symbol,
                timestamp__gte=start_date,
                timestamp__lte=end_date
            ).order_by('timestamp')
            
            if market_data.exists():
                data = []
                for md in market_data:
                    data.append({
                        'timestamp': md.timestamp,
                        'open': float(md.open_price),
                        'high': float(md.high_price),
                        'low': float(md.low_price),
                        'close': float(md.close_price),
                        'volume': float(md.volume) if md.volume else 0
                    })
                
                df = pd.DataFrame(data)
                df.set_index('timestamp', inplace=True)
                return df
            
            else:
                # Enforce real-data-only policy
                self.logger.error(
                    f"No real market data found for {symbol.symbol} in range {start_date} to {end_date}. "
                    f"Populate historical data and retry."
                )
                return pd.DataFrame()
                
        except Exception as e:
            self.logger.error(f"Error getting historical data: {e}")
            return pd.DataFrame()
    
    def _generate_synthetic_data(self, symbol: Symbol, start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """Generate synthetic price data for backtesting purposes."""
        try:
            # Generate hourly data points
            time_range = pd.date_range(start=start_date, end=end_date, freq='1H')
            
            # Base price (use fallback price or default)
            base_price = 100.0  # Default base price
            try:
                # Try to get a reasonable base price
                from apps.data.services import LivePriceService
                price_service = LivePriceService()
                current_price = price_service.get_current_price(symbol.symbol)
                if current_price and current_price > 0:
                    base_price = float(current_price)
            except:
                pass
            
            # Generate realistic price movements
            np.random.seed(42)  # For reproducible results
            returns = np.random.normal(0, 0.02, len(time_range))  # 2% volatility
            
            prices = [base_price]
            for ret in returns[1:]:
                new_price = prices[-1] * (1 + ret)
                prices.append(max(new_price, 0.01))  # Ensure price doesn't go negative
            
            # Generate OHLC data
            data = []
            for i, timestamp in enumerate(time_range):
                price = prices[i]
                
                # Generate realistic OHLC from the close price
                volatility = abs(np.random.normal(0, 0.01))  # 1% intraday volatility
                
                high = price * (1 + volatility)
                low = price * (1 - volatility)
                open_price = prices[i-1] if i > 0 else price
                
                # Ensure OHLC relationships are maintained
                high = max(high, open_price, price)
                low = min(low, open_price, price)
                
                volume = np.random.uniform(1000, 10000)  # Random volume
                
                data.append({
                    'timestamp': timestamp,
                    'open': open_price,
                    'high': high,
                    'low': low,
                    'close': price,
                    'volume': volume
                })
            
            df = pd.DataFrame(data)
            df.set_index('timestamp', inplace=True)
            
            self.logger.info(f"Generated {len(df)} synthetic data points for {symbol.symbol}")
            return df
            
        except Exception as e:
            self.logger.error(f"Error generating synthetic data: {e}")
            return pd.DataFrame()
    
    def _resample_data(self, data: pd.DataFrame, timeframe: str) -> pd.DataFrame:
        """Resample data to different timeframes."""
        try:
            if data.empty:
                return data
            
            # Define resampling rules
            timeframe_map = {
                '1H': '1H',
                '4H': '4H', 
                '1D': '1D',
                '1W': '1W'
            }
            
            if timeframe not in timeframe_map:
                return data
            
            # Resample OHLCV data
            resampled = data.resample(timeframe_map[timeframe]).agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            }).dropna()
            
            return resampled
            
        except Exception as e:
            self.logger.error(f"Error resampling data: {e}")
            return data
    
    def _apply_strategy(
        self, 
        symbol: Symbol, 
        data: pd.DataFrame, 
        strategy_name: str, 
        timeframe: str,
        min_confidence: float
    ) -> List[TradingSignal]:
        """Apply a specific strategy to generate signals."""
        try:
            if data.empty or len(data) < 20:  # Need minimum data points
                return []
            
            strategy_config = self.strategies.get(strategy_name, {})
            signals = []
            
            if strategy_name == 'THIRTY_MINUTE_TIMEFRAME':
                signals = self._thirty_minute_timeframe_strategy(symbol, data, strategy_config, timeframe)
            elif strategy_name == 'SMA_CROSSOVER':
                signals = self._sma_crossover_strategy(symbol, data, strategy_config, timeframe)
            elif strategy_name == 'RSI_OVERSOLD_OVERBOUGHT':
                signals = self._rsi_strategy(symbol, data, strategy_config, timeframe)
            elif strategy_name == 'MACD_SIGNAL':
                signals = self._macd_strategy(symbol, data, strategy_config, timeframe)
            elif strategy_name == 'BOLLINGER_BANDS':
                signals = self._bollinger_bands_strategy(symbol, data, strategy_config, timeframe)
            elif strategy_name == 'SUPPORT_RESISTANCE':
                signals = self._support_resistance_strategy(symbol, data, strategy_config, timeframe)
            elif strategy_name == 'BREAKOUT_PATTERN':
                signals = self._breakout_strategy(symbol, data, strategy_config, timeframe)
            elif strategy_name == 'DIVERGENCE_DETECTION':
                signals = self._divergence_strategy(symbol, data, strategy_config, timeframe)
            elif strategy_name == 'CANDLESTICK_PATTERNS':
                signals = self._candlestick_patterns_strategy(symbol, data, strategy_config, timeframe)
            
            # Filter by minimum confidence
            filtered_signals = [s for s in signals if s.confidence_score >= min_confidence]
            
            return filtered_signals
            
        except Exception as e:
            self.logger.error(f"Error applying strategy {strategy_name}: {e}")
            return []
    
    def _sma_crossover_strategy(self, symbol: Symbol, data: pd.DataFrame, config: dict, timeframe: str) -> List[TradingSignal]:
        """Simple Moving Average Crossover Strategy."""
        signals = []
        try:
            short_period = config.get('short_period', 10)
            long_period = config.get('long_period', 20)
            
            # Calculate SMAs
            data['SMA_short'] = data['close'].rolling(window=short_period).mean()
            data['SMA_long'] = data['close'].rolling(window=long_period).mean()
            
            # Find crossovers
            data['signal'] = 0
            data['signal'][short_period:] = np.where(
                data['SMA_short'][short_period:] > data['SMA_long'][short_period:], 1, 0
            )
            data['positions'] = data['signal'].diff()
            
            # Generate signals at crossover points
            for idx, row in data.iterrows():
                if pd.isna(row['positions']) or row['positions'] == 0:
                    continue
                
                signal_type_name = 'BUY' if row['positions'] > 0 else 'SELL'
                
                # Get or create signal type
                signal_type, _ = SignalType.objects.get_or_create(
                    name=signal_type_name,
                    defaults={'description': f'{signal_type_name} signal from SMA crossover'}
                )
                
                # Calculate confidence based on SMA separation
                sma_diff = abs(row['SMA_short'] - row['SMA_long'])
                price_pct = sma_diff / row['close']
                confidence = min(0.9, max(0.5, price_pct * 50))  # Scale to 0.5-0.9
                
                # Calculate entry, target, and stop loss
                entry_price = Decimal(str(row['close']))
                
                # Capital-based calculation: $60 profit target, $50 stop loss based on $100 capital
                capital_per_trade = Decimal('100.00')  # $100 capital investment
                max_loss_amount = Decimal('50.00')     # $50 max loss
                profit_target_amount = Decimal('60.00')  # $60 profit target
                
                # Calculate position size
                position_size = capital_per_trade / entry_price
                
                if signal_type_name == 'BUY':
                    target_price = entry_price + (profit_target_amount / position_size)  # $60 profit
                    stop_loss = entry_price - (max_loss_amount / position_size)  # $50 loss
                else:
                    target_price = entry_price - (profit_target_amount / position_size)  # $60 profit for sell
                    stop_loss = entry_price + (max_loss_amount / position_size)  # $50 loss for sell
                
                signal = TradingSignal(
                    symbol=symbol,
                    signal_type=signal_type,
                    entry_price=entry_price,
                    target_price=target_price,
                    stop_loss=stop_loss,
                    confidence_score=confidence,
                    confidence_level='MEDIUM' if confidence < 0.7 else 'HIGH',
                    risk_reward_ratio=1.5,
                    timeframe=timeframe,
                    entry_point_type='SMA_CROSSOVER',
                    quality_score=confidence,
                    strength='MEDIUM' if confidence < 0.7 else 'STRONG',
                    notes=f'SMA({short_period}) crossed {"above" if signal_type_name == "BUY" else "below"} SMA({long_period})',
                    is_valid=True,
                    expires_at=idx + timedelta(hours=24),
                    created_at=idx,
                    metadata={
                        'strategy': 'SMA_CROSSOVER',
                        'short_sma': row['SMA_short'],
                        'long_sma': row['SMA_long'],
                        'price_at_signal': row['close']
                    }
                )
                
                signals.append(signal)
                
        except Exception as e:
            self.logger.error(f"Error in SMA crossover strategy: {e}")
        
        return signals
    
    def _rsi_strategy(self, symbol: Symbol, data: pd.DataFrame, config: dict, timeframe: str) -> List[TradingSignal]:
        """RSI Oversold/Overbought Strategy."""
        signals = []
        try:
            period = config.get('period', 14)
            oversold = config.get('oversold', 30)
            overbought = config.get('overbought', 70)
            
            # Calculate RSI
            data['RSI'] = talib.RSI(data['close'].values, timeperiod=period)
            
            # Find oversold/overbought conditions
            for idx, row in data.iterrows():
                if pd.isna(row['RSI']):
                    continue
                
                signal_type_name = None
                if row['RSI'] <= oversold:
                    signal_type_name = 'BUY'  # Oversold, expect bounce
                elif row['RSI'] >= overbought:
                    signal_type_name = 'SELL'  # Overbought, expect pullback
                
                if signal_type_name:
                    # Get or create signal type
                    signal_type, _ = SignalType.objects.get_or_create(
                        name=signal_type_name,
                        defaults={'description': f'{signal_type_name} signal from RSI'}
                    )
                    
                    # Calculate confidence based on RSI extreme
                    if signal_type_name == 'BUY':
                        confidence = min(0.9, (oversold - row['RSI']) / oversold + 0.6)
                    else:
                        confidence = min(0.9, (row['RSI'] - overbought) / (100 - overbought) + 0.6)
                    
                    entry_price = Decimal(str(row['close']))
                    
                    # Capital-based calculation: 60% profit target, 50% stop loss
                    capital_allocation_percentage = Decimal('0.50')  # 50% of capital at risk
                    profit_target_percentage = Decimal('0.60')  # 60% profit target
                    
                    if signal_type_name == 'BUY':
                        target_price = entry_price * (Decimal('1.0') + profit_target_percentage)  # 60% profit
                        stop_loss = entry_price * (Decimal('1.0') - capital_allocation_percentage)  # 50% stop loss
                    else:
                        target_price = entry_price * (Decimal('1.0') - profit_target_percentage)  # 60% profit for sell
                        stop_loss = entry_price * (Decimal('1.0') + capital_allocation_percentage)  # 50% stop loss for sell
                    
                    signal = TradingSignal(
                        symbol=symbol,
                        signal_type=signal_type,
                        entry_price=entry_price,
                        target_price=target_price,
                        stop_loss=stop_loss,
                        confidence_score=confidence,
                        confidence_level='MEDIUM' if confidence < 0.7 else 'HIGH',
                        risk_reward_ratio=1.67,  # 2.5/1.5
                        timeframe=timeframe,
                        entry_point_type='RSI_REVERSAL',
                        quality_score=confidence,
                        strength='MEDIUM' if confidence < 0.7 else 'STRONG',
                        notes=f'RSI {row["RSI"]:.1f} - {"Oversold" if signal_type_name == "BUY" else "Overbought"}',
                        is_valid=True,
                        expires_at=idx + timedelta(hours=12),
                        created_at=idx,
                        metadata={
                            'strategy': 'RSI_OVERSOLD_OVERBOUGHT',
                            'rsi_value': row['RSI'],
                            'price_at_signal': row['close']
                        }
                    )
                    
                    signals.append(signal)
                    
        except Exception as e:
            self.logger.error(f"Error in RSI strategy: {e}")
        
        return signals
    
    def _macd_strategy(self, symbol: Symbol, data: pd.DataFrame, config: dict, timeframe: str) -> List[TradingSignal]:
        """MACD Signal Line Crossover Strategy."""
        signals = []
        try:
            fast_period = config.get('fast_period', 12)
            slow_period = config.get('slow_period', 26)
            signal_period = config.get('signal_period', 9)
            
            # Calculate MACD
            exp1 = data['close'].ewm(span=fast_period).mean()
            exp2 = data['close'].ewm(span=slow_period).mean()
            data['MACD'] = exp1 - exp2
            data['MACD_signal'] = data['MACD'].ewm(span=signal_period).mean()
            data['MACD_histogram'] = data['MACD'] - data['MACD_signal']
            
            # Find signal line crossovers
            data['macd_positions'] = np.where(data['MACD'] > data['MACD_signal'], 1, 0)
            data['macd_crossover'] = data['macd_positions'].diff()
            
            for idx, row in data.iterrows():
                if pd.isna(row['macd_crossover']) or row['macd_crossover'] == 0:
                    continue
                
                signal_type_name = 'BUY' if row['macd_crossover'] > 0 else 'SELL'
                
                # Get or create signal type
                signal_type, _ = SignalType.objects.get_or_create(
                    name=signal_type_name,
                    defaults={'description': f'{signal_type_name} signal from MACD crossover'}
                )
                
                # Calculate confidence based on MACD strength
                macd_strength = abs(row['MACD'] - row['MACD_signal'])
                confidence = min(0.9, max(0.5, macd_strength * 100 + 0.5))
                
                entry_price = Decimal(str(row['close']))
                
                # Capital-based calculation: $60 profit target, $50 stop loss based on $100 capital
                capital_per_trade = Decimal('100.00')  # $100 capital investment
                max_loss_amount = Decimal('50.00')     # $50 max loss
                profit_target_amount = Decimal('60.00')  # $60 profit target
                
                # Calculate position size
                position_size = capital_per_trade / entry_price
                
                if signal_type_name == 'BUY':
                    target_price = entry_price + (profit_target_amount / position_size)  # $60 profit
                    stop_loss = entry_price - (max_loss_amount / position_size)  # $50 loss
                else:
                    target_price = entry_price - (profit_target_amount / position_size)  # $60 profit for sell
                    stop_loss = entry_price + (max_loss_amount / position_size)  # $50 loss for sell
                
                signal = TradingSignal(
                    symbol=symbol,
                    signal_type=signal_type,
                    entry_price=entry_price,
                    target_price=target_price,
                    stop_loss=stop_loss,
                    confidence_score=confidence,
                    confidence_level='MEDIUM' if confidence < 0.7 else 'HIGH',
                    risk_reward_ratio=1.6,  # 4/2.5
                    timeframe=timeframe,
                    entry_point_type='MACD_CROSSOVER',
                    quality_score=confidence,
                    strength='MEDIUM' if confidence < 0.7 else 'STRONG',
                    notes=f'MACD crossed {"above" if signal_type_name == "BUY" else "below"} signal line',
                    is_valid=True,
                    expires_at=idx + timedelta(hours=18),
                    created_at=idx,
                    metadata={
                        'strategy': 'MACD_SIGNAL',
                        'macd_value': row['MACD'],
                        'macd_signal': row['MACD_signal'],
                        'price_at_signal': row['close']
                    }
                )
                
                signals.append(signal)
                
        except Exception as e:
            self.logger.error(f"Error in MACD strategy: {e}")
        
        return signals
    
    def _bollinger_bands_strategy(self, symbol: Symbol, data: pd.DataFrame, config: dict, timeframe: str) -> List[TradingSignal]:
        """Bollinger Bands Strategy."""
        signals = []
        try:
            period = config.get('period', 20)
            std_dev = config.get('std_dev', 2)
            
            # Calculate Bollinger Bands
            data['BB_middle'] = data['close'].rolling(window=period).mean()
            data['BB_upper'] = data['BB_middle'] + (data['close'].rolling(window=period).std() * std_dev)
            data['BB_lower'] = data['BB_middle'] - (data['close'].rolling(window=period).std() * std_dev)
            
            # Find touches or breaks of bands
            for idx, row in data.iterrows():
                if pd.isna(row['BB_upper']) or pd.isna(row['BB_lower']):
                    continue
                
                signal_type_name = None
                confidence = 0.5
                
                # Price touching lower band - potential buy
                if row['close'] <= row['BB_lower']:
                    signal_type_name = 'BUY'
                    band_distance = (row['BB_lower'] - row['close']) / row['close']
                    confidence = min(0.9, 0.6 + band_distance * 20)
                
                # Price touching upper band - potential sell
                elif row['close'] >= row['BB_upper']:
                    signal_type_name = 'SELL'
                    band_distance = (row['close'] - row['BB_upper']) / row['close']
                    confidence = min(0.9, 0.6 + band_distance * 20)
                
                if signal_type_name:
                    # Get or create signal type
                    signal_type, _ = SignalType.objects.get_or_create(
                        name=signal_type_name,
                        defaults={'description': f'{signal_type_name} signal from Bollinger Bands'}
                    )
                    
                    entry_price = Decimal(str(row['close']))
                    
                    if signal_type_name == 'BUY':
                        target_price = Decimal(str(row['BB_middle']))  # Target middle band
                        stop_loss = entry_price * Decimal('0.975')    # 2.5% stop loss
                    else:
                        target_price = Decimal(str(row['BB_middle']))  # Target middle band
                        stop_loss = entry_price * Decimal('1.025')    # 2.5% stop loss
                    
                    # Calculate risk-reward ratio
                    risk = abs(float(entry_price - stop_loss))
                    reward = abs(float(target_price - entry_price))
                    rr_ratio = reward / risk if risk > 0 else 1.0
                    
                    signal = TradingSignal(
                        symbol=symbol,
                        signal_type=signal_type,
                        entry_price=entry_price,
                        target_price=target_price,
                        stop_loss=stop_loss,
                        confidence_score=confidence,
                        confidence_level='MEDIUM' if confidence < 0.7 else 'HIGH',
                        risk_reward_ratio=rr_ratio,
                        timeframe=timeframe,
                        entry_point_type='BB_REVERSAL',
                        quality_score=confidence,
                        strength='MEDIUM' if confidence < 0.7 else 'STRONG',
                        notes=f'Price touched {"lower" if signal_type_name == "BUY" else "upper"} Bollinger Band',
                        is_valid=True,
                        expires_at=idx + timedelta(hours=12),
                        created_at=idx,
                        metadata={
                            'strategy': 'BOLLINGER_BANDS',
                            'bb_upper': row['BB_upper'],
                            'bb_middle': row['BB_middle'],
                            'bb_lower': row['BB_lower'],
                            'price_at_signal': row['close']
                        }
                    )
                    
                    signals.append(signal)
                    
        except Exception as e:
            self.logger.error(f"Error in Bollinger Bands strategy: {e}")
        
        return signals
    
    def _support_resistance_strategy(self, symbol: Symbol, data: pd.DataFrame, config: dict, timeframe: str) -> List[TradingSignal]:
        """Support and Resistance Strategy."""
        signals = []
        try:
            lookback_period = config.get('lookback_period', 50)
            touch_threshold = config.get('touch_threshold', 0.02)  # 2%
            
            # Find support and resistance levels
            highs = data['high'].rolling(window=lookback_period).max()
            lows = data['low'].rolling(window=lookback_period).min()
            
            for idx, row in data.iterrows():
                if pd.isna(highs[idx]) or pd.isna(lows[idx]):
                    continue
                
                signal_type_name = None
                confidence = 0.5
                level_price = 0
                
                # Check if price is near support (potential buy)
                support_distance = abs(row['close'] - lows[idx]) / row['close']
                if support_distance <= touch_threshold:
                    signal_type_name = 'BUY'
                    confidence = min(0.9, 0.7 + (touch_threshold - support_distance) * 10)
                    level_price = lows[idx]
                
                # Check if price is near resistance (potential sell)
                resistance_distance = abs(row['close'] - highs[idx]) / row['close']
                if resistance_distance <= touch_threshold:
                    signal_type_name = 'SELL'
                    confidence = min(0.9, 0.7 + (touch_threshold - resistance_distance) * 10)
                    level_price = highs[idx]
                
                if signal_type_name:
                    # Get or create signal type
                    signal_type, _ = SignalType.objects.get_or_create(
                        name=signal_type_name,
                        defaults={'description': f'{signal_type_name} signal from Support/Resistance'}
                    )
                    
                    entry_price = Decimal(str(row['close']))
                    
                    # Capital-based calculation: 60% profit target, 50% stop loss
                    capital_allocation_percentage = Decimal('0.50')  # 50% of capital at risk
                    profit_target_percentage = Decimal('0.60')  # 60% profit target
                    
                    if signal_type_name == 'BUY':
                        target_price = entry_price * (Decimal('1.0') + profit_target_percentage)  # 60% profit
                        stop_loss = entry_price * (Decimal('1.0') - capital_allocation_percentage)  # 50% stop loss
                    else:
                        target_price = entry_price * (Decimal('1.0') - profit_target_percentage)  # 60% profit for sell
                        stop_loss = entry_price * (Decimal('1.0') + capital_allocation_percentage)  # 50% stop loss for sell
                    
                    # Calculate risk-reward ratio
                    risk = abs(float(entry_price - stop_loss))
                    reward = abs(float(target_price - entry_price))
                    rr_ratio = reward / risk if risk > 0 else 1.0
                    
                    signal = TradingSignal(
                        symbol=symbol,
                        signal_type=signal_type,
                        entry_price=entry_price,
                        target_price=target_price,
                        stop_loss=stop_loss,
                        confidence_score=confidence,
                        confidence_level='HIGH',
                        risk_reward_ratio=rr_ratio,
                        timeframe=timeframe,
                        entry_point_type='SUPPORT_RESISTANCE',
                        quality_score=confidence,
                        strength='STRONG',
                        notes=f'Price near {"support" if signal_type_name == "BUY" else "resistance"} at ${level_price:.2f}',
                        is_valid=True,
                        expires_at=idx + timedelta(hours=6),
                        created_at=idx,
                        metadata={
                            'strategy': 'SUPPORT_RESISTANCE',
                            'level_price': level_price,
                            'level_type': 'support' if signal_type_name == 'BUY' else 'resistance',
                            'price_at_signal': row['close']
                        }
                    )
                    
                    signals.append(signal)
                    
        except Exception as e:
            self.logger.error(f"Error in Support/Resistance strategy: {e}")
        
        return signals
    
    def _breakout_strategy(self, symbol: Symbol, data: pd.DataFrame, config: dict, timeframe: str) -> List[TradingSignal]:
        """Breakout Pattern Strategy."""
        signals = []
        try:
            consolidation_period = config.get('consolidation_period', 20)
            volume_threshold = config.get('volume_threshold', 1.5)
            
            # Calculate volatility and volume metrics
            data['volatility'] = data['high'] / data['low'] - 1
            data['avg_volume'] = data['volume'].rolling(window=consolidation_period).mean()
            data['volume_ratio'] = data['volume'] / data['avg_volume']
            
            # Find consolidation periods (low volatility)
            data['is_consolidating'] = data['volatility'] < data['volatility'].rolling(window=consolidation_period).mean() * 0.7
            
            for idx, row in data.iterrows():
                if pd.isna(row['volume_ratio']) or pd.isna(row['is_consolidating']):
                    continue
                
                # Look for breakout conditions
                if (row['is_consolidating'] and 
                    row['volume_ratio'] >= volume_threshold):
                    
                    # Determine breakout direction
                    recent_high = data['high'].iloc[max(0, data.index.get_loc(idx) - 5):data.index.get_loc(idx)].max()
                    recent_low = data['low'].iloc[max(0, data.index.get_loc(idx) - 5):data.index.get_loc(idx)].min()
                    
                    signal_type_name = None
                    if row['close'] > recent_high:
                        signal_type_name = 'BUY'  # Upward breakout
                    elif row['close'] < recent_low:
                        signal_type_name = 'SELL'  # Downward breakout
                    
                    if signal_type_name:
                        # Get or create signal type
                        signal_type, _ = SignalType.objects.get_or_create(
                            name=signal_type_name,
                            defaults={'description': f'{signal_type_name} signal from breakout'}
                        )
                        
                        # High confidence for volume-confirmed breakouts
                        confidence = min(0.9, 0.7 + (row['volume_ratio'] - volume_threshold) * 0.1)
                        
                        entry_price = Decimal(str(row['close']))
                        
                        # Capital-based calculation: 60% profit target, 50% stop loss
                        capital_allocation_percentage = Decimal('0.50')  # 50% of capital at risk
                        profit_target_percentage = Decimal('0.60')  # 60% profit target
                        
                        if signal_type_name == 'BUY':
                            target_price = entry_price * (Decimal('1.0') + profit_target_percentage)  # 60% profit
                            stop_loss = entry_price * (Decimal('1.0') - capital_allocation_percentage)  # 50% stop loss
                        else:
                            target_price = entry_price * (Decimal('1.0') - profit_target_percentage)  # 60% profit for sell
                            stop_loss = entry_price * (Decimal('1.0') + capital_allocation_percentage)  # 50% stop loss for sell
                        
                        # Calculate risk-reward ratio
                        risk = abs(float(entry_price - stop_loss))
                        reward = abs(float(target_price - entry_price))
                        rr_ratio = reward / risk if risk > 0 else 1.0
                        
                        signal = TradingSignal(
                            symbol=symbol,
                            signal_type=signal_type,
                            entry_price=entry_price,
                            target_price=target_price,
                            stop_loss=stop_loss,
                            confidence_score=confidence,
                            confidence_level='HIGH',
                            risk_reward_ratio=rr_ratio,
                            timeframe=timeframe,
                            entry_point_type='BREAKOUT',
                            quality_score=confidence,
                            strength='STRONG',
                            notes=f'Volume breakout (Volume ratio: {row["volume_ratio"]:.1f}x)',
                            is_valid=True,
                            expires_at=idx + timedelta(hours=8),
                            created_at=idx,
                            metadata={
                                'strategy': 'BREAKOUT_PATTERN',
                                'volume_ratio': row['volume_ratio'],
                                'breakout_level': recent_high if signal_type_name == 'BUY' else recent_low,
                                'price_at_signal': row['close']
                            }
                        )
                        
                        signals.append(signal)
                        
        except Exception as e:
            self.logger.error(f"Error in Breakout strategy: {e}")
        
        return signals
    
    def _divergence_strategy(self, symbol: Symbol, data: pd.DataFrame, config: dict, timeframe: str) -> List[TradingSignal]:
        """Price-RSI Divergence Strategy."""
        signals = []
        try:
            lookback_period = config.get('lookback_period', 30)
            
            # Calculate RSI for divergence analysis
            data['RSI'] = talib.RSI(data['close'].values, timeperiod=14)
            
            # Find price and RSI peaks/troughs
            data['price_peak'] = data['close'].rolling(window=5, center=True).max() == data['close']
            data['price_trough'] = data['close'].rolling(window=5, center=True).min() == data['close']
            data['rsi_peak'] = data['RSI'].rolling(window=5, center=True).max() == data['RSI']
            data['rsi_trough'] = data['RSI'].rolling(window=5, center=True).min() == data['RSI']
            
            peaks = data[data['price_peak'] & data['rsi_peak']].copy()
            troughs = data[data['price_trough'] & data['rsi_trough']].copy()
            
            # Look for divergences
            for i in range(1, len(peaks)):
                current_peak = peaks.iloc[i]
                previous_peak = peaks.iloc[i-1]
                
                # Bullish divergence: price makes lower high, RSI makes higher high
                if (current_peak['close'] < previous_peak['close'] and 
                    current_peak['RSI'] > previous_peak['RSI']):
                    
                    signal_type, _ = SignalType.objects.get_or_create(
                        name='BUY',
                        defaults={'description': 'BUY signal from bullish divergence'}
                    )
                    
                    confidence = 0.85  # High confidence for divergences
                    entry_price = Decimal(str(current_peak['close']))
                    # Capital-based calculation: $60 profit target, $50 stop loss based on $100 capital
                    capital_per_trade = Decimal('100.00')  # $100 capital investment
                    max_loss_amount = Decimal('50.00')     # $50 max loss
                    profit_target_amount = Decimal('60.00')  # $60 profit target
                    
                    # Calculate position size
                    position_size = capital_per_trade / entry_price
                    
                    target_price = entry_price + (profit_target_amount / position_size)  # $60 profit
                    stop_loss = entry_price - (max_loss_amount / position_size)  # $50 loss
                    
                    signal = TradingSignal(
                        symbol=symbol,
                        signal_type=signal_type,
                        entry_price=entry_price,
                        target_price=target_price,
                        stop_loss=stop_loss,
                        confidence_score=confidence,
                        confidence_level='HIGH',
                        risk_reward_ratio=1.6,
                        timeframe=timeframe,
                        entry_point_type='DIVERGENCE',
                        quality_score=confidence,
                        strength='STRONG',
                        notes='Bullish RSI divergence detected',
                        is_valid=True,
                        expires_at=current_peak.name + timedelta(hours=24),
                        created_at=current_peak.name,
                        metadata={
                            'strategy': 'DIVERGENCE_DETECTION',
                            'divergence_type': 'bullish',
                            'price_at_signal': current_peak['close'],
                            'rsi_at_signal': current_peak['RSI']
                        }
                    )
                    
                    signals.append(signal)
            
            # Similar logic for bearish divergences with troughs
            for i in range(1, len(troughs)):
                current_trough = troughs.iloc[i]
                previous_trough = troughs.iloc[i-1]
                
                # Bearish divergence: price makes higher low, RSI makes lower low
                if (current_trough['close'] > previous_trough['close'] and 
                    current_trough['RSI'] < previous_trough['RSI']):
                    
                    signal_type, _ = SignalType.objects.get_or_create(
                        name='SELL',
                        defaults={'description': 'SELL signal from bearish divergence'}
                    )
                    
                    confidence = 0.85
                    entry_price = Decimal(str(current_trough['close']))
                    # Capital-based calculation: $60 profit target, $50 stop loss based on $100 capital
                    capital_per_trade = Decimal('100.00')  # $100 capital investment
                    max_loss_amount = Decimal('50.00')     # $50 max loss
                    profit_target_amount = Decimal('60.00')  # $60 profit target
                    
                    # Calculate position size
                    position_size = capital_per_trade / entry_price
                    
                    target_price = entry_price - (profit_target_amount / position_size)  # $60 profit for sell
                    stop_loss = entry_price + (max_loss_amount / position_size)  # $50 loss for sell
                    
                    signal = TradingSignal(
                        symbol=symbol,
                        signal_type=signal_type,
                        entry_price=entry_price,
                        target_price=target_price,
                        stop_loss=stop_loss,
                        confidence_score=confidence,
                        confidence_level='HIGH',
                        risk_reward_ratio=1.6,
                        timeframe=timeframe,
                        entry_point_type='DIVERGENCE',
                        quality_score=confidence,
                        strength='STRONG',
                        notes='Bearish RSI divergence detected',
                        is_valid=True,
                        expires_at=current_trough.name + timedelta(hours=24),
                        created_at=current_trough.name,
                        metadata={
                            'strategy': 'DIVERGENCE_DETECTION',
                            'divergence_type': 'bearish',
                            'price_at_signal': current_trough['close'],
                            'rsi_at_signal': current_trough['RSI']
                        }
                    )
                    
                    signals.append(signal)
                    
        except Exception as e:
            self.logger.error(f"Error in Divergence strategy: {e}")
        
        return signals
    
    def _candlestick_patterns_strategy(self, symbol: Symbol, data: pd.DataFrame, config: dict, timeframe: str) -> List[TradingSignal]:
        """Candlestick Patterns Strategy."""
        signals = []
        try:
            patterns = config.get('patterns', ['DOJI', 'HAMMER', 'SHOOTING_STAR', 'ENGULFING'])
            
            # Calculate candlestick pattern indicators
            open_prices = data['open'].values
            high_prices = data['high'].values
            low_prices = data['low'].values
            close_prices = data['close'].values
            
            pattern_functions = {
                'DOJI': talib.CDLDOJI,
                'HAMMER': talib.CDLHAMMER,
                'SHOOTING_STAR': talib.CDLSHOOTINGSTAR,
                'ENGULFING': talib.CDLENGULFING
            }
            
            for pattern_name in patterns:
                if pattern_name in pattern_functions:
                    pattern_result = pattern_functions[pattern_name](
                        open_prices, high_prices, low_prices, close_prices
                    )
                    
                    data[f'{pattern_name}_pattern'] = pattern_result
                    
                    # Find pattern occurrences
                    for idx, value in enumerate(pattern_result):
                        if value != 0:  # Pattern detected
                            timestamp = data.index[idx]
                            row = data.iloc[idx]
                            
                            # Determine signal direction based on pattern
                            if pattern_name in ['HAMMER'] or value > 0:
                                signal_type_name = 'BUY'
                            elif pattern_name in ['SHOOTING_STAR'] or value < 0:
                                signal_type_name = 'SELL'
                            else:
                                continue  # Skip neutral patterns
                            
                            # Get or create signal type
                            signal_type, _ = SignalType.objects.get_or_create(
                                name=signal_type_name,
                                defaults={'description': f'{signal_type_name} signal from {pattern_name} pattern'}
                            )
                            
                            confidence = 0.7  # Medium confidence for candlestick patterns
                            entry_price = Decimal(str(row['close']))
                            
                            # Capital-based calculation: 60% profit target, 50% stop loss
                            capital_allocation_percentage = Decimal('0.50')  # 50% of capital at risk
                            profit_target_percentage = Decimal('0.60')  # 60% profit target
                            
                            if signal_type_name == 'BUY':
                                target_price = entry_price * (Decimal('1.0') + profit_target_percentage)  # 60% profit
                                stop_loss = entry_price * (Decimal('1.0') - capital_allocation_percentage)  # 50% stop loss
                            else:
                                target_price = entry_price * (Decimal('1.0') - profit_target_percentage)  # 60% profit for sell
                                stop_loss = entry_price * (Decimal('1.0') + capital_allocation_percentage)  # 50% stop loss for sell
                            
                            signal = TradingSignal(
                                symbol=symbol,
                                signal_type=signal_type,
                                entry_price=entry_price,
                                target_price=target_price,
                                stop_loss=stop_loss,
                                confidence_score=confidence,
                                confidence_level='MEDIUM',
                                risk_reward_ratio=1.67,
                                timeframe=timeframe,
                                entry_point_type='CANDLESTICK_PATTERN',
                                quality_score=confidence,
                                strength='MEDIUM',
                                notes=f'{pattern_name} candlestick pattern detected',
                                is_valid=True,
                                expires_at=timestamp + timedelta(hours=6),
                                created_at=timestamp,
                                metadata={
                                    'strategy': 'CANDLESTICK_PATTERNS',
                                    'pattern_name': pattern_name,
                                    'pattern_strength': abs(value),
                                    'price_at_signal': row['close']
                                }
                            )
                            
                            signals.append(signal)
                            
        except Exception as e:
            self.logger.error(f"Error in Candlestick Patterns strategy: {e}")
        
        return signals
    
    def _deduplicate_signals(self, signals: List[TradingSignal]) -> List[TradingSignal]:
        """Remove duplicate signals based on time and price proximity."""
        if not signals:
            return signals
        
        unique_signals = []
        time_threshold = timedelta(hours=6)  # Signals within 6 hours are considered duplicates
        price_threshold = 0.02  # 2% price difference threshold
        
        for signal in signals:
            is_duplicate = False
            
            # Skip signals without timestamps
            if not signal.created_at:
                unique_signals.append(signal)
                continue
            
            for existing_signal in unique_signals:
                # Skip comparison if existing signal has no timestamp
                if not existing_signal.created_at:
                    continue
                    
                # Check time proximity
                time_diff = abs((signal.created_at - existing_signal.created_at).total_seconds())
                if time_diff <= time_threshold.total_seconds():
                    
                    # Check price proximity
                    price_diff = abs(float(signal.entry_price) - float(existing_signal.entry_price))
                    price_pct = price_diff / float(existing_signal.entry_price)
                    
                    # Check if same signal type
                    if (price_pct <= price_threshold and 
                        signal.signal_type.name == existing_signal.signal_type.name):
                        
                        # Keep the signal with higher confidence
                        if signal.confidence_score > existing_signal.confidence_score:
                            unique_signals.remove(existing_signal)
                        else:
                            is_duplicate = True
                        break
            
            if not is_duplicate:
                unique_signals.append(signal)
        
        self.logger.info(f"Deduplication: {len(signals)} signals -> {len(unique_signals)} unique signals")
        return unique_signals
    
    def _save_signals_to_database(self, signals: List[TradingSignal]):
        """Save signals to database efficiently."""
        try:
            # Use bulk_create for efficiency
            TradingSignal.objects.bulk_create(signals, ignore_conflicts=True)
            self.logger.info(f"Bulk created {len(signals)} comprehensive signals")
            
        except Exception as e:
            self.logger.error(f"Error saving signals to database: {e}")
    
    def _thirty_minute_timeframe_strategy(self, symbol: Symbol, data: pd.DataFrame, config: dict, timeframe: str) -> List[TradingSignal]:
        """
        Implements the user's 30-minute timeframe strategy:
        - Analyze historical data to find previous high (resistance) and previous low (support)
        - For BUY signals: Support = Take Profit, Previous High = Stop Loss
        - For SELL signals: Previous High = Take Profit, Support = Stop Loss
        - If previous high/low not clear, predict possible values
        """
        signals = []
        try:
            self.logger.info(f"Applying 30-minute timeframe strategy to {symbol.symbol}")
            
            # Configuration from strategy config
            lookback_periods = config.get('lookback_periods', 50)
            support_resistance_buffer = config.get('support_resistance_buffer', 0.02)
            min_distance_percentage = config.get('min_distance_percentage', 0.05)
            
            if len(data) < lookback_periods:
                self.logger.warning(f"Insufficient data for {symbol.symbol}: {len(data)} points, need {lookback_periods}")
                return signals
            
            # Analyze historical data to find resistance (previous high) and support (previous low)
            # Use rolling windows to identify peaks and troughs
            rolling_window = min(10, len(data) // 4)  # Adaptive window size
            
            # Find resistance levels (previous highs)
            data['rolling_max'] = data['high'].rolling(window=rolling_window, center=True).max()
            resistance_candidates = data[data['high'] == data['rolling_max']].copy()
            
            # Find support levels (previous lows)
            data['rolling_min'] = data['low'].rolling(window=rolling_window, center=True).min()
            support_candidates = data[data['low'] == data['rolling_min']].copy()
            
            # Filter recent resistance and support levels
            current_price = float(data['close'].iloc[-1])
            
            # Get recent resistance from lookback period
            recent_data = data.tail(lookback_periods)
            recent_resistance_levels = resistance_candidates.loc[recent_data.index] if len(resistance_candidates) > 0 else pd.DataFrame()
            resistance_level = recent_resistance_levels['high'].max() if not recent_resistance_levels.empty else None
            
            # Get recent support from lookback period  
            recent_support_levels = support_candidates.loc[recent_data.index] if len(support_candidates) > 0 else pd.DataFrame()
            support_level = recent_support_levels['low'].min() if not recent_support_levels.empty else None
            
            # Validate levels and predict if not clear
            if resistance_level is not None and abs(resistance_level - current_price) / current_price < support_resistance_buffer:
                resistance_level = None  # Too close to current price
                
            if support_level is not None and abs(support_level - current_price) / current_price < support_resistance_buffer:
                support_level = None  # Too close to current price
            
            # Predict levels if not found
            if resistance_level is None or support_level is None:
                volatility = data['close'].pct_change().std() * data['close'].mean()
                prediction_buffer = max(min_distance_percentage, volatility * 2)
                
                if resistance_level is None:
                    resistance_level = current_price * (1 + prediction_buffer)
                    self.logger.info(f"Predicted resistance level for {symbol.symbol}: {resistance_level:.6f}")
                    
                if support_level is None:
                    support_level = current_price * (1 - prediction_buffer)
                    self.logger.info(f"Predicted support level for {symbol.symbol}: {support_level:.6f}")
            
            # Generate BUY signals when price approaches support
            if support_level and support_level < current_price:
                # BUY signal: Support = Take Profit, Resistance = Stop Loss
                entry_price = Decimal(str(current_price))
                take_profit = Decimal(str(support_level))
                stop_loss = Decimal(str(resistance_level))
                
                # Validate signal logic
                if take_profit < entry_price and stop_loss > entry_price:
                    signal_type, _ = SignalType.objects.get_or_create(
                        name='BUY',
                        defaults={'description': 'Buy signal from 30-minute timeframe strategy'}
                    )
                    
                    # Calculate confidence based on distance from levels
                    distance_to_tp = float(abs(entry_price - take_profit) / entry_price)
                    distance_to_sl = float(abs(stop_loss - entry_price) / entry_price)
                    confidence = min(0.95, max(0.6, (distance_to_tp + distance_to_sl) * 25))
                    
                    signal = TradingSignal(
                        symbol=symbol,
                        signal_type=signal_type,
                        entry_price=entry_price,
                        target_price=take_profit,
                        stop_loss=stop_loss,
                        strength='STRONG',
                        confidence_score=confidence,
                        confidence_level='HIGH',
                        risk_reward_ratio=distance_to_tp / distance_to_sl if distance_to_sl > 0 else 1.0,
                        quality_score=confidence * 0.8,  # Quality based on confidence
                        timeframe=timeframe,
                        entry_point_type='SUPPORT_BOUNCE',
                        notes=f'30-minute strategy: TP={support_level:.6f} (support), SL={resistance_level:.6f} (resistance)',
                        is_valid=True,
                        created_at=data.index[-1].to_pydatetime(),
                        is_hybrid=False,
                        metadata={
                            'strategy': 'THIRTY_MINUTE_TIMEFRAME',
                            'resistance_level': float(resistance_level),
                            'support_level': float(support_level),
                            'levels_found': not (resistance_candidates.empty and support_candidates.empty),
                            'prediction_buffer': prediction_buffer if resistance_level is None or support_level is None else None
                        }
                    )
                    
                    signals.append(signal)
                    self.logger.info(f"Generated BUY signal for {symbol.symbol}: Entry={entry_price}, TP={take_profit}, SL={stop_loss}")
            
            # Generate SELL signals when price approaches resistance
            if resistance_level and resistance_level > current_price:
                # SELL signal: Resistance = Take Profit, Support = Stop Loss
                entry_price = Decimal(str(current_price))
                take_profit = Decimal(str(resistance_level))
                stop_loss = Decimal(str(support_level))
                
                # Validate signal logic
                if take_profit > entry_price and stop_loss < entry_price:
                    signal_type, _ = SignalType.objects.get_or_create(
                        name='SELL',
                        defaults={'description': 'Sell signal from 30-minute timeframe strategy'}
                    )
                    
                    # Calculate confidence based on distance from levels
                    distance_to_tp = float(abs(take_profit - entry_price) / entry_price)
                    distance_to_sl = float(abs(entry_price - stop_loss) / entry_price)
                    confidence = min(0.95, max(0.6, (distance_to_tp + distance_to_sl) * 25))
                    
                    signal = TradingSignal(
                        symbol=symbol,
                        signal_type=signal_type,
                        entry_price=entry_price,
                        target_price=take_profit,
                        stop_loss=stop_loss,
                        strength='STRONG',
                        confidence_score=confidence,
                        confidence_level='HIGH',
                        risk_reward_ratio=distance_to_tp / distance_to_sl if distance_to_sl > 0 else 1.0,
                        quality_score=confidence * 0.8,  # Quality based on confidence
                        timeframe=timeframe,
                        entry_point_type='RESISTANCE_REJECTION',
                        notes=f'30-minute strategy: TP={resistance_level:.6f} (resistance), SL={support_level:.6f} (support)',
                        is_valid=True,
                        created_at=data.index[-1].to_pydatetime(),
                        is_hybrid=False,
                        metadata={
                            'strategy': 'THIRTY_MINUTE_TIMEFRAME',
                            'resistance_level': float(resistance_level),
                            'support_level': float(support_level),
                            'levels_found': not (resistance_candidates.empty and support_candidates.empty),
                            'prediction_buffer': prediction_buffer if resistance_level is None or support_level is None else None
                        }
                    )
                    
                    signals.append(signal)
                    self.logger.info(f"Generated SELL signal for {symbol.symbol}: Entry={entry_price}, TP={take_profit}, SL={stop_loss}")
            
            self.logger.info(f"Generated {len(signals)} signals from 30-minute timeframe strategy for {symbol.symbol}")
            
        except Exception as e:
            self.logger.error(f"Error in 30-minute timeframe strategy for {symbol.symbol}: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            
        return signals

