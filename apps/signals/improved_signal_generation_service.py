"""
Improved SignalGenerationService with proper price handling and deduplication

This service fixes the issues of:
1. Duplicate signals
2. Logically impossible entry prices and targets
3. Inconsistent take profit and stop loss calculations
"""

import logging
from decimal import Decimal
from typing import List, Optional, Dict, Any
from django.utils import timezone
from django.core.cache import cache

from apps.trading.models import Symbol
from apps.signals.models import TradingSignal, SignalType
from apps.data.real_price_service import get_live_prices
from apps.data.models import MarketData
from apps.signals.ethics import is_signal_ethical

logger = logging.getLogger(__name__)


class ImprovedSignalGenerationService:
    """Improved signal generation service with proper price handling"""
    
    def __init__(self):
        self.price_cache_timeout = 300  # 5 minutes
        self.signal_deduplication_window = 3600  # 1 hour
    
    def generate_signals_for_symbol(self, symbol: Symbol) -> List[TradingSignal]:
        """Generate clean, non-duplicate signals for a symbol"""
        logger.info(f"Generating improved signals for {symbol.symbol}")
        
        try:
            # Get current market price - this is critical
            current_price = self._get_reliable_current_price(symbol)
            if not current_price or current_price <= 0:
                logger.warning(f"No valid price found for {symbol.symbol}, skipping signal generation")
                return []
            
            logger.info(f"Using current price ${current_price:,.4f} for {symbol.symbol}")
            
            # Check for recent duplicates to prevent spam
            if self._has_recent_signals(symbol):
                logger.info(f"Recent signals exist for {symbol.symbol}, skipping to prevent duplicates")
                return []
            
            # Generate signals using improved strategy
            signals = self._generate_strategy_based_signals(symbol, current_price)
            
            # Apply final deduplication and validation
            validated_signals = self._validate_and_deduplicate_signals(signals, symbol)
            
            # Save validated signals (ethics-checked)
            saved_signals = []
            for signal in validated_signals:
                try:
                    ethics = is_signal_ethical(signal)
                    if not ethics.is_ethical:
                        logger.warning(f"Dropping unethical signal for {symbol.symbol}: {ethics.issues}")
                        continue
                    signal.save()
                    saved_signals.append(signal)
                    logger.info(f"Saved signal for {symbol.symbol}: {signal.signal_type.name} at ${signal.entry_price}")
                except Exception as e:
                    logger.error(f"Failed to save signal for {symbol.symbol}: {e}")
            
            logger.info(f"Generated {len(saved_signals)} valid signals for {symbol.symbol}")
            return saved_signals
            
        except Exception as e:
            logger.error(f"Error generating signals for {symbol.symbol}: {e}")
            return []
    
    def _get_reliable_current_price(self, symbol: Symbol) -> Optional[Decimal]:
        """Get reliable current price with multiple fallbacks"""
        try:
            # Cache key for price lookup
            cache_key = f"current_price_{symbol.symbol}"
            
            # Try cache first
            cached_price = cache.get(cache_key)
            if cached_price and float(cached_price) > 0:
                return Decimal(str(cached_price))
            
            # Strategy 1: Try live prices from Binance/CoinGecko
            live_prices = get_live_prices()
            if symbol.symbol in live_prices:
                live_data = live_prices[symbol.symbol]
                price = live_data.get('price', 0)
                if price and price > 0:
                    price_decimal = Decimal(str(price))
                    cache.set(cache_key, float(price_decimal), self.price_cache_timeout)
                    logger.info(f"Using live price for {symbol.symbol}: ${price_decimal:,}")
                    return price_decimal
            
            # Strategy 2: Try database market data (last 24 hours)
            recent_data = MarketData.objects.filter(
                symbol=symbol,
                timestamp__gte=timezone.now() - timezone.timedelta(hours=24)
            ).order_by('-timestamp').first()
            
            if recent_data and recent_data.close_price and float(recent_data.close_price) > 0:
                price_decimal = Decimal(str(recent_data.close_price))
                cache.set(cache_key, float(price_decimal), self.price_cache_timeout)
                logger.info(f"Using recent database price for {symbol.symbol}: ${price_decimal:,}")
                return price_decimal
            
            # Strategy 3: Use reasonable fallback prices (updated for 2024/2025)
            fallback_prices = {
                'BTC': 120000.0, 'ETH': 4500.0, 'BNB': 700.0, 'ADA': 0.85, 'SOL': 250.0,
                'XRP': 0.65, 'DOGE': 0.25, 'MATIC': 0.95, 'DOT': 7.5, 'AVAX': 35.0,
                'LINK': 22.0, 'UNI': 12.0, 'ATOM': 11.0, 'FTM': 1.8, 'ALGO': 0.15,
                'VET': 0.04, 'ICP': 12.0, 'THETA': 1.8, 'SAND': 0.45, 'MANA': 0.55,
                'LTC': 95.0, 'BCH': 450.0, 'ETC': 25.0, 'XLM': 0.12, 'TRX': 0.18,
                'XMR': 180.0, 'ZEC': 45.0, 'DASH': 70.0, 'NEO': 20.0, 'QTUM': 4.5,
                'AAVE': 280.0, 'JUP': 1.2, 'IMX': 0.75, 'BONK': 0.000025, 'SUPER': 0.60,
                'NEAR': 8.5, 'LINKUSDT': 22.0, 'ADAUSDT': 0.85, 'AVAXUSDT': 35.0,
                'AAVEUSDT': 280.0, 'BTCUSDT': 120000.0, 'ETHUSDT': 4500.0
            }
            
            fallback_price = fallback_prices.get(symbol.symbol, None)
            if fallback_price:
                price_decimal = Decimal(str(fallback_price))
                cache.set(cache_key, float(price_decimal), self.price_cache_timeout)
                logger.warning(f"Using fallback price for {symbol.symbol}: ${price_decimal:,}")
                return price_decimal
            
            # If no fallback available, return None
            logger.error(f"No price data available for {symbol.symbol}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting price for {symbol.symbol}: {e}")
            return None
    
    def _has_recent_signals(self, symbol: Symbol) -> bool:
        """Check if there are recent signals to prevent spam"""
        try:
            recent_count = TradingSignal.objects.filter(
                symbol=symbol,
                created_at__gte=timezone.now() - timezone.timedelta(seconds=self.signal_deduplication_window),
                is_valid=True
            ).count()
            
            return recent_count > 0
        except Exception as e:
            logger.error(f"Error checking recent signals for {symbol.symbol}: {e}")
            return False
    
    def _generate_strategy_based_signals(self, symbol: Symbol, current_price: Decimal) -> List[TradingSignal]:
        """Generate signals based on improved strategy logic"""
        signals = []
        
        try:
            # Analyze market conditions for the symbol
            technical_analysis = self._analyze_technical_indicators(symbol, current_price)
            
            # Only generate signals if conditions are met
            if technical_analysis['should_generate_buy_signal']:
                buy_signal = self._create_buy_signal(symbol, current_price, technical_analysis)
                if buy_signal:
                    signals.append(buy_signal)
            
            if technical_analysis['should_generate_sell_signal']:
                sell_signal = self._create_sell_signal(symbol, current_price, technical_analysis)
                if sell_signal:
                    signals.append(sell_signal)
            
        except Exception as e:
            logger.error(f"Error generating strategy signals for {symbol.symbol}: {e}")
        
        return signals
    
    def _analyze_technical_indicators(self, symbol: Symbol, current_price: Decimal) -> Dict[str, Any]:
        """Analyze technical indicators to determine signal generation"""
        try:
            # Get recent market data for analysis
            recent_data = MarketData.objects.filter(
                symbol=symbol
            ).order_by('-timestamp')[:50]  # Last 50 candles
            
            if not recent_data.exists():
                return self._get_default_analysis()
            
            prices = [float(candle.close_price) for candle in recent_data]
            
            # Simple moving averages
            sma_20 = sum(prices[:20]) / min(20, len(prices)) if len(prices) >= 20 else sum(prices) / len(prices)
            sma_50 = sum(prices[:min(50, len(prices))]) / min(50, len(prices))
            
            # Price momentum
            price_change_24h = ((float(current_price) - prices[24]) / prices[24]) * 100 if len(prices) > 24 else 0
            
            # Simple RSI calculation
            rsi = self._calculate_rsi(prices[:14])
            
            # Volume analysis (if available)
            volumes = [float(candle.volume) for candle in recent_data if candle.volume]
            avg_volume = sum(volumes) / len(volumes) if volumes else 1
            
            return {
                'current_price': float(current_price),
                'sma_20': sma_20,
                'sma_50': sma_50,
                'price_change_24h': price_change_24h,
                'rsi': rsi,
                'avg_volume': avg_volume,
                'should_generate_buy_signal': sma_20 > sma_50 and rsi < 70 and price_change_24h < 10,
                'should_generate_sell_signal': sma_20 < sma_50 and rsi > 30 and price_change_24h > -10,
                'confidence_score': min(0.95, max(0.5, abs(rsi - 50) / 50))
            }
            
        except Exception as e:
            logger.error(f"Error analyzing technical indicators for {symbol.symbol}: {e}")
            return self._get_default_analysis()
    
    def _calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        """Calculate RSI indicator"""
        try:
            if len(prices) < 2:
                return 50.0  # Neutral RSI
            
            gains = []
            losses = []
            
            for i in range(1, len(prices)):
                change = prices[i] - prices[i-1]
                if change > 0:
                    gains.append(change)
                    losses.append(0)
                else:
                    gains.append(0)
                    losses.append(abs(change))
            
            avg_gain = sum(gains[:period]) / period if gains else 0
            avg_loss = sum(losses[:period]) / period if losses else 0
            
            if avg_loss == 0:
                return 100.0
            
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            
            return min(100, max(0, rsi))
            
        except Exception:
            return 50.0
    
    def _get_default_analysis(self) -> Dict[str, Any]:
        """Get default analysis when no data is available"""
        return {
            'current_price': 1.0,
            'sma_20': 1.0,
            'sma_50': 1.0,
            'price_change_24h': 0,
            'rsi': 50,
            'avg_volume': 1,
            'should_generate_buy_signal': False,
            'should_generate_sell_signal': False,
            'confidence_score': 0.5
        }
    
    def _create_buy_signal(self, symbol: Symbol, current_price: Decimal, analysis: Dict[str, Any]) -> Optional[TradingSignal]:
        """Create a buy signal with proper risk management"""
        try:
            # Get signal type
            signal_type, _ = SignalType.objects.get_or_create(
                name='BUY',
                defaults={'description': 'Buy signal based on technical analysis'}
            )
            
            # Calculate proper target and stop loss using current price
            target_price, stop_loss = self._calculate_target_and_stop_loss(
                current_price, 'BUY', analysis['confidence_score']
            )
            
            # Validate prices make sense
            if not self._validate_price_targets(current_price, target_price, stop_loss, 'BUY'):
                logger.warning(f"Invalid price targets for BUY signal on {symbol.symbol}")
                return None
            
            # Calculate confidence level
            confidence_percentage = analysis['confidence_score'] * 100
            if confidence_percentage < 50:
                confidence_level = 'LOW'
            elif confidence_percentage < 70:
                confidence_level = 'MEDIUM'
            elif confidence_percentage < 85:
                confidence_level = 'HIGH'
            else:
                confidence_level = 'VERY_HIGH'
            
            # Create signal
            signal = TradingSignal(
                symbol=symbol,
                signal_type=signal_type,
                strength='MODERATE',
                confidence_score=analysis['confidence_score'],
                confidence_level=confidence_level,
                entry_price=current_price,
                target_price=target_price,
                stop_loss=stop_loss,
                timeframe='1D',
                entry_point_type='ACCUMULATION_ZONE',
                entry_confidence=analysis['confidence_score'],
                technical_score=analysis['confidence_score'],
                economic_score=0.7,  # Default economic score
                sentiment_score=0.5,    # Neutral sentiment
                quality_score=analysis['confidence_score'],
                is_valid=True,
                is_executed=False
            )
            
            logger.info(f"Created BUY signal for {symbol.symbol}: Entry=${current_price}, Target=${target_price}, Stop=${stop_loss}")
            return signal
            
        except Exception as e:
            logger.error(f"Error creating BUY signal for {symbol.symbol}: {e}")
            return None
    
    def _create_sell_signal(self, symbol: Symbol, current_price: Decimal, analysis: Dict[str, Any]) -> Optional[TradingSignal]:
        """Create a sell signal with proper risk management"""
        try:
            # Get signal type
            signal_type, _ = SignalType.objects.get_or_create(
                name='SELL',
                defaults={'description': 'Sell signal based on technical analysis'}
            )
            
            # Calculate proper target and stop loss using current price
            target_price, stop_loss = self._calculate_target_and_stop_loss(
                current_price, 'SELL', analysis['confidence_score']
            )
            
            # Validate prices make sense
            if not self._validate_price_targets(current_price, target_price, stop_loss, 'SELL'):
                logger.warning(f"Invalid price targets for SELL signal on {symbol.symbol}")
                return None
            
            # Calculate confidence level
            confidence_percentage = analysis['confidence_score'] * 100
            if confidence_percentage < 50:
                confidence_level = 'LOW'
            elif confidence_percentage < 70:
                confidence_level = 'MEDIUM'
            elif confidence_percentage < 85:
                confidence_level = 'HIGH'
            else:
                confidence_level = 'VERY_HIGH'
            
            # Create signal
            signal = TradingSignal(
                symbol=symbol,
                signal_type=signal_type,
                strength='MODERATE',
                confidence_score=analysis['confidence_score'],
                confidence_level=confidence_level,
                entry_price=current_price,
                target_price=target_price,
                stop_loss=stop_loss,
                timeframe='1D',
                entry_point_type='TREND_FOLLOWING',
                entry_confidence=analysis['confidence_score'],
                technical_score=analysis['confidence_score'],
                economic_score=0.3,  # Lower economic score for sell
                sentiment_score=0.4,    # Slightly bearish sentiment
                quality_score=analysis['confidence_score'],
                is_valid=True,
                is_executed=False
            )
            
            logger.info(f"Created SELL signal for {symbol.symbol}: Entry=${current_price}, Target=${target_price}, Stop=${stop_loss}")
            return signal
            
        except Exception as e:
            logger.error(f"Error creating SELL signal for {symbol.symbol}: {e}")
            return None
    
    def _calculate_target_and_stop_loss(self, entry_price: Decimal, signal_type: str, confidence: float) -> tuple[Decimal, Decimal]:
        """Calculate realistic target and stop loss based on entry price"""
        try:
            # Use percentage-based approach instead of fixed dollar amounts
            if signal_type in ['BUY', 'STRONG_BUY']:
                # For buy signals: target above entry, stop below entry
                profit_percentage = Decimal('0.15')  # 15% profit target
                loss_percentage = Decimal('0.08')     # 8% stop loss
                
                target_price = entry_price * (Decimal('1.0') + profit_percentage)
                stop_loss = entry_price * (Decimal('1.0') - loss_percentage)
                
            else:  # SELL signals
                # For sell signals: target below entry, stop above entry
                profit_percentage = Decimal('0.12')  # 12% profit target for sells
                loss_percentage = Decimal('0.06')     # 6% stop loss for sells
                
                target_price = entry_price * (Decimal('1.0') - profit_percentage)
                stop_loss = entry_price * (Decimal('1.0') + loss_percentage)
            
            # Ensure prices are positive and reasonable
            target_price = max(target_price, Decimal('0.000001'))  # Minimum price
            stop_loss = max(stop_loss, Decimal('0.000001'))
            
            return target_price, stop_loss
            
        except Exception as e:
            logger.error(f"Error calculating target/stop loss: {e}")
            # Fallback calculation
            if signal_type in ['BUY', 'STRONG_BUY']:
                return entry_price * Decimal('1.05'), entry_price * Decimal('0.95')
            else:
                return entry_price * Decimal('0.95'), entry_price * Decimal('1.05')
    
    def _validate_price_targets(self, entry: Decimal, target: Decimal, stop: Decimal, signal_type: str) -> bool:
        """Validate that price targets make logical sense"""
        try:
            # Prices must be positive
            if entry <= 0 or target <= 0 or stop <= 0:
                return False
            
            if signal_type in ['BUY', 'STRONG_BUY']:
                # For buy: target > entry > stop_loss
                return target > entry > stop
            else:
                # For sell: stop_loss > entry > target
                return stop > entry > target
                
        except Exception:
            return False
    
    def _validate_and_deduplicate_signals(self, signals: List[TradingSignal], symbol: Symbol) -> List[TradingSignal]:
        """Validate signals and remove duplicates"""
        validated_signals = []
        
        for signal in signals:
            try:
                # Check for duplicates within the batch
                is_duplicate = False
                for existing in validated_signals:
                    if (existing.signal_type == signal.signal_type and 
                        abs(float(existing.entry_price - signal.entry_price)) < 0.01):
                        is_duplicate = True
                        break
                
                if not is_duplicate:
                    validated_signals.append(signal)
                else:
                    logger.info(f"Skipping duplicate signal for {symbol.symbol}: {signal.signal_type.name}")
                    
            except Exception as e:
                logger.error(f"Error validating signal for {symbol.symbol}: {e}")
        
        return validated_signals


# Create global instance
improved_signal_service = ImprovedSignalGenerationService()


def generate_improved_signals_for_symbol(symbol_name: str) -> Dict[str, Any]:
    """Generate improved signals for a symbol"""
    try:
        symbol = Symbol.objects.get(symbol__iexact=symbol_name, is_active=True)
        signals = improved_signal_service.generate_signals_for_symbol(symbol)
        
        return {
            'success': True,
            'symbol': symbol.symbol,
            'signals_generated': len(signals),
            'signal_ids': [s.id for s in signals]
        }
    except Symbol.DoesNotExist:
        return {
            'success': False,
            'error': f'Symbol {symbol_name} not found'
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }
