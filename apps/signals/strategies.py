import logging
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
import numpy as np
from django.utils import timezone
from django.db.models import Q

from apps.signals.models import TradingSignal, SignalType
from apps.trading.models import Symbol
from apps.data.models import TechnicalIndicator, MarketData

logger = logging.getLogger(__name__)


class BaseStrategy:
    """Base class for all trading strategies"""
    
    def __init__(self):
        self.name = self.__class__.__name__
        self.min_confidence_threshold = 0.7
        self.min_risk_reward_ratio = 3.0
        
    def generate_signals(self, symbol: Symbol) -> List[TradingSignal]:
        """Generate trading signals for a symbol"""
        raise NotImplementedError("Subclasses must implement generate_signals")
    
    def _get_latest_indicators(self, symbol: Symbol, indicator_type: str, period: int, limit: int = 5) -> List[TechnicalIndicator]:
        """Get latest technical indicators for a symbol"""
        try:
            return list(TechnicalIndicator.objects.filter(
                symbol=symbol,
                indicator_type=indicator_type,
                period=period
            ).order_by('-timestamp')[:limit])
        except Exception as e:
            logger.error(f"Error getting {indicator_type} indicators for {symbol.symbol}: {e}")
            return []
    
    def _get_latest_price(self, symbol: Symbol) -> Optional[float]:
        """Get latest price for a symbol - prioritizes live prices"""
        try:
            # First, try to get live prices from external API
            try:
                from apps.data.real_price_service import get_live_prices
                live_prices = get_live_prices()
                
                if symbol.symbol in live_prices:
                    live_data = live_prices[symbol.symbol]
                    current_price = live_data.get('price', 0)
                    
                    if current_price and current_price > 0:
                        logger.info(f"Using live price for {symbol.symbol}: ${current_price:,.2f}")
                        return float(current_price)
                    else:
                        logger.warning(f"Invalid live price for {symbol.symbol}: {current_price}")
                
            except Exception as e:
                logger.warning(f"Could not fetch live price for {symbol.symbol}: {e}")
            
            # Fallback to database data if live prices unavailable
            latest_data = MarketData.objects.filter(
                symbol=symbol
            ).order_by('-timestamp').first()
            
            if latest_data:
                database_price = float(latest_data.close_price)
                logger.warning(f"Using database price for {symbol.symbol}: ${database_price:,.2f} (age: {timezone.now() - latest_data.timestamp})")
                return database_price
            
            logger.error(f"No price data found for {symbol.symbol}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting latest price for {symbol.symbol}: {e}")
            return None


class MovingAverageCrossoverStrategy(BaseStrategy):
    """Moving Average Crossover Strategy
    
    Generates signals based on:
    1. 20 SMA vs 50 SMA crossover (trend following)
    2. 10 EMA vs 20 EMA crossover (momentum)
    """
    
    def __init__(self):
        super().__init__()
        self.name = "Moving Average Crossover"
        self.description = "Generates signals based on moving average crossovers"
        
        # Strategy parameters
        self.sma_short_period = 20
        self.sma_long_period = 50
        self.ema_short_period = 10
        self.ema_long_period = 20
        
        # Signal thresholds
        self.crossover_threshold = 0.001  # 0.1% minimum crossover
        self.volume_confirmation = True   # Require volume confirmation
        
    def generate_signals(self, symbol: Symbol) -> List[TradingSignal]:
        """Generate trading signals based on moving average crossovers"""
        try:
            signals = []
            
            # Get latest moving averages
            sma_short = self._get_latest_indicators(symbol, 'SMA', self.sma_short_period, 2)
            sma_long = self._get_latest_indicators(symbol, 'SMA', self.sma_long_period, 2)
            ema_short = self._get_latest_indicators(symbol, 'EMA', self.ema_short_period, 2)
            ema_long = self._get_latest_indicators(symbol, 'EMA', self.ema_long_period, 2)
            
            if not all([sma_short, sma_long, ema_short, ema_long]):
                logger.warning(f"Insufficient moving average data for {symbol.symbol}")
                return signals
            
            # Get current price
            current_price = self._get_latest_price(symbol)
            if not current_price:
                return signals
            
            # Check SMA crossover (20 vs 50)
            sma_signal = self._check_sma_crossover(sma_short, sma_long, current_price)
            if sma_signal:
                signals.append(sma_signal)
            
            # Check EMA crossover (10 vs 20)
            ema_signal = self._check_ema_crossover(ema_short, ema_long, current_price)
            if ema_signal:
                signals.append(ema_signal)
            
            # Check for strong signals (both crossovers aligned)
            strong_signal = self._check_strong_signal(symbol, sma_short, sma_long, ema_short, ema_long, current_price)
            if strong_signal:
                signals.append(strong_signal)
            
            logger.info(f"Generated {len(signals)} MA crossover signals for {symbol.symbol}")
            return signals
            
        except Exception as e:
            logger.error(f"Error generating MA crossover signals for {symbol.symbol}: {e}")
            return []
    
    def _check_sma_crossover(self, sma_short: List[TechnicalIndicator], 
                            sma_long: List[TechnicalIndicator], 
                            current_price: float) -> Optional[TradingSignal]:
        """Check for SMA crossover signals"""
        try:
            if len(sma_short) < 2 or len(sma_long) < 2:
                return None
            
            # Current and previous values
            current_sma_short = float(sma_short[0].value)
            previous_sma_short = float(sma_short[1].value)
            current_sma_long = float(sma_long[0].value)
            previous_sma_long = float(sma_long[1].value)
            
            # Calculate crossover
            current_diff = current_sma_short - current_sma_long
            previous_diff = previous_sma_short - previous_sma_long
            
            # Check for bullish crossover (short crosses above long)
            if (previous_diff <= 0 and current_diff > 0 and 
                abs(current_diff) > self.crossover_threshold * current_price):
                
                signal_type = self._get_or_create_signal_type('BUY')
                confidence_score = self._calculate_sma_confidence(current_diff, current_price)
                
                if confidence_score >= self.min_confidence_threshold:
                    return self._create_signal(
                        symbol=symbol,
                        signal_type=signal_type,
                        confidence_score=confidence_score,
                        entry_price=current_price,
                        target_price=current_price * 1.05,  # 5% target
                        stop_loss=current_price * 0.98,    # 2% stop loss
                        strength='STRONG' if confidence_score > 0.8 else 'MODERATE',
                        notes=f"SMA Crossover: 20 SMA ({current_sma_short:.4f}) crossed above 50 SMA ({current_sma_long:.4f})"
                    )
            
            # Check for bearish crossover (short crosses below long)
            elif (previous_diff >= 0 and current_diff < 0 and 
                  abs(current_diff) > self.crossover_threshold * current_price):
                
                signal_type = self._get_or_create_signal_type('SELL')
                confidence_score = self._calculate_sma_confidence(abs(current_diff), current_price)
                
                if confidence_score >= self.min_confidence_threshold:
                    return self._create_signal(
                        symbol=symbol,
                        signal_type=signal_type,
                        confidence_score=confidence_score,
                        entry_price=current_price,
                        target_price=current_price * 0.95,  # 5% target
                        stop_loss=current_price * 1.02,    # 2% stop loss
                        strength='STRONG' if confidence_score > 0.8 else 'MODERATE',
                        notes=f"SMA Crossover: 20 SMA ({current_sma_short:.4f}) crossed below 50 SMA ({current_sma_long:.4f})"
                    )
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking SMA crossover: {e}")
            return None
    
    def _check_ema_crossover(self, ema_short: List[TechnicalIndicator], 
                            ema_long: List[TechnicalIndicator], 
                            current_price: float) -> Optional[TradingSignal]:
        """Check for EMA crossover signals"""
        try:
            if len(ema_short) < 2 or len(ema_long) < 2:
                return None
            
            # Current and previous values
            current_ema_short = float(ema_short[0].value)
            previous_ema_short = float(ema_short[1].value)
            current_ema_long = float(ema_long[0].value)
            previous_ema_long = float(ema_long[1].value)
            
            # Calculate crossover
            current_diff = current_ema_short - current_ema_long
            previous_diff = previous_ema_short - previous_ema_long
            
            # Check for bullish crossover (short crosses above long)
            if (previous_diff <= 0 and current_diff > 0 and 
                abs(current_diff) > self.crossover_threshold * current_price):
                
                signal_type = self._get_or_create_signal_type('BUY')
                confidence_score = self._calculate_ema_confidence(current_diff, current_price)
                
                if confidence_score >= self.min_confidence_threshold:
                    return self._create_signal(
                        symbol=symbol,
                        signal_type=signal_type,
                        confidence_score=confidence_score,
                        entry_price=current_price,
                        target_price=current_price * 1.03,  # 3% target (shorter term)
                        stop_loss=current_price * 0.99,    # 1% stop loss
                        strength='MODERATE',
                        notes=f"EMA Crossover: 10 EMA ({current_ema_short:.4f}) crossed above 20 EMA ({current_ema_long:.4f})"
                    )
            
            # Check for bearish crossover (short crosses below long)
            elif (previous_diff >= 0 and current_diff < 0 and 
                  abs(current_diff) > self.crossover_threshold * current_price):
                
                signal_type = self._get_or_create_signal_type('SELL')
                confidence_score = self._calculate_ema_confidence(abs(current_diff), current_price)
                
                if confidence_score >= self.min_confidence_threshold:
                    return self._create_signal(
                        symbol=symbol,
                        signal_type=signal_type,
                        confidence_score=confidence_score,
                        entry_price=current_price,
                        target_price=current_price * 0.97,  # 3% target (shorter term)
                        stop_loss=current_price * 1.01,    # 1% stop loss
                        strength='MODERATE',
                        notes=f"EMA Crossover: 10 EMA ({current_ema_short:.4f}) crossed below 20 EMA ({current_ema_long:.4f})"
                    )
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking EMA crossover: {e}")
            return None
    
    def _check_strong_signal(self, symbol: Symbol, sma_short: List[TechnicalIndicator], 
                            sma_long: List[TechnicalIndicator],
                            ema_short: List[TechnicalIndicator], 
                            ema_long: List[TechnicalIndicator],
                            current_price: float) -> Optional[TradingSignal]:
        """Check for strong signals when both crossovers align"""
        try:
            if len(sma_short) < 2 or len(sma_long) < 2 or len(ema_short) < 2 or len(ema_long) < 2:
                return None
            
            # Current values
            current_sma_short = float(sma_short[0].value)
            current_sma_long = float(sma_long[0].value)
            current_ema_short = float(ema_short[0].value)
            current_ema_long = float(ema_long[0].value)
            
            # Check if both crossovers are bullish
            sma_bullish = current_sma_short > current_sma_long
            ema_bullish = current_ema_short > current_ema_long
            
            if sma_bullish and ema_bullish:
                # Strong bullish signal
                signal_type = self._get_or_create_signal_type('STRONG_BUY')
                confidence_score = 0.9  # High confidence for aligned signals
                
                return self._create_signal(
                    symbol=symbol,
                    signal_type=signal_type,
                    confidence_score=confidence_score,
                    entry_price=current_price,
                    target_price=current_price * 1.08,  # 8% target
                    stop_loss=current_price * 0.97,    # 3% stop loss
                    strength='VERY_STRONG',
                    notes=f"Strong Signal: Both SMA and EMA crossovers are bullish. 20 SMA above 50 SMA, 10 EMA above 20 EMA"
                )
            
            # Check if both crossovers are bearish
            sma_bearish = current_sma_short < current_sma_long
            ema_bearish = current_ema_short < current_ema_long
            
            if sma_bearish and ema_bearish:
                # Strong bearish signal
                signal_type = self._get_or_create_signal_type('STRONG_SELL')
                confidence_score = 0.9  # High confidence for aligned signals
                
                return self._create_signal(
                    symbol=symbol,
                    signal_type=signal_type,
                    confidence_score=confidence_score,
                    entry_price=current_price,
                    target_price=current_price * 0.92,  # 8% target
                    stop_loss=current_price * 1.03,    # 3% stop loss
                    strength='VERY_STRONG',
                    notes=f"Strong Signal: Both SMA and EMA crossovers are bearish. 20 SMA below 50 SMA, 10 EMA below 20 EMA"
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking strong signal: {e}")
            return None
    
    def _calculate_sma_confidence(self, crossover_diff: float, current_price: float) -> float:
        """Calculate confidence score for SMA crossover"""
        try:
            # Normalize crossover difference
            normalized_diff = abs(crossover_diff) / current_price
            
            # Base confidence on crossover strength
            if normalized_diff > 0.01:  # >1% crossover
                base_confidence = 0.9
            elif normalized_diff > 0.005:  # >0.5% crossover
                base_confidence = 0.8
            elif normalized_diff > 0.002:  # >0.2% crossover
                base_confidence = 0.7
            else:
                base_confidence = 0.6
            
            # Add volume confirmation bonus (if implemented)
            volume_bonus = 0.05 if self.volume_confirmation else 0.0
            
            return min(1.0, base_confidence + volume_bonus)
            
        except Exception as e:
            logger.error(f"Error calculating SMA confidence: {e}")
            return 0.7
    
    def _calculate_ema_confidence(self, crossover_diff: float, current_price: float) -> float:
        """Calculate confidence score for EMA crossover"""
        try:
            # Normalize crossover difference
            normalized_diff = abs(crossover_diff) / current_price
            
            # EMA crossovers are typically shorter-term, so lower confidence
            if normalized_diff > 0.01:  # >1% crossover
                base_confidence = 0.8
            elif normalized_diff > 0.005:  # >0.5% crossover
                base_confidence = 0.7
            elif normalized_diff > 0.002:  # >0.2% crossover
                base_confidence = 0.6
            else:
                base_confidence = 0.5
            
            return base_confidence
            
        except Exception as e:
            logger.error(f"Error calculating EMA confidence: {e}")
            return 0.6
    
    def _get_or_create_signal_type(self, signal_name: str) -> SignalType:
        """Get or create a signal type"""
        try:
            signal_type, created = SignalType.objects.get_or_create(
                name=signal_name,
                defaults={
                    'description': f'{signal_name} signal from Moving Average Crossover Strategy',
                    'color': '#28a745' if 'BUY' in signal_name else '#dc3545',
                    'is_active': True
                }
            )
            return signal_type
        except Exception as e:
            logger.error(f"Error getting/creating signal type {signal_name}: {e}")
            # Return a default signal type
            return SignalType.objects.filter(name='BUY').first() or SignalType.objects.first()
    
    def _create_signal(self, symbol: Symbol, signal_type: SignalType, 
                       confidence_score: float, entry_price: float,
                       target_price: float, stop_loss: float,
                       strength: str, notes: str) -> TradingSignal:
        """Create a trading signal"""
        try:
            # Calculate risk-reward ratio
            risk = abs(entry_price - stop_loss)
            reward = abs(target_price - entry_price)
            risk_reward_ratio = reward / risk if risk > 0 else 0
            
            # Calculate quality score
            quality_score = (confidence_score * 0.6 + 
                           min(1.0, risk_reward_ratio / 3.0) * 0.4)
            
            # Determine confidence level
            if confidence_score >= 0.85:
                confidence_level = 'VERY_HIGH'
            elif confidence_score >= 0.7:
                confidence_level = 'HIGH'
            elif confidence_score >= 0.5:
                confidence_level = 'MEDIUM'
            else:
                confidence_level = 'LOW'
            
            # Create signal
            signal = TradingSignal.objects.create(
                symbol=symbol,
                signal_type=signal_type,
                strength=strength,
                confidence_score=confidence_score,
                confidence_level=confidence_level,
                entry_price=Decimal(str(entry_price)),
                target_price=Decimal(str(target_price)),
                stop_loss=Decimal(str(stop_loss)),
                risk_reward_ratio=risk_reward_ratio,
                quality_score=quality_score,
                is_valid=True,
                expires_at=timezone.now() + timezone.timedelta(hours=24),
                technical_score=confidence_score,  # MA crossover is purely technical
                sentiment_score=0.0,
                news_score=0.0,
                volume_score=0.0,
                pattern_score=0.0,
                # New timeframe and entry point fields
                timeframe='1H',  # Default timeframe for strategies
                entry_point_type='TREND_FOLLOWING',  # Default entry point type
                entry_point_details={},
                entry_zone_low=Decimal(str(entry_price * 0.99)),  # 1% below entry
                entry_zone_high=Decimal(str(entry_price * 1.01)),  # 1% above entry
                entry_confidence=confidence_score,  # Use confidence score as entry confidence
                notes=notes
            )
            
            logger.info(f"Created {signal_type.name} signal for {symbol.symbol} with confidence {confidence_score:.2f}")
            return signal
            
        except Exception as e:
            logger.error(f"Error creating signal: {e}")
            return None


class RSIStrategy(BaseStrategy):
    """RSI Strategy
    
    Generates signals based on:
    1. Oversold conditions (RSI < 30) - BUY signals
    2. Overbought conditions (RSI > 70) - SELL signals
    3. RSI divergence detection
    """
    
    def __init__(self):
        super().__init__()
        self.name = "RSI Strategy"
        self.description = "Generates signals based on RSI oversold/overbought conditions and divergence"
        
        # Strategy parameters
        self.rsi_period = 14
        self.oversold_threshold = 30
        self.overbought_threshold = 70
        self.extreme_oversold = 20
        self.extreme_overbought = 80
        
        # Divergence parameters
        self.divergence_lookback = 5  # Look back 5 periods for divergence
        self.min_divergence_strength = 0.02  # 2% minimum price movement for divergence
        
    def generate_signals(self, symbol: Symbol) -> List[TradingSignal]:
        """Generate trading signals based on RSI analysis"""
        try:
            signals = []
            
            # Get RSI indicators
            rsi_indicators = self._get_latest_indicators(symbol, 'RSI', self.rsi_period, 10)
            if len(rsi_indicators) < 2:
                logger.warning(f"Insufficient RSI data for {symbol.symbol}")
                return signals
            
            # Get current price
            current_price = self._get_latest_price(symbol)
            if not current_price:
                return signals
            
            # Get market data for divergence analysis
            market_data = self._get_market_data_for_divergence(symbol, 10)
            
            # Check oversold signals
            oversold_signal = self._check_oversold_signal(symbol, rsi_indicators, current_price)
            if oversold_signal:
                signals.append(oversold_signal)
            
            # Check overbought signals
            overbought_signal = self._check_overbought_signal(symbol, rsi_indicators, current_price)
            if overbought_signal:
                signals.append(overbought_signal)
            
            # Check divergence signals
            if market_data:
                divergence_signals = self._check_divergence_signals(symbol, rsi_indicators, market_data, current_price)
                signals.extend(divergence_signals)
            
            logger.info(f"Generated {len(signals)} RSI signals for {symbol.symbol}")
            return signals
            
        except Exception as e:
            logger.error(f"Error generating RSI signals for {symbol.symbol}: {e}")
            return []
    
    def _get_market_data_for_divergence(self, symbol: Symbol, limit: int = 10) -> List[Dict]:
        """Get market data for divergence analysis"""
        try:
            market_data = MarketData.objects.filter(
                symbol=symbol
            ).order_by('-timestamp')[:limit]
            
            return [
                {
                    'timestamp': data.timestamp,
                    'close_price': float(data.close_price),
                    'high_price': float(data.high_price),
                    'low_price': float(data.low_price)
                }
                for data in market_data
            ]
        except Exception as e:
            logger.error(f"Error getting market data for divergence: {e}")
            return []
    
    def _check_oversold_signal(self, symbol: Symbol, rsi_indicators: List[TechnicalIndicator], 
                               current_price: float) -> Optional[TradingSignal]:
        """Check for oversold signals"""
        try:
            current_rsi = float(rsi_indicators[0].value)
            
            # Check for oversold condition
            if current_rsi <= self.oversold_threshold:
                signal_type = self._get_or_create_signal_type('BUY')
                
                # Calculate confidence based on how oversold
                if current_rsi <= self.extreme_oversold:
                    confidence_score = 0.9  # Very high confidence for extreme oversold
                    strength = 'VERY_STRONG'
                    target_multiplier = 1.08  # 8% target for extreme oversold
                    stop_multiplier = 0.97    # 3% stop loss
                elif current_rsi <= 25:
                    confidence_score = 0.8
                    strength = 'STRONG'
                    target_multiplier = 1.06  # 6% target
                    stop_multiplier = 0.98    # 2% stop loss
                else:
                    confidence_score = 0.75
                    strength = 'MODERATE'
                    target_multiplier = 1.04  # 4% target
                    stop_multiplier = 0.99    # 1% stop loss
                
                # Check if RSI is starting to turn up (additional confirmation)
                if len(rsi_indicators) >= 2:
                    previous_rsi = float(rsi_indicators[1].value)
                    if current_rsi > previous_rsi:
                        confidence_score += 0.05  # Bonus for RSI turning up
                
                confidence_score = min(1.0, confidence_score)
                
                if confidence_score >= self.min_confidence_threshold:
                    return self._create_signal(
                        symbol=symbol,
                        signal_type=signal_type,
                        confidence_score=confidence_score,
                        entry_price=current_price,
                        target_price=current_price * target_multiplier,
                        stop_loss=current_price * stop_multiplier,
                        strength=strength,
                        notes=f"RSI Oversold: RSI({current_rsi:.1f}) <= {self.oversold_threshold}. Strong bounce potential from oversold levels."
                    )
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking oversold signal: {e}")
            return None
    
    def _check_overbought_signal(self, symbol: Symbol, rsi_indicators: List[TechnicalIndicator], 
                                 current_price: float) -> Optional[TradingSignal]:
        """Check for overbought signals"""
        try:
            current_rsi = float(rsi_indicators[0].value)
            
            # Check for overbought condition
            if current_rsi >= self.overbought_threshold:
                signal_type = self._get_or_create_signal_type('SELL')
                
                # Calculate confidence based on how overbought
                if current_rsi >= self.extreme_overbought:
                    confidence_score = 0.9  # Very high confidence for extreme overbought
                    strength = 'VERY_STRONG'
                    target_multiplier = 0.92  # 8% target for extreme overbought
                    stop_multiplier = 1.03    # 3% stop loss
                elif current_rsi >= 75:
                    confidence_score = 0.8
                    strength = 'STRONG'
                    target_multiplier = 0.94  # 6% target
                    stop_multiplier = 1.02    # 2% stop loss
                else:
                    confidence_score = 0.75
                    strength = 'MODERATE'
                    target_multiplier = 0.96  # 4% target
                    stop_multiplier = 1.01    # 1% stop loss
                
                # Check if RSI is starting to turn down (additional confirmation)
                if len(rsi_indicators) >= 2:
                    previous_rsi = float(rsi_indicators[1].value)
                    if current_rsi < previous_rsi:
                        confidence_score += 0.05  # Bonus for RSI turning down
                
                confidence_score = min(1.0, confidence_score)
                
                if confidence_score >= self.min_confidence_threshold:
                    return self._create_signal(
                        symbol=symbol,
                        signal_type=signal_type,
                        confidence_score=confidence_score,
                        entry_price=current_price,
                        target_price=current_price * target_multiplier,
                        stop_loss=current_price * stop_multiplier,
                        strength=strength,
                        notes=f"RSI Overbought: RSI({current_rsi:.1f}) >= {self.overbought_threshold}. Strong correction potential from overbought levels."
                    )
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking overbought signal: {e}")
            return None
    
    def _check_divergence_signals(self, symbol: Symbol, rsi_indicators: List[TechnicalIndicator], 
                                  market_data: List[Dict], current_price: float) -> List[TradingSignal]:
        """Check for RSI divergence signals"""
        signals = []
        
        try:
            if len(rsi_indicators) < self.divergence_lookback or len(market_data) < self.divergence_lookback:
                return signals
            
            # Check for bullish divergence (price makes lower lows, RSI makes higher lows)
            bullish_divergence = self._detect_bullish_divergence(rsi_indicators, market_data)
            if bullish_divergence:
                signal_type = self._get_or_create_signal_type('BUY')
                confidence_score = 0.85  # High confidence for divergence signals
                
                signal = self._create_signal(
                    symbol=symbol,
                    signal_type=signal_type,
                    confidence_score=confidence_score,
                    entry_price=current_price,
                    target_price=current_price * 1.06,  # 6% target
                    stop_loss=current_price * 0.97,    # 3% stop loss
                    strength='STRONG',
                    notes=f"RSI Bullish Divergence: Price made lower low but RSI made higher low. Strong reversal signal."
                )
                if signal:
                    signals.append(signal)
            
            # Check for bearish divergence (price makes higher highs, RSI makes lower highs)
            bearish_divergence = self._detect_bearish_divergence(rsi_indicators, market_data)
            if bearish_divergence:
                signal_type = self._get_or_create_signal_type('SELL')
                confidence_score = 0.85  # High confidence for divergence signals
                
                signal = self._create_signal(
                    symbol=symbol,
                    signal_type=signal_type,
                    confidence_score=confidence_score,
                    entry_price=current_price,
                    target_price=current_price * 0.94,  # 6% target
                    stop_loss=current_price * 1.03,    # 3% stop loss
                    strength='STRONG',
                    notes=f"RSI Bearish Divergence: Price made higher high but RSI made lower high. Strong reversal signal."
                )
                if signal:
                    signals.append(signal)
            
            return signals
            
        except Exception as e:
            logger.error(f"Error checking divergence signals: {e}")
            return signals
    
    def _detect_bullish_divergence(self, rsi_indicators: List[TechnicalIndicator], 
                                   market_data: List[Dict]) -> bool:
        """Detect bullish divergence pattern"""
        try:
            # Get recent RSI and price data
            recent_rsi = [float(ind.value) for ind in rsi_indicators[:self.divergence_lookback]]
            recent_lows = [data['low_price'] for data in market_data[:self.divergence_lookback]]
            
            # Find local minima in both price and RSI
            price_min_idx = recent_lows.index(min(recent_lows))
            rsi_min_idx = recent_rsi.index(min(recent_rsi))
            
            # For bullish divergence, we need:
            # 1. Recent low in price is lower than previous low
            # 2. Recent low in RSI is higher than previous low
            # 3. This should occur in oversold region
            
            if len(recent_lows) >= 3 and len(recent_rsi) >= 3:
                current_price_low = recent_lows[0]
                previous_price_low = min(recent_lows[1:])
                
                current_rsi_low = min(recent_rsi[:2])  # Recent RSI low
                previous_rsi_low = min(recent_rsi[2:])  # Previous RSI low
                
                # Check if we have lower low in price but higher low in RSI
                price_lower_low = current_price_low < previous_price_low
                rsi_higher_low = current_rsi_low > previous_rsi_low
                rsi_in_oversold = current_rsi_low <= self.oversold_threshold + 10  # Allow some buffer
                
                # Check if the divergence is significant enough
                price_change = abs(current_price_low - previous_price_low) / previous_price_low
                significant_change = price_change >= self.min_divergence_strength
                
                return (price_lower_low and rsi_higher_low and 
                       rsi_in_oversold and significant_change)
            
            return False
            
        except Exception as e:
            logger.error(f"Error detecting bullish divergence: {e}")
            return False
    
    def _detect_bearish_divergence(self, rsi_indicators: List[TechnicalIndicator], 
                                   market_data: List[Dict]) -> bool:
        """Detect bearish divergence pattern"""
        try:
            # Get recent RSI and price data
            recent_rsi = [float(ind.value) for ind in rsi_indicators[:self.divergence_lookback]]
            recent_highs = [data['high_price'] for data in market_data[:self.divergence_lookback]]
            
            # For bearish divergence, we need:
            # 1. Recent high in price is higher than previous high
            # 2. Recent high in RSI is lower than previous high
            # 3. This should occur in overbought region
            
            if len(recent_highs) >= 3 and len(recent_rsi) >= 3:
                current_price_high = recent_highs[0]
                previous_price_high = max(recent_highs[1:])
                
                current_rsi_high = max(recent_rsi[:2])  # Recent RSI high
                previous_rsi_high = max(recent_rsi[2:])  # Previous RSI high
                
                # Check if we have higher high in price but lower high in RSI
                price_higher_high = current_price_high > previous_price_high
                rsi_lower_high = current_rsi_high < previous_rsi_high
                rsi_in_overbought = current_rsi_high >= self.overbought_threshold - 10  # Allow some buffer
                
                # Check if the divergence is significant enough
                price_change = abs(current_price_high - previous_price_high) / previous_price_high
                significant_change = price_change >= self.min_divergence_strength
                
                return (price_higher_high and rsi_lower_high and 
                       rsi_in_overbought and significant_change)
            
            return False
            
        except Exception as e:
            logger.error(f"Error detecting bearish divergence: {e}")
            return False
    
    def _get_or_create_signal_type(self, signal_name: str) -> SignalType:
        """Get or create a signal type"""
        try:
            signal_type, created = SignalType.objects.get_or_create(
                name=signal_name,
                defaults={
                    'description': f'{signal_name} signal from RSI Strategy',
                    'color': '#28a745' if 'BUY' in signal_name else '#dc3545',
                    'is_active': True
                }
            )
            return signal_type
        except Exception as e:
            logger.error(f"Error getting/creating signal type {signal_name}: {e}")
            # Return a default signal type
            return SignalType.objects.filter(name='BUY').first() or SignalType.objects.first()
    
    def _create_signal(self, symbol: Symbol, signal_type: SignalType, 
                       confidence_score: float, entry_price: float,
                       target_price: float, stop_loss: float,
                       strength: str, notes: str) -> TradingSignal:
        """Create a trading signal"""
        try:
            # Calculate risk-reward ratio
            risk = abs(entry_price - stop_loss)
            reward = abs(target_price - entry_price)
            risk_reward_ratio = reward / risk if risk > 0 else 0
            
            # Calculate quality score
            quality_score = (confidence_score * 0.6 + 
                           min(1.0, risk_reward_ratio / 3.0) * 0.4)
            
            # Determine confidence level
            if confidence_score >= 0.85:
                confidence_level = 'VERY_HIGH'
            elif confidence_score >= 0.7:
                confidence_level = 'HIGH'
            elif confidence_score >= 0.5:
                confidence_level = 'MEDIUM'
            else:
                confidence_level = 'LOW'
            
            # Create signal
            signal = TradingSignal.objects.create(
                symbol=symbol,
                signal_type=signal_type,
                strength=strength,
                confidence_score=confidence_score,
                confidence_level=confidence_level,
                entry_price=Decimal(str(entry_price)),
                target_price=Decimal(str(target_price)),
                stop_loss=Decimal(str(stop_loss)),
                risk_reward_ratio=risk_reward_ratio,
                quality_score=quality_score,
                is_valid=True,
                expires_at=timezone.now() + timezone.timedelta(hours=24),
                technical_score=confidence_score,  # RSI is purely technical
                sentiment_score=0.0,
                news_score=0.0,
                volume_score=0.0,
                pattern_score=0.0,
                # New timeframe and entry point fields
                timeframe='1H',  # Default timeframe for strategies
                entry_point_type='TREND_FOLLOWING',  # Default entry point type
                entry_point_details={},
                entry_zone_low=Decimal(str(entry_price * 0.99)),  # 1% below entry
                entry_zone_high=Decimal(str(entry_price * 1.01)),  # 1% above entry
                entry_confidence=confidence_score,  # Use confidence score as entry confidence
                notes=notes
            )
            
            logger.info(f"Created {signal_type.name} signal for {symbol.symbol} with confidence {confidence_score:.2f}")
            return signal
            
        except Exception as e:
            logger.error(f"Error creating RSI signal: {e}")
            return None


class MACDStrategy(BaseStrategy):
    """MACD Strategy
    
    Generates signals based on:
    1. MACD line vs Signal line crossover
    2. MACD histogram analysis
    3. Bullish/bearish divergence detection
    4. MACD momentum analysis
    """
    
    def __init__(self):
        super().__init__()
        self.name = "MACD Strategy"
        self.description = "Generates signals based on MACD crossovers, histogram, and divergence"
        
        # Strategy parameters
        self.fast_period = 12
        self.slow_period = 26
        self.signal_period = 9
        
        # Signal thresholds
        self.min_crossover_strength = 0.0001  # Minimum crossover strength
        self.histogram_threshold = 0.0001     # Minimum histogram change for signals
        self.momentum_threshold = 0.001       # Minimum momentum change
        
        # Divergence parameters
        self.divergence_lookback = 5  # Look back 5 periods for divergence
        
    def generate_signals(self, symbol: Symbol) -> List[TradingSignal]:
        """Generate trading signals based on MACD analysis"""
        try:
            signals = []
            
            # Get MACD indicators
            macd_line = self._get_latest_indicators(symbol, 'MACD_LINE', 0, 5)
            signal_line = self._get_latest_indicators(symbol, 'MACD_SIGNAL', 0, 5)
            histogram = self._get_latest_indicators(symbol, 'MACD_HISTOGRAM', 0, 5)
            
            if len(macd_line) < 2 or len(signal_line) < 2 or len(histogram) < 2:
                logger.warning(f"Insufficient MACD data for {symbol.symbol}")
                return signals
            
            # Get current price
            current_price = self._get_latest_price(symbol)
            if not current_price:
                return signals
            
            # Get market data for divergence analysis
            market_data = self._get_market_data_for_divergence(symbol, 10)
            
            # Check MACD crossover signals
            crossover_signals = self._check_macd_crossover(symbol, macd_line, signal_line, current_price)
            signals.extend(crossover_signals)
            
            # Check histogram signals
            histogram_signals = self._check_histogram_signals(symbol, histogram, current_price)
            signals.extend(histogram_signals)
            
            # Check momentum signals
            momentum_signals = self._check_momentum_signals(symbol, macd_line, histogram, current_price)
            signals.extend(momentum_signals)
            
            # Check divergence signals
            if market_data:
                divergence_signals = self._check_divergence_signals(symbol, macd_line, market_data, current_price)
                signals.extend(divergence_signals)
            
            logger.info(f"Generated {len(signals)} MACD signals for {symbol.symbol}")
            return signals
            
        except Exception as e:
            logger.error(f"Error generating MACD signals for {symbol.symbol}: {e}")
            return []
    
    def _get_market_data_for_divergence(self, symbol: Symbol, limit: int = 10) -> List[Dict]:
        """Get market data for divergence analysis"""
        try:
            market_data = MarketData.objects.filter(
                symbol=symbol
            ).order_by('-timestamp')[:limit]
            
            return [
                {
                    'timestamp': data.timestamp,
                    'close_price': float(data.close_price),
                    'high_price': float(data.high_price),
                    'low_price': float(data.low_price)
                }
                for data in market_data
            ]
        except Exception as e:
            logger.error(f"Error getting market data for divergence: {e}")
            return []
    
    def _check_macd_crossover(self, symbol: Symbol, macd_line: List[TechnicalIndicator], 
                              signal_line: List[TechnicalIndicator], current_price: float) -> List[TradingSignal]:
        """Check for MACD crossover signals"""
        signals = []
        
        try:
            if len(macd_line) < 2 or len(signal_line) < 2:
                return signals
            
            # Current and previous values
            current_macd = float(macd_line[0].value)
            previous_macd = float(macd_line[1].value)
            current_signal = float(signal_line[0].value)
            previous_signal = float(signal_line[1].value)
            
            # Calculate current and previous differences
            current_diff = current_macd - current_signal
            previous_diff = previous_macd - previous_signal
            
            # Check for bullish crossover (MACD crosses above signal line)
            if (previous_diff <= 0 and current_diff > 0 and 
                abs(current_diff) > self.min_crossover_strength * current_price):
                
                signal_type = self._get_or_create_signal_type('BUY')
                confidence_score = self._calculate_crossover_confidence(current_diff, current_price)
                
                if confidence_score >= self.min_confidence_threshold:
                    signal = self._create_signal(
                        symbol=symbol,
                        signal_type=signal_type,
                        confidence_score=confidence_score,
                        entry_price=current_price,
                        target_price=current_price * 1.05,  # 5% target
                        stop_loss=current_price * 0.98,    # 2% stop loss
                        strength='STRONG' if confidence_score > 0.8 else 'MODERATE',
                        notes=f"MACD Bullish Crossover: MACD({current_macd:.6f}) crossed above Signal({current_signal:.6f})"
                    )
                    if signal:
                        signals.append(signal)
            
            # Check for bearish crossover (MACD crosses below signal line)
            elif (previous_diff >= 0 and current_diff < 0 and 
                  abs(current_diff) > self.min_crossover_strength * current_price):
                
                signal_type = self._get_or_create_signal_type('SELL')
                confidence_score = self._calculate_crossover_confidence(abs(current_diff), current_price)
                
                if confidence_score >= self.min_confidence_threshold:
                    signal = self._create_signal(
                        symbol=symbol,
                        signal_type=signal_type,
                        confidence_score=confidence_score,
                        entry_price=current_price,
                        target_price=current_price * 0.95,  # 5% target
                        stop_loss=current_price * 1.02,    # 2% stop loss
                        strength='STRONG' if confidence_score > 0.8 else 'MODERATE',
                        notes=f"MACD Bearish Crossover: MACD({current_macd:.6f}) crossed below Signal({current_signal:.6f})"
                    )
                    if signal:
                        signals.append(signal)
            
            return signals
            
        except Exception as e:
            logger.error(f"Error checking MACD crossover: {e}")
            return signals
    
    def _check_histogram_signals(self, symbol: Symbol, histogram: List[TechnicalIndicator], 
                                 current_price: float) -> List[TradingSignal]:
        """Check for histogram-based signals"""
        signals = []
        
        try:
            if len(histogram) < 3:
                return signals
            
            # Get histogram values
            current_hist = float(histogram[0].value)
            previous_hist = float(histogram[1].value)
            earlier_hist = float(histogram[2].value)
            
            # Check for histogram reversal (increasing after decreasing)
            if (earlier_hist > previous_hist and previous_hist < current_hist and 
                abs(current_hist - previous_hist) > self.histogram_threshold * current_price):
                
                # Bullish histogram reversal
                signal_type = self._get_or_create_signal_type('BUY')
                confidence_score = 0.75  # Moderate confidence for histogram signals
                
                signal = self._create_signal(
                    symbol=symbol,
                    signal_type=signal_type,
                    confidence_score=confidence_score,
                    entry_price=current_price,
                    target_price=current_price * 1.04,  # 4% target
                    stop_loss=current_price * 0.99,    # 1% stop loss
                    strength='MODERATE',
                    notes=f"MACD Histogram Bullish Reversal: Histogram turned positive from negative"
                )
                if signal:
                    signals.append(signal)
            
            # Check for histogram reversal (decreasing after increasing)
            elif (earlier_hist < previous_hist and previous_hist > current_hist and 
                  abs(current_hist - previous_hist) > self.histogram_threshold * current_price):
                
                # Bearish histogram reversal
                signal_type = self._get_or_create_signal_type('SELL')
                confidence_score = 0.75  # Moderate confidence for histogram signals
                
                signal = self._create_signal(
                    symbol=symbol,
                    signal_type=signal_type,
                    confidence_score=confidence_score,
                    entry_price=current_price,
                    target_price=current_price * 0.96,  # 4% target
                    stop_loss=current_price * 1.01,    # 1% stop loss
                    strength='MODERATE',
                    notes=f"MACD Histogram Bearish Reversal: Histogram turned negative from positive"
                )
                if signal:
                    signals.append(signal)
            
            return signals
            
        except Exception as e:
            logger.error(f"Error checking histogram signals: {e}")
            return signals
    
    def _check_momentum_signals(self, symbol: Symbol, macd_line: List[TechnicalIndicator], 
                                histogram: List[TechnicalIndicator], current_price: float) -> List[TradingSignal]:
        """Check for momentum-based signals"""
        signals = []
        
        try:
            if len(macd_line) < 3 or len(histogram) < 3:
                return signals
            
            # Get MACD and histogram values
            current_macd = float(macd_line[0].value)
            previous_macd = float(macd_line[1].value)
            earlier_macd = float(macd_line[2].value)
            
            current_hist = float(histogram[0].value)
            previous_hist = float(histogram[1].value)
            
            # Calculate momentum
            macd_momentum = current_macd - earlier_macd
            hist_momentum = current_hist - previous_hist
            
            # Check for strong bullish momentum
            if (macd_momentum > 0 and hist_momentum > 0 and 
                abs(macd_momentum) > self.momentum_threshold * current_price):
                
                signal_type = self._get_or_create_signal_type('BUY')
                confidence_score = 0.8  # High confidence for momentum signals
                
                signal = self._create_signal(
                    symbol=symbol,
                    signal_type=signal_type,
                    confidence_score=confidence_score,
                    entry_price=current_price,
                    target_price=current_price * 1.06,  # 6% target
                    stop_loss=current_price * 0.98,    # 2% stop loss
                    strength='STRONG',
                    notes=f"MACD Strong Bullish Momentum: MACD and histogram both increasing"
                )
                if signal:
                    signals.append(signal)
            
            # Check for strong bearish momentum
            elif (macd_momentum < 0 and hist_momentum < 0 and 
                  abs(macd_momentum) > self.momentum_threshold * current_price):
                
                signal_type = self._get_or_create_signal_type('SELL')
                confidence_score = 0.8  # High confidence for momentum signals
                
                signal = self._create_signal(
                    symbol=symbol,
                    signal_type=signal_type,
                    confidence_score=confidence_score,
                    entry_price=current_price,
                    target_price=current_price * 0.94,  # 6% target
                    stop_loss=current_price * 1.02,    # 2% stop loss
                    strength='STRONG',
                    notes=f"MACD Strong Bearish Momentum: MACD and histogram both decreasing"
                )
                if signal:
                    signals.append(signal)
            
            return signals
            
        except Exception as e:
            logger.error(f"Error checking momentum signals: {e}")
            return signals
    
    def _check_divergence_signals(self, symbol: Symbol, macd_line: List[TechnicalIndicator], 
                                  market_data: List[Dict], current_price: float) -> List[TradingSignal]:
        """Check for MACD divergence signals"""
        signals = []
        
        try:
            if len(macd_line) < self.divergence_lookback or len(market_data) < self.divergence_lookback:
                return signals
            
            # Check for bullish divergence (price makes lower lows, MACD makes higher lows)
            bullish_divergence = self._detect_bullish_divergence(macd_line, market_data)
            if bullish_divergence:
                signal_type = self._get_or_create_signal_type('BUY')
                confidence_score = 0.85  # High confidence for divergence signals
                
                signal = self._create_signal(
                    symbol=symbol,
                    signal_type=signal_type,
                    confidence_score=confidence_score,
                    entry_price=current_price,
                    target_price=current_price * 1.07,  # 7% target
                    stop_loss=current_price * 0.97,    # 3% stop loss
                    strength='STRONG',
                    notes=f"MACD Bullish Divergence: Price made lower low but MACD made higher low. Strong reversal signal."
                )
                if signal:
                    signals.append(signal)
            
            # Check for bearish divergence (price makes higher highs, MACD makes lower highs)
            bearish_divergence = self._detect_bearish_divergence(macd_line, market_data)
            if bearish_divergence:
                signal_type = self._get_or_create_signal_type('SELL')
                confidence_score = 0.85  # High confidence for divergence signals
                
                signal = self._create_signal(
                    symbol=symbol,
                    signal_type=signal_type,
                    confidence_score=confidence_score,
                    entry_price=current_price,
                    target_price=current_price * 0.93,  # 7% target
                    stop_loss=current_price * 1.03,    # 3% stop loss
                    strength='STRONG',
                    notes=f"MACD Bearish Divergence: Price made higher high but MACD made lower high. Strong reversal signal."
                )
                if signal:
                    signals.append(signal)
            
            return signals
            
        except Exception as e:
            logger.error(f"Error checking divergence signals: {e}")
            return signals
    
    def _detect_bullish_divergence(self, macd_line: List[TechnicalIndicator], 
                                   market_data: List[Dict]) -> bool:
        """Detect bullish divergence pattern"""
        try:
            # Get recent MACD and price data
            recent_macd = [float(ind.value) for ind in macd_line[:self.divergence_lookback]]
            recent_lows = [data['low_price'] for data in market_data[:self.divergence_lookback]]
            
            if len(recent_macd) >= 3 and len(recent_lows) >= 3:
                current_macd_low = min(recent_macd[:2])  # Recent MACD low
                previous_macd_low = min(recent_macd[2:])  # Previous MACD low
                
                current_price_low = recent_lows[0]
                previous_price_low = min(recent_lows[1:])
                
                # Check if we have lower low in price but higher low in MACD
                price_lower_low = current_price_low < previous_price_low
                macd_higher_low = current_macd_low > previous_macd_low
                
                # Check if the divergence is significant enough
                price_change = abs(current_price_low - previous_price_low) / previous_price_low
                significant_change = price_change >= 0.01  # 1% minimum change
                
                return price_lower_low and macd_higher_low and significant_change
            
            return False
            
        except Exception as e:
            logger.error(f"Error detecting bullish divergence: {e}")
            return False
    
    def _detect_bearish_divergence(self, macd_line: List[TechnicalIndicator], 
                                   market_data: List[Dict]) -> bool:
        """Detect bearish divergence pattern"""
        try:
            # Get recent MACD and price data
            recent_macd = [float(ind.value) for ind in macd_line[:self.divergence_lookback]]
            recent_highs = [data['high_price'] for data in market_data[:self.divergence_lookback]]
            
            if len(recent_macd) >= 3 and len(recent_highs) >= 3:
                current_macd_high = max(recent_macd[:2])  # Recent MACD high
                previous_macd_high = max(recent_macd[2:])  # Previous MACD high
                
                current_price_high = recent_highs[0]
                previous_price_high = max(recent_highs[1:])
                
                # Check if we have higher high in price but lower high in MACD
                price_higher_high = current_price_high > previous_price_high
                macd_lower_high = current_macd_high < previous_macd_high
                
                # Check if the divergence is significant enough
                price_change = abs(current_price_high - previous_price_high) / previous_price_high
                significant_change = price_change >= 0.01  # 1% minimum change
                
                return price_higher_high and macd_lower_high and significant_change
            
            return False
            
        except Exception as e:
            logger.error(f"Error detecting bearish divergence: {e}")
            return False
    
    def _calculate_crossover_confidence(self, crossover_diff: float, current_price: float) -> float:
        """Calculate confidence score for MACD crossover"""
        try:
            # Normalize crossover difference
            normalized_diff = abs(crossover_diff) / current_price
            
            # Base confidence on crossover strength
            if normalized_diff > 0.001:  # >0.1% crossover
                base_confidence = 0.9
            elif normalized_diff > 0.0005:  # >0.05% crossover
                base_confidence = 0.8
            elif normalized_diff > 0.0002:  # >0.02% crossover
                base_confidence = 0.7
            else:
                base_confidence = 0.6
            
            return base_confidence
            
        except Exception as e:
            logger.error(f"Error calculating crossover confidence: {e}")
            return 0.7
    
    def _get_or_create_signal_type(self, signal_name: str) -> SignalType:
        """Get or create a signal type"""
        try:
            signal_type, created = SignalType.objects.get_or_create(
                name=signal_name,
                defaults={
                    'description': f'{signal_name} signal from MACD Strategy',
                    'color': '#28a745' if 'BUY' in signal_name else '#dc3545',
                    'is_active': True
                }
            )
            return signal_type
        except Exception as e:
            logger.error(f"Error getting/creating signal type {signal_name}: {e}")
            # Return a default signal type
            return SignalType.objects.filter(name='BUY').first() or SignalType.objects.first()
    
    def _create_signal(self, symbol: Symbol, signal_type: SignalType, 
                       confidence_score: float, entry_price: float,
                       target_price: float, stop_loss: float,
                       strength: str, notes: str) -> TradingSignal:
        """Create a trading signal"""
        try:
            # Calculate risk-reward ratio
            risk = abs(entry_price - stop_loss)
            reward = abs(target_price - entry_price)
            risk_reward_ratio = reward / risk if risk > 0 else 0
            
            # Calculate quality score
            quality_score = (confidence_score * 0.6 + 
                           min(1.0, risk_reward_ratio / 3.0) * 0.4)
            
            # Determine confidence level
            if confidence_score >= 0.85:
                confidence_level = 'VERY_HIGH'
            elif confidence_score >= 0.7:
                confidence_level = 'HIGH'
            elif confidence_score >= 0.5:
                confidence_level = 'MEDIUM'
            else:
                confidence_level = 'LOW'
            
            # Create signal
            signal = TradingSignal.objects.create(
                symbol=symbol,
                signal_type=signal_type,
                strength=strength,
                confidence_score=confidence_score,
                confidence_level=confidence_level,
                entry_price=Decimal(str(entry_price)),
                target_price=Decimal(str(target_price)),
                stop_loss=Decimal(str(stop_loss)),
                risk_reward_ratio=risk_reward_ratio,
                quality_score=quality_score,
                is_valid=True,
                expires_at=timezone.now() + timezone.timedelta(hours=24),
                technical_score=confidence_score,  # MACD is purely technical
                sentiment_score=0.0,
                news_score=0.0,
                volume_score=0.0,
                pattern_score=0.0,
                notes=notes
            )
            
            logger.info(f"Created {signal_type.name} signal for {symbol.symbol} with confidence {confidence_score:.2f}")
            return signal
            
        except Exception as e:
            logger.error(f"Error creating MACD signal: {e}")
            return None


class BollingerBandsStrategy(BaseStrategy):
    """Bollinger Bands Strategy
    
    Generates signals based on:
    1. Price position relative to Bollinger Bands (upper, middle, lower)
    2. Band width analysis (volatility expansion/contraction)
    3. Bollinger Band squeeze detection
    4. Mean reversion signals from band touches
    """
    
    def __init__(self):
        super().__init__()
        self.name = "Bollinger Bands Strategy"
        self.description = "Generates signals based on Bollinger Bands analysis and volatility patterns"
        
        # Strategy parameters
        self.bb_period = 20
        self.bb_std_dev = 2.0
        
        # Signal thresholds
        self.squeeze_threshold = 0.1  # 10% of average band width for squeeze detection
        self.expansion_threshold = 0.3  # 30% increase in band width for expansion signals
        self.touch_threshold = 0.02  # 2% from band for touch signals
        
        # Mean reversion parameters
        self.mean_reversion_lookback = 5  # Look back 5 periods for mean reversion
        self.min_reversion_strength = 0.03  # 3% minimum move for reversion signals
        
    def generate_signals(self, symbol: Symbol) -> List[TradingSignal]:
        """Generate trading signals based on Bollinger Bands analysis"""
        try:
            signals = []
            
            # Get Bollinger Bands indicators
            upper_band = self._get_latest_indicators(symbol, 'BB_UPPER', self.bb_period, 10)
            middle_band = self._get_latest_indicators(symbol, 'BB_MIDDLE', self.bb_period, 10)
            lower_band = self._get_latest_indicators(symbol, 'BB_LOWER', self.bb_period, 10)
            
            if len(upper_band) < 3 or len(middle_band) < 3 or len(lower_band) < 3:
                logger.warning(f"Insufficient Bollinger Bands data for {symbol.symbol}")
                return signals
            
            # Get current price
            current_price = self._get_latest_price(symbol)
            if not current_price:
                return signals
            
            # Check price position signals
            position_signals = self._check_price_position(symbol, upper_band, middle_band, lower_band, current_price)
            signals.extend(position_signals)
            
            # Check band width signals
            width_signals = self._check_band_width(symbol, upper_band, lower_band, current_price)
            signals.extend(width_signals)
            
            # Check squeeze signals
            squeeze_signals = self._check_squeeze(symbol, upper_band, lower_band, current_price)
            signals.extend(squeeze_signals)
            
            # Check mean reversion signals
            reversion_signals = self._check_mean_reversion(symbol, upper_band, middle_band, lower_band, current_price)
            signals.extend(reversion_signals)
            
            logger.info(f"Generated {len(signals)} Bollinger Bands signals for {symbol.symbol}")
            return signals
            
        except Exception as e:
            logger.error(f"Error generating Bollinger Bands signals for {symbol.symbol}: {e}")
            return []
    
    def _check_price_position(self, symbol: Symbol, upper_band: List[TechnicalIndicator], 
                               middle_band: List[TechnicalIndicator], lower_band: List[TechnicalIndicator], 
                               current_price: float) -> List[TradingSignal]:
        """Check for signals based on price position relative to bands"""
        signals = []
        
        try:
            if len(upper_band) < 1 or len(middle_band) < 1 or len(lower_band) < 1:
                return signals
            
            current_upper = float(upper_band[0].value)
            current_middle = float(middle_band[0].value)
            current_lower = float(lower_band[0].value)
            
            # Calculate price position relative to bands
            upper_distance = (current_upper - current_price) / current_price
            lower_distance = (current_price - current_lower) / current_price
            middle_distance = abs(current_price - current_middle) / current_price
            
            # Check for oversold signal (price near lower band)
            if lower_distance <= self.touch_threshold:
                signal_type = self._get_or_create_signal_type('BUY')
                confidence_score = self._calculate_position_confidence(lower_distance, 'oversold')
                
                if confidence_score >= self.min_confidence_threshold:
                    signal = self._create_signal(
                        symbol=symbol,
                        signal_type=signal_type,
                        confidence_score=confidence_score,
                        entry_price=current_price,
                        target_price=current_middle,  # Target middle band
                        stop_loss=current_lower * 0.98,  # Stop below lower band
                        strength='STRONG' if confidence_score > 0.8 else 'MODERATE',
                        notes=f"BB Oversold: Price({current_price:.4f}) near lower band({current_lower:.4f}). Mean reversion expected."
                    )
                    if signal:
                        signals.append(signal)
            
            # Check for overbought signal (price near upper band)
            elif upper_distance <= self.touch_threshold:
                signal_type = self._get_or_create_signal_type('SELL')
                confidence_score = self._calculate_position_confidence(upper_distance, 'overbought')
                
                if confidence_score >= self.min_confidence_threshold:
                    signal = self._create_signal(
                        symbol=symbol,
                        signal_type=signal_type,
                        confidence_score=confidence_score,
                        entry_price=current_price,
                        target_price=current_middle,  # Target middle band
                        stop_loss=current_upper * 1.02,  # Stop above upper band
                        strength='STRONG' if confidence_score > 0.8 else 'MODERATE',
                        notes=f"BB Overbought: Price({current_price:.4f}) near upper band({current_upper:.4f}). Mean reversion expected."
                    )
                    if signal:
                        signals.append(signal)
            
            # Check for strong trend signal (price between middle and upper/lower bands)
            elif current_price > current_middle and middle_distance > 0.01:  # Above middle, significant distance
                signal_type = self._get_or_create_signal_type('BUY')
                confidence_score = 0.75  # Moderate confidence for trend continuation
                
                signal = self._create_signal(
                    symbol=symbol,
                    signal_type=signal_type,
                    confidence_score=confidence_score,
                    entry_price=current_price,
                    target_price=current_price * 1.04,  # 4% target
                    stop_loss=current_middle,  # Stop at middle band
                    strength='MODERATE',
                    notes=f"BB Bullish Trend: Price({current_price:.4f}) above middle band({current_middle:.4f}). Trend continuation expected."
                )
                if signal:
                    signals.append(signal)
            
            elif current_price < current_middle and middle_distance > 0.01:  # Below middle, significant distance
                signal_type = self._get_or_create_signal_type('SELL')
                confidence_score = 0.75  # Moderate confidence for trend continuation
                
                signal = self._create_signal(
                    symbol=symbol,
                    signal_type=signal_type,
                    confidence_score=confidence_score,
                    entry_price=current_price,
                    target_price=current_price * 0.96,  # 4% target
                    stop_loss=current_middle,  # Stop at middle band
                    strength='MODERATE',
                    notes=f"BB Bearish Trend: Price({current_price:.4f}) below middle band({current_middle:.4f}). Trend continuation expected."
                )
                if signal:
                    signals.append(signal)
            
            return signals
            
        except Exception as e:
            logger.error(f"Error checking price position: {e}")
            return signals
    
    def _check_band_width(self, symbol: Symbol, upper_band: List[TechnicalIndicator], 
                            lower_band: List[TechnicalIndicator], current_price: float) -> List[TradingSignal]:
        """Check for signals based on band width changes"""
        signals = []
        
        try:
            if len(upper_band) < 3 or len(lower_band) < 3:
                return signals
            
            # Calculate current and previous band widths
            current_width = float(upper_band[0].value) - float(lower_band[0].value)
            previous_width = float(upper_band[1].value) - float(lower_band[1].value)
            earlier_width = float(upper_band[2].value) - float(lower_band[2].value)
            
            # Calculate width changes
            width_change = (current_width - previous_width) / previous_width if previous_width > 0 else 0
            previous_change = (previous_width - earlier_width) / earlier_width if earlier_width > 0 else 0
            
            # Check for volatility expansion (bands widening)
            if width_change > self.expansion_threshold and previous_change <= 0:
                # Bands are expanding after contraction - potential breakout
                signal_type = self._get_or_create_signal_type('BUY')
                confidence_score = 0.8  # High confidence for volatility expansion
                
                signal = self._create_signal(
                    symbol=symbol,
                    signal_type=signal_type,
                    confidence_score=confidence_score,
                    entry_price=current_price,
                    target_price=current_price * 1.06,  # 6% target
                    stop_loss=current_price * 0.97,    # 3% stop loss
                    strength='STRONG',
                    notes=f"BB Volatility Expansion: Bands widening by {width_change:.1%}. Potential breakout signal."
                )
                if signal:
                    signals.append(signal)
            
            # Check for volatility contraction (bands narrowing)
            elif width_change < -self.expansion_threshold and previous_change >= 0:
                # Bands are contracting after expansion - potential consolidation
                signal_type = self._get_or_create_signal_type('SELL')
                confidence_score = 0.7  # Moderate confidence for consolidation
                
                signal = self._create_signal(
                    symbol=symbol,
                    signal_type=signal_type,
                    confidence_score=confidence_score,
                    entry_price=current_price,
                    target_price=current_price * 0.95,  # 5% target
                    stop_loss=current_price * 1.03,    # 3% stop loss
                    strength='MODERATE',
                    notes=f"BB Volatility Contraction: Bands narrowing by {abs(width_change):.1%}. Consolidation expected."
                )
                if signal:
                    signals.append(signal)
            
            return signals
            
        except Exception as e:
            logger.error(f"Error checking band width: {e}")
            return signals
    
    def _check_squeeze(self, symbol: Symbol, upper_band: List[TechnicalIndicator], 
                         lower_band: List[TechnicalIndicator], current_price: float) -> List[TradingSignal]:
        """Check for Bollinger Band squeeze signals"""
        signals = []
        
        try:
            if len(upper_band) < 5 or len(lower_band) < 5:
                return signals
            
            # Calculate average band width over the last 5 periods
            recent_widths = []
            for i in range(5):
                width = float(upper_band[i].value) - float(lower_band[i].value)
                recent_widths.append(width)
            
            avg_width = sum(recent_widths) / len(recent_widths)
            current_width = recent_widths[0]
            
            # Check if current width is significantly smaller than average (squeeze)
            if current_width < avg_width * (1 - self.squeeze_threshold):
                # Potential squeeze - look for breakout direction
                signal_type = self._get_or_create_signal_type('BUY')
                confidence_score = 0.85  # High confidence for squeeze breakout
                
                signal = self._create_signal(
                    symbol=symbol,
                    signal_type=signal_type,
                    confidence_score=confidence_score,
                    entry_price=current_price,
                    target_price=current_price * 1.08,  # 8% target for squeeze breakout
                    stop_loss=current_price * 0.95,    # 5% stop loss
                    strength='VERY_STRONG',
                    notes=f"BB Squeeze: Bands compressed to {current_width/avg_width:.1%} of average width. Major breakout expected."
                )
                if signal:
                    signals.append(signal)
            
            return signals
            
        except Exception as e:
            logger.error(f"Error checking squeeze: {e}")
            return signals
    
    def _check_mean_reversion(self, symbol: Symbol, upper_band: List[TechnicalIndicator], 
                                middle_band: List[TechnicalIndicator], lower_band: List[TechnicalIndicator], 
                                current_price: float) -> List[TradingSignal]:
        """Check for mean reversion signals"""
        signals = []
        
        try:
            if len(upper_band) < self.mean_reversion_lookback or len(middle_band) < self.mean_reversion_lookback:
                return signals
            
            current_middle = float(middle_band[0].value)
            middle_distance = abs(current_price - current_middle) / current_price
            
            # Check if price has moved significantly from middle band
            if middle_distance > self.min_reversion_strength:
                # Determine reversion direction
                if current_price > current_middle:  # Price above middle - expect reversion down
                    signal_type = self._get_or_create_signal_type('SELL')
                    target_price = current_middle  # Target middle band
                    stop_loss = current_price * 1.02  # 2% stop loss
                    notes = f"BB Mean Reversion: Price({current_price:.4f}) {middle_distance:.1%} above middle band. Reversion expected."
                else:  # Price below middle - expect reversion up
                    signal_type = self._get_or_create_signal_type('BUY')
                    target_price = current_middle  # Target middle band
                    stop_loss = current_price * 0.98  # 2% stop loss
                    notes = f"BB Mean Reversion: Price({current_price:.4f}) {middle_distance:.1%} below middle band. Reversion expected."
                
                confidence_score = 0.8  # High confidence for mean reversion
                
                signal = self._create_signal(
                    symbol=symbol,
                    signal_type=signal_type,
                    confidence_score=confidence_score,
                    entry_price=current_price,
                    target_price=target_price,
                    stop_loss=stop_loss,
                    strength='STRONG',
                    notes=notes
                )
                if signal:
                    signals.append(signal)
            
            return signals
            
        except Exception as e:
            logger.error(f"Error checking mean reversion: {e}")
            return signals
    
    def _calculate_position_confidence(self, distance: float, position_type: str) -> float:
        """Calculate confidence score based on price position"""
        try:
            # Closer to band = higher confidence
            if distance <= 0.01:  # Very close to band
                base_confidence = 0.9
            elif distance <= 0.02:  # Close to band
                base_confidence = 0.8
            elif distance <= 0.03:  # Near band
                base_confidence = 0.7
            else:
                base_confidence = 0.6
            
            # Additional confidence for extreme positions
            if position_type == 'oversold' and distance <= 0.005:
                base_confidence += 0.05
            elif position_type == 'overbought' and distance <= 0.005:
                base_confidence += 0.05
            
            return min(1.0, base_confidence)
            
        except Exception as e:
            logger.error(f"Error calculating position confidence: {e}")
            return 0.7
    
    def _get_or_create_signal_type(self, signal_name: str) -> SignalType:
        """Get or create a signal type"""
        try:
            signal_type, created = SignalType.objects.get_or_create(
                name=signal_name,
                defaults={
                    'description': f'{signal_name} signal from Bollinger Bands Strategy',
                    'color': '#28a745' if 'BUY' in signal_name else '#dc3545',
                    'is_active': True
                }
            )
            return signal_type
        except Exception as e:
            logger.error(f"Error getting/creating signal type {signal_name}: {e}")
            # Return a default signal type
            return SignalType.objects.filter(name='BUY').first() or SignalType.objects.first()
    
    def _create_signal(self, symbol: Symbol, signal_type: SignalType, 
                         confidence_score: float, entry_price: float,
                         target_price: float, stop_loss: float,
                         strength: str, notes: str) -> TradingSignal:
        """Create a trading signal"""
        try:
            # Calculate risk-reward ratio
            risk = abs(entry_price - stop_loss)
            reward = abs(target_price - entry_price)
            risk_reward_ratio = reward / risk if risk > 0 else 0
            
            # Calculate quality score
            quality_score = (confidence_score * 0.6 + 
                           min(1.0, risk_reward_ratio / 3.0) * 0.4)
            
            # Determine confidence level
            if confidence_score >= 0.85:
                confidence_level = 'VERY_HIGH'
            elif confidence_score >= 0.7:
                confidence_level = 'HIGH'
            elif confidence_score >= 0.5:
                confidence_level = 'MEDIUM'
            else:
                confidence_level = 'LOW'
            
            # Create signal
            signal = TradingSignal.objects.create(
                symbol=symbol,
                signal_type=signal_type,
                strength=strength,
                confidence_score=confidence_score,
                confidence_level=confidence_level,
                entry_price=Decimal(str(entry_price)),
                target_price=Decimal(str(target_price)),
                stop_loss=Decimal(str(stop_loss)),
                risk_reward_ratio=risk_reward_ratio,
                quality_score=quality_score,
                is_valid=True,
                expires_at=timezone.now() + timezone.timedelta(hours=24),
                technical_score=confidence_score,  # Bollinger Bands is purely technical
                sentiment_score=0.0,
                news_score=0.0,
                volume_score=0.0,
                pattern_score=0.0,
                notes=notes
            )
            
            logger.info(f"Created {signal_type.name} signal for {symbol.symbol} with confidence {confidence_score:.2f}")
            return signal
            
        except Exception as e:
            logger.error(f"Error creating Bollinger Bands signal: {e}")
            return None


class BreakoutStrategy(BaseStrategy):
    """Breakout Strategy
    
    Generates signals based on:
    1. Support/Resistance level breakouts
    2. Volume confirmation of breakouts
    3. Price pattern breakouts (triangles, rectangles, channels)
    4. Breakout momentum and follow-through
    """
    
    def __init__(self):
        super().__init__()
        self.name = "Breakout Strategy"
        self.description = "Generates signals based on support/resistance breakouts and pattern breakouts"
        
        # Strategy parameters
        self.support_resistance_lookback = 20  # Look back 20 periods for S/R levels
        self.breakout_threshold = 0.02  # 2% breakout above/below level
        self.volume_multiplier = 1.5  # Volume should be 1.5x average for confirmation
        self.follow_through_threshold = 0.01  # 1% follow-through after breakout
        
        # Pattern detection parameters
        self.triangle_lookback = 15  # Look back 15 periods for triangle patterns
        self.rectangle_lookback = 12  # Look back 12 periods for rectangle patterns
        self.channel_lookback = 18  # Look back 18 periods for channel patterns
        
        # Signal thresholds
        self.min_breakout_strength = 0.03  # 3% minimum move for strong breakout
        self.max_false_breakout_threshold = 0.005  # 0.5% maximum pullback for valid breakout
        
    def generate_signals(self, symbol: Symbol) -> List[TradingSignal]:
        """Generate trading signals based on breakout analysis"""
        try:
            signals = []
            
            # Get current price and market data
            current_price = self._get_latest_price(symbol)
            if not current_price:
                return signals
            
            # Check support/resistance breakouts
            sr_signals = self._check_support_resistance_breakouts(symbol, current_price)
            signals.extend(sr_signals)
            
            # Check pattern breakouts
            pattern_signals = self._check_pattern_breakouts(symbol, current_price)
            signals.extend(pattern_signals)
            
            # Check momentum breakouts
            momentum_signals = self._check_momentum_breakouts(symbol, current_price)
            signals.extend(momentum_signals)
            
            logger.info(f"Generated {len(signals)} breakout signals for {symbol.symbol}")
            return signals
            
        except Exception as e:
            logger.error(f"Error generating breakout signals for {symbol.symbol}: {e}")
            return []
    
    def _check_support_resistance_breakouts(self, symbol: Symbol, current_price: float) -> List[TradingSignal]:
        """Check for support/resistance level breakouts"""
        signals = []
        
        try:
            # Get recent market data for support/resistance analysis
            recent_data = MarketData.objects.filter(
                symbol=symbol
            ).order_by('-timestamp')[:self.support_resistance_lookback]
            
            if len(recent_data) < 10:
                return signals
            
            # Find support and resistance levels
            highs = [float(data.high_price) for data in recent_data]
            lows = [float(data.low_price) for data in recent_data]
            
            # Calculate dynamic support/resistance levels
            resistance_level = max(highs[-10:])  # Recent high as resistance
            support_level = min(lows[-10:])      # Recent low as support
            
            # Check for resistance breakout (bullish)
            if current_price > resistance_level * (1 + self.breakout_threshold):
                # Verify volume confirmation
                if self._check_volume_confirmation(symbol, 1.5):
                    signal_type = self._get_or_create_signal_type('BUY')
                    confidence_score = self._calculate_breakout_confidence(current_price, resistance_level, 'resistance')
                    
                    if confidence_score >= self.min_confidence_threshold:
                        signal = self._create_signal(
                            symbol=symbol,
                            signal_type=signal_type,
                            confidence_score=confidence_score,
                            entry_price=current_price,
                            target_price=current_price * 1.06,  # 6% target
                            stop_loss=resistance_level,  # Stop at resistance level
                            strength='STRONG' if confidence_score > 0.8 else 'MODERATE',
                            notes=f"Resistance Breakout: Price({current_price:.4f}) broke above resistance({resistance_level:.4f}). Bullish continuation expected."
                        )
                        if signal:
                            signals.append(signal)
            
            # Check for support breakdown (bearish)
            elif current_price < support_level * (1 - self.breakout_threshold):
                # Verify volume confirmation
                if self._check_volume_confirmation(symbol, 1.5):
                    signal_type = self._get_or_create_signal_type('SELL')
                    confidence_score = self._calculate_breakout_confidence(current_price, support_level, 'support')
                    
                    if confidence_score >= self.min_confidence_threshold:
                        signal = self._create_signal(
                            symbol=symbol,
                            signal_type=signal_type,
                            confidence_score=confidence_score,
                            entry_price=current_price,
                            target_price=current_price * 0.94,  # 6% target
                            stop_loss=support_level,  # Stop at support level
                            strength='STRONG' if confidence_score > 0.8 else 'MODERATE',
                            notes=f"Support Breakdown: Price({current_price:.4f}) broke below support({support_level:.4f}). Bearish continuation expected."
                        )
                        if signal:
                            signals.append(signal)
            
            return signals
            
        except Exception as e:
            logger.error(f"Error checking support/resistance breakouts: {e}")
            return signals
    
    def _check_pattern_breakouts(self, symbol: Symbol, current_price: float) -> List[TradingSignal]:
        """Check for pattern breakouts (triangles, rectangles, channels)"""
        signals = []
        
        try:
            # Get recent market data for pattern analysis
            recent_data = MarketData.objects.filter(
                symbol=symbol
            ).order_by('-timestamp')[:max(self.triangle_lookback, self.rectangle_lookback, self.channel_lookback)]
            
            if len(recent_data) < 10:
                return signals
            
            # Check for triangle breakout
            triangle_signal = self._check_triangle_breakout(symbol, recent_data, current_price)
            if triangle_signal:
                signals.append(triangle_signal)
            
            # Check for rectangle breakout
            rectangle_signal = self._check_rectangle_breakout(symbol, recent_data, current_price)
            if rectangle_signal:
                signals.append(rectangle_signal)
            
            # Check for channel breakout
            channel_signal = self._check_channel_breakout(symbol, recent_data, current_price)
            if channel_signal:
                signals.append(channel_signal)
            
            return signals
            
        except Exception as e:
            logger.error(f"Error checking pattern breakouts: {e}")
            return signals
    
    def _check_triangle_breakout(self, symbol: Symbol, recent_data: List[MarketData], current_price: float) -> Optional[TradingSignal]:
        """Check for triangle pattern breakout"""
        try:
            if len(recent_data) < self.triangle_lookback:
                return None
            
            # Extract highs and lows for triangle analysis
            highs = [float(data.high_price) for data in recent_data[:self.triangle_lookback]]
            lows = [float(data.low_price) for data in recent_data[:self.triangle_lookback]]
            
            # Simple triangle detection: converging highs and lows
            high_trend = (highs[0] - highs[-1]) / len(highs)  # Slope of highs
            low_trend = (lows[-1] - lows[0]) / len(lows)      # Slope of lows
            
            # Check if highs are declining and lows are rising (ascending triangle)
            if high_trend < -0.001 and low_trend > 0.001:
                # Check for breakout above upper trendline
                upper_trendline = highs[0] + (high_trend * len(highs))
                if current_price > upper_trendline * (1 + self.breakout_threshold):
                    if self._check_volume_confirmation(symbol, 1.3):
                        signal_type = self._get_or_create_signal_type('BUY')
                        confidence_score = 0.85  # High confidence for triangle breakout
                        
                        return self._create_signal(
                            symbol=symbol,
                            signal_type=signal_type,
                            confidence_score=confidence_score,
                            entry_price=current_price,
                            target_price=current_price * 1.08,  # 8% target
                            stop_loss=upper_trendline,  # Stop at trendline
                            strength='STRONG',
                            notes=f"Triangle Breakout: Ascending triangle breakout above {upper_trendline:.4f}. Bullish continuation expected."
                        )
            
            # Check if highs are declining and lows are declining (descending triangle)
            elif high_trend < -0.001 and low_trend < -0.001:
                # Check for breakdown below lower trendline
                lower_trendline = lows[0] + (low_trend * len(lows))
                if current_price < lower_trendline * (1 - self.breakout_threshold):
                    if self._check_volume_confirmation(symbol, 1.3):
                        signal_type = self._get_or_create_signal_type('SELL')
                        confidence_score = 0.85  # High confidence for triangle breakdown
                        
                        return self._create_signal(
                            symbol=symbol,
                            signal_type=signal_type,
                            confidence_score=confidence_score,
                            entry_price=current_price,
                            target_price=current_price * 0.92,  # 8% target
                            stop_loss=lower_trendline,  # Stop at trendline
                            strength='STRONG',
                            notes=f"Triangle Breakdown: Descending triangle breakdown below {lower_trendline:.4f}. Bearish continuation expected."
                        )
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking triangle breakout: {e}")
            return None
    
    def _check_rectangle_breakout(self, symbol: Symbol, recent_data: List[MarketData], current_price: float) -> Optional[TradingSignal]:
        """Check for rectangle pattern breakout"""
        try:
            if len(recent_data) < self.rectangle_lookback:
                return None
            
            # Extract highs and lows for rectangle analysis
            highs = [float(data.high_price) for data in recent_data[:self.rectangle_lookback]]
            lows = [float(data.low_price) for data in recent_data[:self.rectangle_lookback]]
            
            # Calculate rectangle boundaries
            upper_boundary = max(highs)
            lower_boundary = min(lows)
            rectangle_height = upper_boundary - lower_boundary
            
            # Check if price is in a rectangle (sideways movement)
            if lower_boundary <= current_price <= upper_boundary:
                # Check for breakout above upper boundary
                if current_price > upper_boundary * (1 + self.breakout_threshold):
                    if self._check_volume_confirmation(symbol, 1.4):
                        signal_type = self._get_or_create_signal_type('BUY')
                        confidence_score = 0.8  # Good confidence for rectangle breakout
                        
                        return self._create_signal(
                            symbol=symbol,
                            signal_type=signal_type,
                            confidence_score=confidence_score,
                            entry_price=current_price,
                            target_price=current_price + rectangle_height,  # Target = entry + rectangle height
                            stop_loss=upper_boundary,  # Stop at upper boundary
                            strength='STRONG',
                            notes=f"Rectangle Breakout: Price broke above rectangle upper boundary {upper_boundary:.4f}. Bullish continuation expected."
                        )
                
                # Check for breakdown below lower boundary
                elif current_price < lower_boundary * (1 - self.breakout_threshold):
                    if self._check_volume_confirmation(symbol, 1.4):
                        signal_type = self._get_or_create_signal_type('SELL')
                        confidence_score = 0.8  # Good confidence for rectangle breakdown
                        
                        return self._create_signal(
                            symbol=symbol,
                            signal_type=signal_type,
                            confidence_score=confidence_score,
                            entry_price=current_price,
                            target_price=current_price - rectangle_height,  # Target = entry - rectangle height
                            stop_loss=lower_boundary,  # Stop at lower boundary
                            strength='STRONG',
                            notes=f"Rectangle Breakdown: Price broke below rectangle lower boundary {lower_boundary:.4f}. Bearish continuation expected."
                        )
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking rectangle breakout: {e}")
            return None
    
    def _check_channel_breakout(self, symbol: Symbol, recent_data: List[MarketData], current_price: float) -> Optional[TradingSignal]:
        """Check for channel pattern breakout"""
        try:
            if len(recent_data) < self.channel_lookback:
                return None
            
            # Extract highs and lows for channel analysis
            highs = [float(data.high_price) for data in recent_data[:self.channel_lookback]]
            lows = [float(data.low_price) for data in recent_data[:self.channel_lookback]]
            
            # Calculate channel boundaries (parallel trendlines)
            high_trend = (highs[0] - highs[-1]) / len(highs)  # Slope of highs
            low_trend = (lows[0] - lows[-1]) / len(lows)      # Slope of lows
            
            # Check if highs and lows are parallel (channel pattern)
            if abs(high_trend - low_trend) < 0.001:  # Parallel trendlines
                # Calculate current channel boundaries
                upper_channel = highs[0] + (high_trend * len(highs))
                lower_channel = lows[0] + (low_trend * len(lows))
                
                # Check for breakout above upper channel
                if current_price > upper_channel * (1 + self.breakout_threshold):
                    if self._check_volume_confirmation(symbol, 1.5):
                        signal_type = self._get_or_create_signal_type('BUY')
                        confidence_score = 0.9  # Very high confidence for channel breakout
                        
                        return self._create_signal(
                            symbol=symbol,
                            signal_type=signal_type,
                            confidence_score=confidence_score,
                            entry_price=current_price,
                            target_price=current_price * 1.1,  # 10% target
                            stop_loss=upper_channel,  # Stop at upper channel
                            strength='VERY_STRONG',
                            notes=f"Channel Breakout: Price broke above upper channel {upper_channel:.4f}. Strong bullish continuation expected."
                        )
                
                # Check for breakdown below lower channel
                elif current_price < lower_channel * (1 - self.breakout_threshold):
                    if self._check_volume_confirmation(symbol, 1.5):
                        signal_type = self._get_or_create_signal_type('SELL')
                        confidence_score = 0.9  # Very high confidence for channel breakdown
                        
                        return self._create_signal(
                            symbol=symbol,
                            signal_type=signal_type,
                            confidence_score=confidence_score,
                            entry_price=current_price,
                            target_price=current_price * 0.9,  # 10% target
                            stop_loss=lower_channel,  # Stop at lower channel
                            strength='VERY_STRONG',
                            notes=f"Channel Breakdown: Price broke below lower channel {lower_channel:.4f}. Strong bearish continuation expected."
                        )
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking channel breakout: {e}")
            return None
    
    def _check_momentum_breakouts(self, symbol: Symbol, current_price: float) -> List[TradingSignal]:
        """Check for momentum-based breakouts"""
        signals = []
        
        try:
            # Get recent price data for momentum analysis
            recent_data = MarketData.objects.filter(
                symbol=symbol
            ).order_by('-timestamp')[:10]
            
            if len(recent_data) < 5:
                return signals
            
            # Calculate price momentum
            prices = [float(data.close_price) for data in recent_data]
            momentum = (prices[0] - prices[-1]) / prices[-1]  # Percentage change
            
            # Check for strong momentum breakout
            if abs(momentum) > self.min_breakout_strength:
                # Determine direction
                if momentum > 0:  # Bullish momentum
                    signal_type = self._get_or_create_signal_type('BUY')
                    confidence_score = min(0.9, 0.7 + (momentum * 2))  # Higher momentum = higher confidence
                    
                    signal = self._create_signal(
                        symbol=symbol,
                        signal_type=signal_type,
                        confidence_score=confidence_score,
                        entry_price=current_price,
                        target_price=current_price * (1 + momentum * 1.5),  # Extend momentum
                        stop_loss=current_price * (1 - momentum * 0.5),    # Tight stop
                        strength='STRONG' if confidence_score > 0.8 else 'MODERATE',
                        notes=f"Momentum Breakout: Strong bullish momentum {momentum:.1%}. Trend continuation expected."
                    )
                    if signal:
                        signals.append(signal)
                
                else:  # Bearish momentum
                    signal_type = self._get_or_create_signal_type('SELL')
                    confidence_score = min(0.9, 0.7 + (abs(momentum) * 2))  # Higher momentum = higher confidence
                    
                    signal = self._create_signal(
                        symbol=symbol,
                        signal_type=signal_type,
                        confidence_score=confidence_score,
                        entry_price=current_price,
                        target_price=current_price * (1 + momentum * 1.5),  # Extend momentum
                        stop_loss=current_price * (1 - momentum * 0.5),    # Tight stop
                        strength='STRONG' if confidence_score > 0.8 else 'MODERATE',
                        notes=f"Momentum Breakdown: Strong bearish momentum {abs(momentum):.1%}. Trend continuation expected."
                    )
                    if signal:
                        signals.append(signal)
            
            return signals
            
        except Exception as e:
            logger.error(f"Error checking momentum breakouts: {e}")
            return signals
    
    def _check_volume_confirmation(self, symbol: Symbol, multiplier: float) -> bool:
        """Check if volume confirms the breakout"""
        try:
            # Get recent volume data
            recent_data = MarketData.objects.filter(
                symbol=symbol
            ).order_by('-timestamp')[:20]
            
            if len(recent_data) < 10:
                return False
            
            # Calculate average volume
            volumes = [float(data.volume) for data in recent_data[1:]]  # Exclude most recent
            avg_volume = sum(volumes) / len(volumes)
            
            # Check if current volume is above threshold
            current_volume = float(recent_data[0].volume)
            return current_volume > (avg_volume * multiplier)
            
        except Exception as e:
            logger.error(f"Error checking volume confirmation: {e}")
            return False
    
    def _calculate_breakout_confidence(self, current_price: float, level: float, level_type: str) -> float:
        """Calculate confidence score for breakout signals"""
        try:
            # Base confidence
            base_confidence = 0.7
            
            # Distance from level (closer = higher confidence)
            distance = abs(current_price - level) / level
            if distance <= 0.02:  # Very close to level
                base_confidence += 0.1
            elif distance <= 0.05:  # Close to level
                base_confidence += 0.05
            
            # Level type preference
            if level_type == 'resistance':
                base_confidence += 0.05  # Slightly prefer resistance breakouts
            
            # Volume confirmation bonus
            if self._check_volume_confirmation(symbol, 1.5):
                base_confidence += 0.1
            
            return min(1.0, base_confidence)
            
        except Exception as e:
            logger.error(f"Error calculating breakout confidence: {e}")
            return 0.7
    
    def _get_or_create_signal_type(self, signal_name: str) -> SignalType:
        """Get or create a signal type"""
        try:
            signal_type, created = SignalType.objects.get_or_create(
                name=signal_name,
                defaults={
                    'description': f'{signal_name} signal from Breakout Strategy',
                    'color': '#28a745' if 'BUY' in signal_name else '#dc3545',
                    'is_active': True
                }
            )
            return signal_type
        except Exception as e:
            logger.error(f"Error getting/creating signal type {signal_name}: {e}")
            # Return a default signal type
            return SignalType.objects.filter(name='BUY').first() or SignalType.objects.first()
    
    def _create_signal(self, symbol: Symbol, signal_type: SignalType, 
                        confidence_score: float, entry_price: float,
                        target_price: float, stop_loss: float,
                        strength: str, notes: str) -> TradingSignal:
        """Create a trading signal"""
        try:
            # Calculate risk-reward ratio
            risk = abs(entry_price - stop_loss)
            reward = abs(target_price - entry_price)
            risk_reward_ratio = reward / risk if risk > 0 else 0
            
            # Calculate quality score
            quality_score = (confidence_score * 0.6 + 
                            min(1.0, risk_reward_ratio / 3.0) * 0.4)
            
            # Determine confidence level
            if confidence_score >= 0.85:
                confidence_level = 'VERY_HIGH'
            elif confidence_score >= 0.7:
                confidence_level = 'HIGH'
            elif confidence_score >= 0.5:
                confidence_level = 'MEDIUM'
            else:
                confidence_level = 'LOW'
            
            # Create signal
            signal = TradingSignal.objects.create(
                symbol=symbol,
                signal_type=signal_type,
                strength=strength,
                confidence_score=confidence_score,
                confidence_level=confidence_level,
                entry_price=Decimal(str(entry_price)),
                target_price=Decimal(str(target_price)),
                stop_loss=Decimal(str(stop_loss)),
                risk_reward_ratio=risk_reward_ratio,
                quality_score=quality_score,
                is_valid=True,
                expires_at=timezone.now() + timezone.timedelta(hours=24),
                technical_score=confidence_score,  # Breakout is purely technical
                sentiment_score=0.0,
                news_score=0.0,
                volume_score=0.0,
                pattern_score=0.0,
                # New timeframe and entry point fields
                timeframe='1H',  # Default timeframe for strategies
                entry_point_type='BREAKOUT',  # Specific to breakout strategy
                entry_point_details={},
                entry_zone_low=Decimal(str(entry_price * 0.99)),  # 1% below entry
                entry_zone_high=Decimal(str(entry_price * 1.01)),  # 1% above entry
                entry_confidence=confidence_score,  # Use confidence score as entry confidence
                notes=notes
            )
            
            logger.info(f"Created {signal_type.name} signal for {symbol.symbol} with confidence {confidence_score:.2f}")
            return signal
            
        except Exception as e:
            logger.error(f"Error creating breakout signal: {e}")
            return None


class MeanReversionStrategy(BaseStrategy):
    """Mean Reversion Strategy
    
    Generates signals based on:
    1. Price deviation from moving averages (oversold/overbought)
    2. RSI extreme levels with price reversion
    3. Bollinger Bands mean reversion signals
    4. Stochastic oscillator extreme levels
    5. Williams %R overbought/oversold conditions
    """
    
    def __init__(self):
        super().__init__()
        self.name = "Mean Reversion Strategy"
        self.description = "Generates signals based on mean reversion principles"
        
        # Strategy parameters
        self.sma_period = 20  # 20-period SMA for mean calculation
        self.rsi_period = 14  # 14-period RSI
        self.bb_period = 20   # 20-period Bollinger Bands
        self.stoch_period = 14  # 14-period Stochastic
        self.williams_period = 14  # 14-period Williams %R
        
        # Mean reversion thresholds
        self.price_deviation_threshold = 0.05  # 5% deviation from mean
        self.rsi_oversold = 30  # RSI oversold level
        self.rsi_overbought = 70  # RSI overbought level
        self.stoch_oversold = 20  # Stochastic oversold level
        self.stoch_overbought = 80  # Stochastic overbought level
        self.williams_oversold = -80  # Williams %R oversold level
        self.williams_overbought = -20  # Williams %R overbought level
        
        # Confirmation parameters
        self.volume_confirmation_multiplier = 1.1  # Volume should be 1.1x average (reduced from 1.3x)
        self.reversal_confirmation_periods = 2  # Number of periods to confirm reversal
        
    def generate_signals(self, symbol: Symbol) -> List[TradingSignal]:
        """Generate trading signals based on mean reversion analysis"""
        try:
            signals = []
            
            # Get current price and market data
            current_price = self._get_latest_price(symbol)
            if not current_price:
                return signals
            
            # Check price deviation from moving average
            ma_signals = self._check_price_deviation_signals(symbol, current_price)
            signals.extend(ma_signals)
            
            # Check RSI mean reversion signals
            rsi_signals = self._check_rsi_mean_reversion(symbol, current_price)
            signals.extend(rsi_signals)
            
            # Check Bollinger Bands mean reversion
            bb_signals = self._check_bollinger_bands_reversion(symbol, current_price)
            signals.extend(bb_signals)
            
            # Check Stochastic oscillator mean reversion
            stoch_signals = self._check_stochastic_reversion(symbol, current_price)
            signals.extend(stoch_signals)
            
            # Check Williams %R mean reversion
            williams_signals = self._check_williams_reversion(symbol, current_price)
            signals.extend(williams_signals)
            
            logger.info(f"Generated {len(signals)} mean reversion signals for {symbol.symbol}")
            return signals
            
        except Exception as e:
            logger.error(f"Error generating mean reversion signals for {symbol.symbol}: {e}")
            return []
    
    def _check_price_deviation_signals(self, symbol: Symbol, current_price: float) -> List[TradingSignal]:
        """Check for signals based on price deviation from moving average"""
        signals = []
        
        try:
            # Get SMA data
            sma_data = self._get_latest_indicators(symbol, 'SMA', self.sma_period, 3)
            logger.info(f"Found {len(sma_data)} SMA indicators for {symbol.symbol}")
            
            if len(sma_data) < 2:
                logger.warning(f"Insufficient SMA data for {symbol.symbol}")
                return signals
            
            current_sma = float(sma_data[0].value)
            previous_sma = float(sma_data[1].value)
            
            logger.info(f"Current SMA: {current_sma:.4f}, Current Price: {current_price:.4f}")
            
            # Calculate price deviation from SMA
            deviation = (current_price - current_sma) / current_sma
            logger.info(f"Price deviation: {deviation:.1%}, Threshold: {self.price_deviation_threshold:.1%}")
            
            # Check for oversold condition (price significantly below SMA)
            if deviation < -self.price_deviation_threshold:
                logger.info(f"Oversold condition detected: deviation {deviation:.1%} < -{self.price_deviation_threshold:.1%}")
                
                # Verify volume confirmation
                volume_confirmed = self._check_volume_confirmation(symbol, self.volume_confirmation_multiplier)
                logger.info(f"Volume confirmation: {volume_confirmed}")
                
                if volume_confirmed:
                    # Check for reversal confirmation
                    reversal_confirmed = self._check_reversal_confirmation(symbol, 'bullish')
                    logger.info(f"Reversal confirmation: {reversal_confirmed}")
                    
                    if reversal_confirmed:
                        signal_type = self._get_or_create_signal_type('BUY')
                        confidence_score = min(0.9, 0.7 + abs(deviation) * 2)
                        
                        signal = self._create_signal(
                            symbol=symbol,
                            signal_type=signal_type,
                            confidence_score=confidence_score,
                            entry_price=current_price,
                            target_price=current_sma,  # Target is the mean
                            stop_loss=current_price * 0.95,  # 5% stop loss
                            strength='STRONG' if confidence_score > 0.8 else 'MODERATE',
                            notes=f"Mean Reversion BUY: Price({current_price:.4f}) is {abs(deviation):.1%} below SMA({current_sma:.4f}). Reversion to mean expected."
                        )
                        if signal:
                            signals.append(signal)
                            logger.info(f"Created BUY signal for {symbol.symbol}")
            
            # Check for overbought condition (price significantly above SMA)
            elif deviation > self.price_deviation_threshold:
                logger.info(f"Overbought condition detected: deviation {deviation:.1%} > {self.price_deviation_threshold:.1%}")
                
                # Verify volume confirmation
                volume_confirmed = self._check_volume_confirmation(symbol, self.volume_confirmation_multiplier)
                logger.info(f"Volume confirmation: {volume_confirmed}")
                
                if volume_confirmed:
                    # Check for reversal confirmation
                    reversal_confirmed = self._check_reversal_confirmation(symbol, 'bearish')
                    logger.info(f"Reversal confirmation: {reversal_confirmed}")
                    
                    if reversal_confirmed:
                        signal_type = self._get_or_create_signal_type('SELL')
                        confidence_score = min(0.9, 0.7 + abs(deviation) * 2)
                        
                        signal = self._create_signal(
                            symbol=symbol,
                            signal_type=signal_type,
                            confidence_score=confidence_score,
                            entry_price=current_price,
                            target_price=current_sma,  # Target is the mean
                            stop_loss=current_price * 1.05,  # 5% stop loss
                            strength='STRONG' if confidence_score > 0.8 else 'MODERATE',
                            notes=f"Mean Reversion SELL: Price({current_price:.4f}) is {abs(deviation):.1%} above SMA({current_sma:.4f}). Reversion to mean expected."
                        )
                        if signal:
                            signals.append(signal)
                            logger.info(f"Created SELL signal for {symbol.symbol}")
            
            logger.info(f"Generated {len(signals)} price deviation signals for {symbol.symbol}")
            return signals
            
        except Exception as e:
            logger.error(f"Error checking price deviation signals: {e}")
            return signals
    
    def _check_rsi_mean_reversion(self, symbol: Symbol, current_price: float) -> List[TradingSignal]:
        """Check for RSI-based mean reversion signals"""
        signals = []
        
        try:
            # Get RSI data
            rsi_data = self._get_latest_indicators(symbol, 'RSI', self.rsi_period, 3)
            logger.info(f"Found {len(rsi_data)} RSI indicators for {symbol.symbol}")
            
            if len(rsi_data) < 2:
                logger.warning(f"Insufficient RSI data for {symbol.symbol}")
                return signals
            
            current_rsi = float(rsi_data[0].value)
            previous_rsi = float(rsi_data[1].value)
            
            # Check for oversold RSI with bullish reversal
            if current_rsi < self.rsi_oversold and previous_rsi < self.rsi_oversold:
                logger.info(f"RSI oversold condition detected: current={current_rsi:.1f}, previous={previous_rsi:.1f}")
                
                # RSI is oversold, check for reversal
                reversal_confirmed = self._check_reversal_confirmation(symbol, 'bullish')
                logger.info(f"RSI reversal confirmation: {reversal_confirmed}")
                
                if reversal_confirmed:
                    signal_type = self._get_or_create_signal_type('BUY')
                    confidence_score = 0.8  # High confidence for RSI oversold
                    
                    signal = self._create_signal(
                        symbol=symbol,
                        signal_type=signal_type,
                        confidence_score=confidence_score,
                        entry_price=current_price,
                        target_price=current_price * 1.06,  # 6% target
                        stop_loss=current_price * 0.94,  # 6% stop loss
                        strength='STRONG',
                        notes=f"RSI Mean Reversion BUY: RSI({current_rsi:.1f}) is oversold. Bullish reversal expected."
                    )
                    if signal:
                        signals.append(signal)
                        logger.info(f"Created RSI BUY signal for {symbol.symbol}")
            
            # Check for overbought RSI with bearish reversal
            elif current_rsi > self.rsi_overbought and previous_rsi > self.rsi_overbought:
                # RSI is overbought, check for reversal
                if self._check_reversal_confirmation(symbol, 'bearish'):
                    signal_type = self._get_or_create_signal_type('SELL')
                    confidence_score = 0.8  # High confidence for RSI overbought
                    
                    signal = self._create_signal(
                        symbol=symbol,
                        signal_type=signal_type,
                        confidence_score=confidence_score,
                        entry_price=current_price,
                        target_price=current_price * 0.94,  # 6% target
                        stop_loss=current_price * 1.06,  # 6% stop loss
                        strength='STRONG',
                        notes=f"RSI Mean Reversion SELL: RSI({current_rsi:.1f}) is overbought. Bearish reversal expected."
                    )
                    if signal:
                        signals.append(signal)
            
            return signals
            
        except Exception as e:
            logger.error(f"Error checking RSI mean reversion: {e}")
            return signals
    
    def _check_bollinger_bands_reversion(self, symbol: Symbol, current_price: float) -> List[TradingSignal]:
        """Check for Bollinger Bands mean reversion signals"""
        signals = []
        
        try:
            # Get Bollinger Bands data (separate upper, middle, lower)
            upper_band_data = self._get_latest_indicators(symbol, 'BB_UPPER', self.bb_period, 3)
            middle_band_data = self._get_latest_indicators(symbol, 'BB_MIDDLE', self.bb_period, 3)
            lower_band_data = self._get_latest_indicators(symbol, 'BB_LOWER', self.bb_period, 3)
            
            if len(upper_band_data) < 1 or len(middle_band_data) < 1 or len(lower_band_data) < 1:
                return signals
            
            current_upper = float(upper_band_data[0].value)
            current_middle = float(middle_band_data[0].value)
            current_lower = float(lower_band_data[0].value)
            
            # Check for price touching lower band (oversold)
            if current_price <= current_lower * 1.01:  # Within 1% of lower band
                if self._check_reversal_confirmation(symbol, 'bullish'):
                    signal_type = self._get_or_create_signal_type('BUY')
                    confidence_score = 0.85  # High confidence for BB touch
                    
                    signal = self._create_signal(
                        symbol=symbol,
                        signal_type=signal_type,
                        confidence_score=confidence_score,
                        entry_price=current_price,
                        target_price=current_middle,  # Target is the middle band (mean)
                        stop_loss=current_lower * 0.98,  # Stop below lower band
                        strength='STRONG',
                        notes=f"BB Mean Reversion BUY: Price({current_price:.4f}) touched lower band({current_lower:.4f}). Reversion to mean({current_middle:.4f}) expected."
                    )
                    if signal:
                        signals.append(signal)
            
            # Check for price touching upper band (overbought)
            elif current_price >= current_upper * 0.99:  # Within 1% of upper band
                if self._check_reversal_confirmation(symbol, 'bearish'):
                    signal_type = self._get_or_create_signal_type('SELL')
                    confidence_score = 0.85  # High confidence for BB touch
                    
                    signal = self._create_signal(
                        symbol=symbol,
                        signal_type=signal_type,
                        confidence_score=confidence_score,
                        entry_price=current_price,
                        target_price=current_middle,  # Target is the middle band (mean)
                        stop_loss=current_upper * 1.02,  # Stop above upper band
                        strength='STRONG',
                        notes=f"BB Mean Reversion SELL: Price({current_price:.4f}) touched upper band({current_upper:.4f}). Reversion to mean({current_middle:.4f}) expected."
                    )
                    if signal:
                        signals.append(signal)
            
            return signals
            
        except Exception as e:
            logger.error(f"Error checking Bollinger Bands reversion: {e}")
            return signals
    
    def _check_stochastic_reversion(self, symbol: Symbol, current_price: float) -> List[TradingSignal]:
        """Check for Stochastic oscillator mean reversion signals"""
        signals = []
        
        try:
            # Get Stochastic data
            stoch_data = self._get_latest_indicators(symbol, 'STOCH', self.stoch_period, 3)
            if len(stoch_data) < 2:
                return signals
            
            current_stoch = float(stoch_data[0].value)
            previous_stoch = float(stoch_data[1].value)
            
            # Check for oversold Stochastic with bullish reversal
            if current_stoch < self.stoch_oversold and previous_stoch < self.stoch_oversold:
                if self._check_reversal_confirmation(symbol, 'bullish'):
                    signal_type = self._get_or_create_signal_type('BUY')
                    confidence_score = 0.75  # Good confidence for Stochastic oversold
                    
                    signal = self._create_signal(
                        symbol=symbol,
                        signal_type=signal_type,
                        confidence_score=confidence_score,
                        entry_price=current_price,
                        target_price=current_price * 1.05,  # 5% target
                        stop_loss=current_price * 0.95,  # 5% stop loss
                        strength='MODERATE',
                        notes=f"Stochastic Mean Reversion BUY: Stochastic({current_stoch:.1f}) is oversold. Bullish reversal expected."
                    )
                    if signal:
                        signals.append(signal)
            
            # Check for overbought Stochastic with bearish reversal
            elif current_stoch > self.stoch_overbought and previous_stoch > self.stoch_overbought:
                if self._check_reversal_confirmation(symbol, 'bearish'):
                    signal_type = self._get_or_create_signal_type('SELL')
                    confidence_score = 0.75  # Good confidence for Stochastic overbought
                    
                    signal = self._create_signal(
                        symbol=symbol,
                        signal_type=signal_type,
                        confidence_score=confidence_score,
                        entry_price=current_price,
                        target_price=current_price * 0.95,  # 5% target
                        stop_loss=current_price * 1.05,  # 5% stop loss
                        strength='MODERATE',
                        notes=f"Stochastic Mean Reversion SELL: Stochastic({current_stoch:.1f}) is overbought. Bearish reversal expected."
                    )
                    if signal:
                        signals.append(signal)
            
            return signals
            
        except Exception as e:
            logger.error(f"Error checking Stochastic reversion: {e}")
            return signals
    
    def _check_williams_reversion(self, symbol: Symbol, current_price: float) -> List[TradingSignal]:
        """Check for Williams %R mean reversion signals"""
        signals = []
        
        try:
            # Get Williams %R data
            williams_data = self._get_latest_indicators(symbol, 'WILLIAMS_R', self.williams_period, 3)
            if len(williams_data) < 2:
                return signals
            
            current_williams = float(williams_data[0].value)
            previous_williams = float(williams_data[1].value)
            
            # Check for oversold Williams %R with bullish reversal
            if current_williams < self.williams_oversold and previous_williams < self.williams_oversold:
                if self._check_reversal_confirmation(symbol, 'bullish'):
                    signal_type = self._get_or_create_signal_type('BUY')
                    confidence_score = 0.75  # Good confidence for Williams %R oversold
                    
                    signal = self._create_signal(
                        symbol=symbol,
                        signal_type=signal_type,
                        confidence_score=confidence_score,
                        entry_price=current_price,
                        target_price=current_price * 1.05,  # 5% target
                        stop_loss=current_price * 0.95,  # 5% stop loss
                        strength='MODERATE',
                        notes=f"Williams %R Mean Reversion BUY: Williams %R({current_williams:.1f}) is oversold. Bullish reversal expected."
                    )
                    if signal:
                        signals.append(signal)
            
            # Check for overbought Williams %R with bearish reversal
            elif current_williams > self.williams_overbought and previous_williams > self.williams_overbought:
                if self._check_reversal_confirmation(symbol, 'bearish'):
                    signal_type = self._get_or_create_signal_type('SELL')
                    confidence_score = 0.75  # Good confidence for Williams %R overbought
                    
                    signal = self._create_signal(
                        symbol=symbol,
                        signal_type=signal_type,
                        confidence_score=confidence_score,
                        entry_price=current_price,
                        target_price=current_price * 0.95,  # 5% target
                        stop_loss=current_price * 1.05,  # 5% stop loss
                        strength='MODERATE',
                        notes=f"Williams %R Mean Reversion SELL: Williams %R({current_williams:.1f}) is overbought. Bearish reversal expected."
                    )
                    if signal:
                        signals.append(signal)
            
            return signals
            
        except Exception as e:
            logger.error(f"Error checking Williams %R reversion: {e}")
            return signals
    
    def _check_reversal_confirmation(self, symbol: Symbol, direction: str) -> bool:
        """Check if price reversal is confirmed"""
        try:
            # Get recent price data
            recent_data = MarketData.objects.filter(
                symbol=symbol
            ).order_by('-timestamp')[:self.reversal_confirmation_periods + 1]
            
            if len(recent_data) < self.reversal_confirmation_periods + 1:
                logger.warning(f"Insufficient data for reversal confirmation: {len(recent_data)} < {self.reversal_confirmation_periods + 1}")
                return False
            
            prices = [float(data.close_price) for data in recent_data]
            logger.info(f"Reversal confirmation prices: {prices}")
            
            if direction == 'bullish':
                # Check for upward price movement
                result = prices[0] > prices[1] > prices[2]
                logger.info(f"Bullish reversal check: {prices[0]:.4f} > {prices[1]:.4f} > {prices[2]:.4f} = {result}")
                return result
            else:  # bearish
                # Check for downward price movement
                result = prices[0] < prices[1] < prices[2]
                logger.info(f"Bearish reversal check: {prices[0]:.4f} < {prices[1]:.4f} < {prices[2]:.4f} = {result}")
                return result
                
        except Exception as e:
            logger.error(f"Error checking reversal confirmation: {e}")
            return False
    
    def _check_volume_confirmation(self, symbol: Symbol, multiplier: float) -> bool:
        """Check if volume confirms the signal"""
        try:
            # Get recent volume data
            recent_data = MarketData.objects.filter(
                symbol=symbol
            ).order_by('-timestamp')[:20]
            
            if len(recent_data) < 10:
                return False
            
            # Calculate average volume
            volumes = [float(data.volume) for data in recent_data[1:]]  # Exclude most recent
            avg_volume = sum(volumes) / len(volumes)
            
            # Check if current volume is above threshold
            current_volume = float(recent_data[0].volume)
            return current_volume > (avg_volume * multiplier)
            
        except Exception as e:
            logger.error(f"Error checking volume confirmation: {e}")
            return False
    
    def _get_or_create_signal_type(self, signal_name: str) -> SignalType:
        """Get or create a signal type"""
        try:
            signal_type, created = SignalType.objects.get_or_create(
                name=signal_name,
                defaults={
                    'description': f'{signal_name} signal from Mean Reversion Strategy',
                    'color': '#28a745' if 'BUY' in signal_name else '#dc3545',
                    'is_active': True
                }
            )
            return signal_type
        except Exception as e:
            logger.error(f"Error getting/creating signal type {signal_name}: {e}")
            # Return a default signal type
            return SignalType.objects.filter(name='BUY').first() or SignalType.objects.first()
    
    def _create_signal(self, symbol: Symbol, signal_type: SignalType, 
                        confidence_score: float, entry_price: float,
                        target_price: float, stop_loss: float,
                        strength: str, notes: str) -> TradingSignal:
        """Create a trading signal"""
        try:
            # Calculate risk-reward ratio
            risk = abs(entry_price - stop_loss)
            reward = abs(target_price - entry_price)
            risk_reward_ratio = reward / risk if risk > 0 else 0
            
            # Calculate quality score
            quality_score = (confidence_score * 0.6 + 
                            min(1.0, risk_reward_ratio / 3.0) * 0.4)
            
            # Determine confidence level
            if confidence_score >= 0.85:
                confidence_level = 'VERY_HIGH'
            elif confidence_score >= 0.7:
                confidence_level = 'HIGH'
            elif confidence_score >= 0.5:
                confidence_level = 'MEDIUM'
            else:
                confidence_level = 'LOW'
            
            # Create signal
            signal = TradingSignal.objects.create(
                symbol=symbol,
                signal_type=signal_type,
                strength=strength,
                confidence_score=confidence_score,
                confidence_level=confidence_level,
                entry_price=Decimal(str(entry_price)),
                target_price=Decimal(str(target_price)),
                stop_loss=Decimal(str(stop_loss)),
                risk_reward_ratio=risk_reward_ratio,
                quality_score=quality_score,
                is_valid=True,
                expires_at=timezone.now() + timezone.timedelta(hours=24),
                technical_score=confidence_score,  # Mean reversion is purely technical
                sentiment_score=0.0,
                news_score=0.0,
                volume_score=0.0,
                pattern_score=0.0,
                notes=notes
            )
            
            logger.info(f"Created {signal_type.name} signal for {symbol.symbol} with confidence {confidence_score:.2f}")
            return signal
            
        except Exception as e:
            logger.error(f"Error creating mean reversion signal: {e}")
            return None
