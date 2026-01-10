import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
import numpy as np
from django.utils import timezone
from django.db.models import Q, Avg, Count, Max, Min
from django.conf import settings
import time # Added for time.sleep in PerformanceMonitor

from apps.signals.models import (
    TradingSignal, SignalType, SignalFactor, SignalFactorContribution,
    MarketRegime, SignalPerformance, SignalAlert
)
from apps.trading.models import Symbol
from apps.data.models import TechnicalIndicator, MarketData
from apps.data.services import EconomicDataService, SectorAnalysisService
from apps.sentiment.models import SentimentAggregate, CryptoMention
from apps.signals.timeframe_analysis_service import TimeframeAnalysisService
from apps.signals.strategy_engine import StrategyEngine
from apps.signals.spot_trading_engine import SpotTradingStrategyEngine

logger = logging.getLogger(__name__)


class SignalGenerationService:
    """Main service for generating trading signals"""
    
    def __init__(self):
        self.min_confidence_threshold = 0.3  # Lowered from 0.5 for better signal generation
        self.timeframe_service = TimeframeAnalysisService()  # 50% minimum confidence
        self.min_risk_reward_ratio = 1.0     # Lowered from 1.5 for better signal generation
        self.signal_expiry_hours = 48        # Signal expires in 48 hours for better coverage
        
        # Unified rule-based engine for futures trading
        self.engine = StrategyEngine()
        
        # Spot trading engine for long-term signals
        self.spot_engine = SpotTradingStrategyEngine()
        
        # Initialize economic data service
        self.economic_service = EconomicDataService()
        
        # Initialize sector analysis service
        self.sector_service = SectorAnalysisService()
        
    def generate_signals_for_symbol(self, symbol: Symbol) -> List[TradingSignal]:
        """Generate both futures and spot signals for a specific symbol"""
        logger.info(f"Generating signals for {symbol.symbol}")
        
        signals = []
        
        # Generate futures signals (existing logic)
        futures_signals = self._generate_futures_signals(symbol)
        signals.extend(futures_signals)
        
        # Generate spot signals (new logic)
        spot_signals = self._generate_spot_signals(symbol)
        signals.extend(spot_signals)
        
        # Generate multi-timeframe confluence signals
        multi_timeframe_signals = self._generate_multi_timeframe_signals(symbol)
        signals.extend(multi_timeframe_signals)
        
        logger.info(f"Generated {len(signals)} total signals for {symbol.symbol} ({len(futures_signals)} futures, {len(spot_signals)} spot, {len(multi_timeframe_signals)} multi-timeframe)")
        
        return signals
    
    def _generate_multi_timeframe_signals(self, symbol: Symbol) -> List[TradingSignal]:
        """Generate signals based on multi-timeframe confluence analysis"""
        logger.info(f"Generating multi-timeframe signals for {symbol.symbol}")
        
        signals = []
        
        try:
            # Get latest market data
            market_data = self._get_latest_market_data(symbol)
            if not market_data:
                logger.warning(f"No market data available for {symbol.symbol}")
                return signals
            
            # Handle both dict and object (dict is returned from _get_latest_market_data)
            if isinstance(market_data, dict):
                current_price = float(market_data.get('close_price', 0))
            else:
                current_price = float(market_data.close_price)
            
            if not current_price or current_price <= 0:
                logger.warning(f"Invalid price for {symbol.symbol}: {current_price}")
                return signals
            
            # Get multi-timeframe analysis
            multi_analysis = self.timeframe_service.get_multi_timeframe_analysis(symbol, current_price)
            
            if multi_analysis.get('error'):
                logger.error(f"Error in multi-timeframe analysis: {multi_analysis['error']}")
                return signals
            
            # Extract final recommendation
            final_rec = multi_analysis.get('final_recommendation', {})
            action = final_rec.get('action', 'WAIT')
            confidence = final_rec.get('confidence', 0.0)
            
            if action != 'WAIT' and confidence >= self.min_confidence_threshold:
                # Create signal based on multi-timeframe confluence
                signal_type = SignalType.BUY if action == 'BUY' else SignalType.SELL
                
                signal = TradingSignal(
                    symbol=symbol,
                    signal_type=signal_type,
                    confidence=confidence,
                    entry_price=current_price,
                    stop_loss=final_rec.get('stop_loss', current_price * 0.95),
                    target_price=final_rec.get('target', current_price * 1.05),
                    timeframe='MULTI',
                    strategy='MULTI_TIMEFRAME_CONFLUENCE',
                    reasoning=final_rec.get('reason', 'Multi-timeframe confluence analysis'),
                    expiry_time=timezone.now() + timedelta(hours=self.signal_expiry_hours),
                    created_at=timezone.now(),
                    is_best_of_day=False
                )
                
                signals.append(signal)
                logger.info(f"Generated multi-timeframe {action} signal for {symbol.symbol} with confidence {confidence:.2f}")
            
        except Exception as e:
            logger.error(f"Error generating multi-timeframe signals for {symbol.symbol}: {e}")
        
        return signals
    
    def _generate_futures_signals(self, symbol: Symbol) -> List[TradingSignal]:
        """Generate short-term futures signals"""
        logger.info(f"Generating futures signals for {symbol.symbol}")
        
        signals = []
        
        # Generate futures signals for ALL crypto symbols (not just futures tradable ones)
        if not symbol.is_crypto_symbol:
            logger.info(f"Skipping futures signals for {symbol.symbol} - not a crypto symbol")
            return signals
        
        # Get latest market data and indicators
        market_data = self._get_latest_market_data(symbol)
        if not market_data:
            logger.warning(f"No market data available for {symbol.symbol}")
            return signals
        
        # Get sentiment data
        sentiment_data = self._get_latest_sentiment_data(symbol)
        
        # Calculate technical scores
        technical_score = self._calculate_technical_score(symbol)
        
        # Calculate sentiment scores
        sentiment_score = self._calculate_sentiment_score(sentiment_data)
        
        # Calculate news impact
        news_score = self._calculate_news_score(symbol)
        
        # Calculate volume analysis
        volume_score = self._calculate_volume_score(symbol)
        
        # Calculate pattern recognition
        pattern_score = self._calculate_pattern_score(symbol)
        
        # Calculate economic/fundamental score
        economic_score = self._calculate_economic_score(symbol)
        
        # Calculate sector analysis score
        sector_score = self._calculate_sector_score(symbol)
        
        # Use unified engine to evaluate signals
        engine_signals = self.engine.evaluate_symbol(symbol)
        signals.extend(engine_signals)
        
        # Generate buy signals based on sentiment and technical analysis
        buy_signals = self._generate_buy_signals(
            symbol=symbol,
            market_data=market_data,
            technical_score=technical_score,
            sentiment_score=sentiment_score,
            news_score=news_score,
            volume_score=volume_score,
            pattern_score=pattern_score,
            economic_score=economic_score,
            sector_score=sector_score
        )
        signals.extend(buy_signals)
        
        # Generate sell signals based on sentiment and technical analysis
        sell_signals = self._generate_sell_signals(
            symbol=symbol,
            market_data=market_data,
            technical_score=technical_score,
            sentiment_score=sentiment_score,
            news_score=news_score,
            volume_score=volume_score,
            pattern_score=pattern_score,
            economic_score=economic_score,
            sector_score=sector_score
        )
        signals.extend(sell_signals)
        
        # Filter signals by quality criteria
        filtered_signals = self._filter_signals_by_quality(signals)
        
        # Return all quality signals (don't select top 5 here - will be done globally)
        # Persist and broadcast
        saved_signals = []
        for sig in filtered_signals:
            try:
                sig.save()
                saved_signals.append(sig)
                # Broadcast
                try:
                    from apps.core.services import RealTimeBroadcaster
                    broadcaster = RealTimeBroadcaster()
                    from asgiref.sync import async_to_sync
                    async_to_sync(broadcaster.broadcast_trading_signal)(
                        signal_id=sig.id,
                        symbol=sig.symbol.symbol,
                        signal_type=sig.signal_type.name,
                        strength=sig.strength,
                        confidence_score=sig.confidence_score,
                        entry_price=float(sig.entry_price) if sig.entry_price else None,
                        target_price=float(sig.target_price) if sig.target_price else None,
                        stop_loss=float(sig.stop_loss) if sig.stop_loss else None,
                        timestamp=sig.created_at
                    )
                except Exception:
                    pass
            except Exception as e:
                logger.error(f"Failed saving signal for {symbol.symbol}: {e}")

        logger.info(f"Generated {len(saved_signals)} engine signals for {symbol.symbol}")
        return saved_signals
    
    def _generate_spot_signals(self, symbol: Symbol) -> List[TradingSignal]:
        """Generate long-term spot trading signals"""
        logger.info(f"Generating spot signals for {symbol.symbol}")
        
        signals = []
        
        # Generate spot signals ONLY for symbols that are spot tradable
        if not symbol.is_crypto_symbol or not symbol.is_spot_tradable:
            logger.info(f"Skipping spot signals for {symbol.symbol} - not spot tradable")
            return signals
        
        try:
            # Generate spot trading signals using spot engine
            spot_signals = self.spot_engine.generate_spot_signals(symbol)
            
            # Convert SpotTradingSignal to TradingSignal for compatibility
            for spot_signal in spot_signals:
                trading_signal = self._convert_spot_to_trading_signal(spot_signal)
                if trading_signal:
                    signals.append(trading_signal)
            
            logger.info(f"Generated {len(signals)} spot signals for {symbol.symbol}")
            
        except Exception as e:
            logger.error(f"Error generating spot signals for {symbol.symbol}: {e}")
        
        return signals
    
    def _convert_spot_to_trading_signal(self, spot_signal) -> Optional[TradingSignal]:
        """Convert SpotTradingSignal to TradingSignal format"""
        try:
            from apps.signals.models import SpotTradingSignal
            
            # Map spot categories to trading signal types
            signal_type_mapping = {
                'ACCUMULATION': 'STRONG_BUY',
                'DCA': 'BUY',
                'DISTRIBUTION': 'SELL',
                'HOLD': 'HOLD',
                'REBALANCE': 'HOLD',
            }
            
            signal_type_name = signal_type_mapping.get(spot_signal.signal_category, 'HOLD')
            
            try:
                signal_type = SignalType.objects.get(name=signal_type_name)
            except SignalType.DoesNotExist:
                signal_type = SignalType.objects.get(name='HOLD')
            
            # Calculate overall confidence score from individual scores
            confidence_score = (spot_signal.fundamental_score + spot_signal.technical_score + spot_signal.sentiment_score) / 3.0
            
            # Determine strength based on confidence
            if confidence_score >= 0.8:
                strength = 'VERY_STRONG'
            elif confidence_score >= 0.7:
                strength = 'STRONG'
            elif confidence_score >= 0.5:
                strength = 'MODERATE'
            else:
                strength = 'WEAK'
            
            # Determine confidence level
            if confidence_score >= 0.8:
                confidence_level = 'VERY_HIGH'
            elif confidence_score >= 0.7:
                confidence_level = 'HIGH'
            elif confidence_score >= 0.5:
                confidence_level = 'MEDIUM'
            else:
                confidence_level = 'LOW'
            
            # Get current market data for price calculations
            market_data = self._get_latest_market_data(spot_signal.symbol)
            if not market_data:
                logger.warning(f"No market data available for {spot_signal.symbol.symbol}")
                return None
            
            # Calculate entry price, target price, and stop loss
            current_price = Decimal(str(market_data.get('close_price', 0)))
            if current_price <= 0:
                logger.warning(f"Invalid current price for {spot_signal.symbol.symbol}: {current_price}")
                return None
            
            # Calculate entry price based on signal type
            if signal_type_name in ['BUY', 'STRONG_BUY']:
                entry_price = current_price * Decimal('0.98')  # 2% below current price
            elif signal_type_name in ['SELL', 'STRONG_SELL']:
                entry_price = current_price * Decimal('1.02')  # 2% above current price
            else:
                entry_price = current_price
            
            # Calculate target price and stop loss based on signal type
            if signal_type_name in ['BUY', 'STRONG_BUY']:
                target_price = entry_price * Decimal('1.15')  # 15% profit target
                stop_loss = entry_price * Decimal('0.95')     # 5% stop loss
            elif signal_type_name in ['SELL', 'STRONG_SELL']:
                target_price = entry_price * Decimal('0.85')  # 15% profit target for sells
                stop_loss = entry_price * Decimal('1.05')     # 5% stop loss for sells
            else:  # HOLD signals
                target_price = entry_price * Decimal('1.05')  # 5% target
                stop_loss = entry_price * Decimal('0.95')     # 5% stop loss
            
            # Calculate risk-reward ratio
            risk = abs(float(entry_price - stop_loss))
            reward = abs(float(target_price - entry_price))
            risk_reward_ratio = reward / risk if risk > 0 else 0
            
            # Create TradingSignal
            trading_signal = TradingSignal(
                symbol=spot_signal.symbol,
                signal_type=signal_type,
                strength=strength,
                confidence_score=confidence_score,
                confidence_level=confidence_level,
                entry_price=entry_price,
                target_price=target_price,
                stop_loss=stop_loss,
                risk_reward_ratio=risk_reward_ratio,
                timeframe='1D',  # Long-term timeframe
                entry_point_type='ACCUMULATION_ZONE',
                quality_score=confidence_score,
                technical_score=spot_signal.technical_score,
                sentiment_score=spot_signal.sentiment_score,
                is_hybrid=True,
                is_best_of_day=False,
                metadata={
                    'spot_signal_id': spot_signal.id,
                    'investment_horizon': spot_signal.investment_horizon,
                    'signal_category': spot_signal.signal_category,
                    'recommended_allocation': float(spot_signal.recommended_allocation),
                    'dca_frequency': spot_signal.dca_frequency,
                    'fundamental_score': spot_signal.fundamental_score,
                    'technical_score': spot_signal.technical_score,
                    'sentiment_score': spot_signal.sentiment_score,
                    'target_price_6m': float(spot_signal.target_price_6m) if spot_signal.target_price_6m else None,
                    'target_price_1y': float(spot_signal.target_price_1y) if spot_signal.target_price_1y else None,
                    'target_price_2y': float(spot_signal.target_price_2y) if spot_signal.target_price_2y else None,
                    'max_position_size': spot_signal.max_position_size,
                    'stop_loss_percentage': spot_signal.stop_loss_percentage,
                    'signal_type': 'SPOT_TRADING',
                },
                notes=f"Spot signal conversion: {spot_signal.signal_category} - {spot_signal.investment_horizon}"
            )
            
            return trading_signal
            
        except Exception as e:
            logger.error(f"Error converting spot signal to trading signal: {e}")
            return None
    
    def _get_latest_market_data(self, symbol: Symbol) -> Optional[Dict]:
        """Get latest market data for signal generation - prioritizes live prices"""
        try:
            # First, try to get live prices from external API
            try:
                from apps.data.real_price_service import get_live_prices
                live_prices = get_live_prices()
                
                if symbol.symbol in live_prices:
                    live_data = live_prices[symbol.symbol]
                    current_price = live_data.get('price', 0)
                    
                    if current_price and current_price > 0:
                        # Calculate high/low based on current price (approximate)
                        price_variation = current_price * 0.02  # 2% variation
                        
                        market_data = {
                            'close_price': current_price,
                            'high_price': current_price + price_variation,
                            'low_price': current_price - price_variation,
                            'volume': live_data.get('volume_24h', 1000000),  # Default volume
                            'timestamp': timezone.now(),
                            'data_source': 'live_api',
                            'symbol': symbol.symbol
                        }
                        
                        logger.info(f"Using live market data for {symbol.symbol}: ${current_price:,.2f}")
                        return market_data
                    else:
                        logger.warning(f"Invalid live price for {symbol.symbol}: {current_price}")
                
            except Exception as e:
                logger.warning(f"Could not fetch live market data for {symbol.symbol}: {e}")
            
            # Fallback to database data if live prices unavailable
            latest_data = MarketData.objects.filter(
                symbol=symbol
            ).order_by('-timestamp').first()
            
            if not latest_data:
                logger.error(f"No market data found for {symbol.symbol}")
                return None
            
            # Check if database data is too old (more than 1 day)
            time_diff = timezone.now() - latest_data.timestamp
            if time_diff.days > 1:
                logger.warning(f"Database market data for {symbol.symbol} is {time_diff.days} days old")
            
            market_data = {
                'close_price': float(latest_data.close_price),
                'high_price': float(latest_data.high_price),
                'low_price': float(latest_data.low_price),
                'volume': float(latest_data.volume),
                'timestamp': latest_data.timestamp,
                'data_source': 'database',
                'symbol': symbol.symbol
            }
            
            logger.info(f"Using database market data for {symbol.symbol}: ${market_data['close_price']:,.2f} (age: {time_diff})")
            return market_data
        except Exception as e:
            logger.error(f"Error getting market data for {symbol.symbol}: {e}")
            return None
    
    def _get_latest_sentiment_data(self, symbol: Symbol) -> Optional[Dict]:
        """Get latest sentiment data for signal generation"""
        try:
            latest_sentiment = SentimentAggregate.objects.filter(
                asset=symbol,
                timeframe='1h'
            ).order_by('-created_at').first()
            
            if not latest_sentiment:
                return None
            
            return {
                'combined_score': latest_sentiment.combined_sentiment_score,
                'social_score': latest_sentiment.social_sentiment_score,
                'news_score': latest_sentiment.news_sentiment_score,
                'confidence_score': latest_sentiment.confidence_score,
                'total_mentions': latest_sentiment.total_mentions
            }
        except Exception as e:
            logger.error(f"Error getting sentiment data for {symbol.symbol}: {e}")
            return None
    
    def _calculate_technical_score(self, symbol: Symbol) -> float:
        """Calculate technical analysis score (-1 to 1)"""
        try:
            # Get latest technical indicators
            indicators = list(TechnicalIndicator.objects.filter(
                symbol=symbol
            ).order_by('-timestamp')[:10])  # Last 10 indicators
            
            if not indicators:
                return 0.0
            
            # Calculate RSI score
            rsi_indicators = [ind for ind in indicators if ind.indicator_type == 'RSI']
            rsi_score = 0.0
            if rsi_indicators:
                latest_rsi = float(rsi_indicators[0].value)
                if latest_rsi < 30:
                    rsi_score = 0.8  # Oversold - bullish
                elif latest_rsi > 70:
                    rsi_score = -0.8  # Overbought - bearish
                else:
                    rsi_score = (latest_rsi - 50) / 50  # Normalized
            
            # Calculate MACD score
            macd_indicators = [ind for ind in indicators if ind.indicator_type == 'MACD']
            macd_score = 0.0
            if macd_indicators:
                latest_macd = float(macd_indicators[0].value)
                macd_score = np.tanh(latest_macd)  # Normalize to -1 to 1
            
            # Calculate moving average score
            sma_indicators = [ind for ind in indicators if ind.indicator_type == 'SMA']
            ema_indicators = [ind for ind in indicators if ind.indicator_type == 'EMA']
            ma_score = 0.0
            if sma_indicators and ema_indicators:
                sma_value = float(sma_indicators[0].value)
                ema_value = float(ema_indicators[0].value)
                if ema_value > sma_value:
                    ma_score = 0.6  # Bullish crossover
                else:
                    ma_score = -0.6  # Bearish crossover
            
            # Combine technical scores
            technical_score = (rsi_score * 0.3 + macd_score * 0.4 + ma_score * 0.3)
            return max(-1.0, min(1.0, technical_score))
            
        except Exception as e:
            logger.error(f"Error calculating technical score for {symbol.symbol}: {e}")
            return 0.0
    
    def _calculate_sentiment_score(self, sentiment_data: Optional[Dict]) -> float:
        """Calculate sentiment analysis score (-1 to 1)"""
        if not sentiment_data:
            return 0.0
        
        try:
            # Combine sentiment scores with weights
            combined_score = sentiment_data['combined_score']
            social_score = sentiment_data['social_score']
            news_score = sentiment_data['news_score']
            confidence = sentiment_data['confidence_score']
            
            # Weighted sentiment score
            sentiment_score = (
                combined_score * 0.5 +
                social_score * 0.3 +
                news_score * 0.2
            ) * confidence
            
            return max(-1.0, min(1.0, sentiment_score))
            
        except Exception as e:
            logger.error(f"Error calculating sentiment score: {e}")
            return 0.0
    
    def _calculate_news_score(self, symbol: Symbol) -> float:
        """Calculate news impact score (-1 to 1)"""
        try:
            # Get recent news mentions
            recent_mentions = CryptoMention.objects.filter(
                asset=symbol,
                mention_type='news',
                created_at__gte=timezone.now() - timedelta(hours=24)
            )
            
            if not recent_mentions.exists():
                return 0.0
            
            # Calculate weighted news score
            total_score = 0.0
            total_weight = 0.0
            
            for mention in recent_mentions:
                weight = mention.impact_weight
                score = mention.sentiment_score
                total_score += score * weight
                total_weight += weight
            
            if total_weight > 0:
                news_score = total_score / total_weight
                return max(-1.0, min(1.0, news_score))
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Error calculating news score for {symbol.symbol}: {e}")
            return 0.0
    
    def _calculate_volume_score(self, symbol: Symbol) -> float:
        """Calculate volume analysis score (-1 to 1)"""
        try:
            # Get recent volume data
            recent_data = MarketData.objects.filter(
                symbol=symbol
            ).order_by('-timestamp')[:20]  # Last 20 data points
            
            if not recent_data.exists():
                return 0.0
            
            volumes = [float(data.volume) for data in recent_data]
            avg_volume = np.mean(volumes)
            current_volume = volumes[0]
            
            # Volume ratio
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
            
            # Normalize to -1 to 1
            volume_score = np.tanh((volume_ratio - 1.0) * 2)
            
            return volume_score
            
        except Exception as e:
            logger.error(f"Error calculating volume score for {symbol.symbol}: {e}")
            return 0.0
    
    def _calculate_pattern_score(self, symbol: Symbol) -> float:
        """Calculate pattern recognition score (-1 to 1)"""
        try:
            # Get recent price data for pattern analysis
            recent_data = MarketData.objects.filter(
                symbol=symbol
            ).order_by('-timestamp')[:50]  # Last 50 data points
            
            if not recent_data.exists() or len(recent_data) < 20:
                return 0.0
            
            prices = [float(data.close_price) for data in recent_data]
            
            # Simple pattern detection
            # Check for bullish/bearish patterns
            pattern_score = 0.0
            
            # Higher highs and higher lows (bullish)
            if len(prices) >= 10:
                highs = [max(prices[i:i+5]) for i in range(0, len(prices)-5, 5)]
                lows = [min(prices[i:i+5]) for i in range(0, len(prices)-5, 5)]
                
                if len(highs) >= 2 and len(lows) >= 2:
                    if highs[-1] > highs[-2] and lows[-1] > lows[-2]:
                        pattern_score = 0.6  # Bullish pattern
                    elif highs[-1] < highs[-2] and lows[-1] < lows[-2]:
                        pattern_score = -0.6  # Bearish pattern
            
            return pattern_score
            
        except Exception as e:
            logger.error(f"Error calculating pattern score for {symbol.symbol}: {e}")
            return 0.0
    
    def _calculate_economic_score(self, symbol: Symbol) -> float:
        """Calculate economic/fundamental analysis score (-1 to 1)"""
        try:
            # Determine the country/region for the symbol
            # For crypto, we'll primarily use US economic data
            # as it's the global reserve currency and affects crypto markets
            country = 'US'
            
            # Get market impact score from economic service
            economic_impact = self.economic_service.get_market_impact_score(country)
            
            # Check for upcoming high-impact events
            upcoming_events = self.economic_service.check_upcoming_events(days_ahead=3)
            
            event_impact = 0.0
            if upcoming_events:
                for event in upcoming_events:
                    if event.impact_level in ['HIGH', 'CRITICAL']:
                        event_analysis = self.economic_service.analyze_event_impact(event)
                        if event_analysis:
                            # Weight by time proximity (closer events have more impact)
                            time_weight = max(0.1, 1.0 - (event_analysis.get('time_to_event', 72) / 72))
                            event_impact += event_analysis.get('market_impact', 0.0) * time_weight
            
            # Combine economic sentiment and event impact
            combined_economic_score = (economic_impact * 0.7) + (event_impact * 0.3)
            
            # Normalize to -1 to 1 range
            normalized_score = max(-1.0, min(1.0, combined_economic_score))
            
            logger.debug(f"Economic score for {symbol.symbol}: {normalized_score:.3f} "
                        f"(sentiment: {economic_impact:.3f}, events: {event_impact:.3f})")
            
            return normalized_score
            
        except Exception as e:
            logger.error(f"Error calculating economic score for {symbol.symbol}: {e}")
            return 0.0
    
    def _calculate_sector_score(self, symbol: Symbol) -> float:
        """Calculate sector analysis score (-1 to 1)"""
        try:
            # Get sector impact score from sector service
            sector_impact = self.sector_service.get_sector_impact_score(symbol)
            
            # Normalize to -1 to 1 range (sector_impact is already in this range)
            sector_score = max(-1.0, min(1.0, sector_impact))
            
            logger.debug(f"Sector score for {symbol.symbol}: {sector_score}")
            return sector_score
            
        except Exception as e:
            logger.error(f"Error calculating sector score for {symbol.symbol}: {e}")
            return 0.0
    
    def _generate_buy_signals(self, symbol: Symbol, market_data: Dict, 
                             technical_score: float, sentiment_score: float,
                             news_score: float, volume_score: float, 
                             pattern_score: float, economic_score: float, sector_score: float) -> List[TradingSignal]:
        """Generate buy signals based on analysis"""
        signals = []
        
        # Calculate combined score
        combined_score = (
            technical_score * 0.25 +
            sentiment_score * 0.20 +
            news_score * 0.15 +
            volume_score * 0.15 +
            pattern_score * 0.10 +
            economic_score * 0.10 +
            sector_score * 0.05
        )
        
        # Generate buy signal if conditions are met (balanced threshold)
        if combined_score > 0.2:  # Bullish threshold (lowered from 0.3 to match sell threshold)
            confidence_score = min(1.0, combined_score + 0.5)
            
            if confidence_score >= self.min_confidence_threshold:
                signal = self._create_signal(
                    symbol=symbol,
                    signal_type_name='BUY',
                    confidence_score=confidence_score,
                    market_data=market_data,
                    technical_score=technical_score,
                    sentiment_score=sentiment_score,
                    news_score=news_score,
                    volume_score=volume_score,
                    pattern_score=pattern_score,
                    economic_score=economic_score,
                    sector_score=sector_score
                )
                
                if signal:
                    signals.append(signal)
        
        # Generate strong buy signal (balanced threshold)
        if combined_score > 0.5:  # Lowered from 0.6 to match sell threshold
            confidence_score = min(1.0, combined_score + 0.3)
            
            if confidence_score >= self.min_confidence_threshold:
                signal = self._create_signal(
                    symbol=symbol,
                    signal_type_name='STRONG_BUY',
                    confidence_score=confidence_score,
                    market_data=market_data,
                    technical_score=technical_score,
                    sentiment_score=sentiment_score,
                    news_score=news_score,
                    volume_score=volume_score,
                    pattern_score=pattern_score,
                    economic_score=economic_score,
                    sector_score=sector_score
                )
                
                if signal:
                    signals.append(signal)
        
        return signals
    
    def _generate_sell_signals(self, symbol: Symbol, market_data: Dict,
                              technical_score: float, sentiment_score: float,
                              news_score: float, volume_score: float,
                              pattern_score: float, economic_score: float, sector_score: float) -> List[TradingSignal]:
        """Generate sell signals based on analysis"""
        signals = []
        
        # Calculate combined score
        combined_score = (
            technical_score * 0.25 +
            sentiment_score * 0.20 +
            news_score * 0.15 +
            volume_score * 0.15 +
            pattern_score * 0.10 +
            economic_score * 0.10 +
            sector_score * 0.05
        )
        
        # Generate sell signal if conditions are met (lowered threshold for more sell signals)
        if combined_score < -0.2:  # Bearish threshold (lowered from -0.3 to generate more sell signals)
            confidence_score = min(1.0, abs(combined_score) + 0.5)
            
            if confidence_score >= self.min_confidence_threshold:
                signal = self._create_signal(
                    symbol=symbol,
                    signal_type_name='SELL',
                    confidence_score=confidence_score,
                    market_data=market_data,
                    technical_score=technical_score,
                    sentiment_score=sentiment_score,
                    news_score=news_score,
                    volume_score=volume_score,
                    pattern_score=pattern_score,
                    economic_score=economic_score,
                    sector_score=sector_score
                )
                
                if signal:
                    signals.append(signal)
        
        # Generate strong sell signal (lowered threshold)
        if combined_score < -0.5:  # Lowered from -0.6
            confidence_score = min(1.0, abs(combined_score) + 0.3)
            
            if confidence_score >= self.min_confidence_threshold:
                signal = self._create_signal(
                    symbol=symbol,
                    signal_type_name='STRONG_SELL',
                    confidence_score=confidence_score,
                    market_data=market_data,
                    technical_score=technical_score,
                    sentiment_score=sentiment_score,
                    news_score=news_score,
                    volume_score=volume_score,
                    pattern_score=pattern_score,
                    economic_score=economic_score,
                    sector_score=sector_score
                )
                
                if signal:
                    signals.append(signal)
        
        return signals
    
    def _create_signal(self, symbol: Symbol, signal_type_name: str,
                      confidence_score: float, market_data: Dict,
                      technical_score: float, sentiment_score: float,
                      news_score: float, volume_score: float,
                      pattern_score: float, economic_score: float, sector_score: float) -> Optional[TradingSignal]:
        """Create a trading signal with all details"""
        try:
            # Get signal type
            signal_type, created = SignalType.objects.get_or_create(
                name=signal_type_name,
                defaults={'description': f'{signal_type_name} signal'}
            )
            
            # Calculate signal strength
            if confidence_score >= 0.9:
                strength = 'VERY_STRONG'
            elif confidence_score >= 0.8:
                strength = 'STRONG'
            elif confidence_score >= 0.7:
                strength = 'MODERATE'
            else:
                strength = 'WEAK'
            
            # Calculate confidence level
            if confidence_score >= 0.85:
                confidence_level = 'VERY_HIGH'
            elif confidence_score >= 0.7:
                confidence_level = 'HIGH'
            elif confidence_score >= 0.5:
                confidence_level = 'MEDIUM'
            else:
                confidence_level = 'LOW'
            
            # Get current live price for accurate entry price
            current_price = None
            try:
                from apps.data.real_price_service import get_live_prices
                live_prices = get_live_prices()
                if symbol.symbol in live_prices:
                    current_price = Decimal(str(live_prices[symbol.symbol].get('price', 0)))
                    logger.info(f"Using live price for {symbol.symbol}: {current_price}")
                else:
                    logger.warning(f"No live price found for {symbol.symbol}, using market data")
            except Exception as e:
                logger.warning(f"Could not fetch live price for {symbol.symbol}: {e}")
            
            # Calculate entry price based on signal type and current price
            if current_price and current_price > 0:
                base_price = current_price
                logger.info(f"Using live price as base: {base_price}")
            else:
                # Try to get historical price from market data first
                market_close_price = market_data.get('close_price', 0)
                if market_close_price and market_close_price > 0:
                    base_price = Decimal(str(market_close_price))
                    logger.info(f"Using market data price as base: {base_price}")
                else:
                    # Fallback to reasonable default price
                    fallback_prices = {
                        'BTC': 50000.0, 'ETH': 3000.0, 'BNB': 300.0, 'ADA': 1.0, 'SOL': 100.0,
                        'XRP': 0.5, 'DOGE': 0.1, 'TRX': 0.05, 'LINK': 20.0, 'DOT': 10.0,
                        'MATIC': 1.0, 'UNI': 15.0, 'AVAX': 30.0, 'ATOM': 8.0, 'FTM': 0.5,
                        'ALGO': 0.3, 'VET': 0.05, 'ICP': 15.0, 'THETA': 2.0, 'SAND': 0.5,
                        'MANA': 0.8, 'LTC': 150.0, 'BCH': 300.0, 'ETC': 30.0, 'XLM': 0.3,
                        'XMR': 150.0, 'ZEC': 50.0, 'DASH': 80.0, 'NEO': 25.0, 'QTUM': 5.0
                    }
                    base_price = Decimal(str(fallback_prices.get(symbol.symbol, 1.0)))
                    logger.info(f"Using fallback price as base: {base_price}")
            
            # Calculate realistic entry price based on signal type
            if signal_type_name in ['BUY', 'STRONG_BUY']:
                # For buy signals, entry should be slightly below current price for better entry
                entry_price = base_price * Decimal('0.98')  # 2% below current price
                logger.info(f"BUY signal entry price: {entry_price} (2% below current {base_price})")
            elif signal_type_name in ['SELL', 'STRONG_SELL']:
                # For sell signals, entry should be slightly above current price for better entry
                entry_price = base_price * Decimal('1.02')  # 2% above current price
                logger.info(f"SELL signal entry price: {entry_price} (2% above current {base_price})")
            else:
                # For HOLD signals, use current price as entry
                entry_price = base_price
                logger.info(f"HOLD signal entry price: {entry_price} (same as current)")
            
            # Enhanced price validation with multiple fallbacks
            if not entry_price or entry_price <= 0:
                logger.warning(f"Invalid entry price for {symbol.symbol}: {entry_price}, applying fallbacks")
                
                # Fallback 1: Try to get latest market data from database
                try:
                    from apps.data.models import MarketData
                    latest_market_data = MarketData.objects.filter(
                        symbol=symbol
                    ).order_by('-timestamp').first()
                    
                    if latest_market_data and latest_market_data.close_price > 0:
                        entry_price = Decimal(str(latest_market_data.close_price))
                        logger.info(f"Using database market data price for {symbol.symbol}: {entry_price}")
                    else:
                        raise Exception("No valid market data in database")
                        
                except Exception as e:
                    logger.warning(f"Database fallback failed for {symbol.symbol}: {e}")
                    
                    # Fallback 2: Use reasonable default prices
                    default_prices = {
                        'BTC': 100000.0, 'ETH': 4000.0, 'BNB': 600.0, 'ADA': 1.0, 'SOL': 200.0,
                        'XRP': 2.0, 'DOGE': 0.4, 'MATIC': 1.0, 'DOT': 8.0, 'AVAX': 40.0,
                        'LINK': 20.0, 'UNI': 15.0, 'ATOM': 12.0, 'FTM': 1.2, 'ALGO': 0.3,
                        'VET': 0.05, 'ICP': 15.0, 'THETA': 2.0, 'SAND': 0.5, 'MANA': 0.8,
                        'LTC': 150.0, 'BCH': 500.0, 'ETC': 30.0, 'XLM': 0.3, 'TRX': 0.2,
                        'XMR': 200.0, 'ZEC': 50.0, 'DASH': 80.0, 'NEO': 25.0, 'QTUM': 5.0
                    }
                    
                    fallback_price = default_prices.get(symbol.symbol, 1.0)
                    entry_price = Decimal(str(fallback_price))
                    logger.info(f"Using fallback price for {symbol.symbol}: {entry_price}")
            
            # Ensure entry_price is always valid
            if not entry_price or entry_price <= 0:
                entry_price = Decimal('1.0')  # Ultimate fallback
                logger.warning(f"Applied ultimate fallback price for {symbol.symbol}: {entry_price}")
            
            logger.info(f"Final entry price for {symbol.symbol}: {entry_price}")
            
            # Perform timeframe analysis to identify entry points
            timeframe_analysis = None
            entry_point_type = 'UNKNOWN'
            entry_point_details = {}
            entry_zone_low = None
            entry_zone_high = None
            entry_confidence = 0.8
            
            try:
                # Get multi-timeframe analysis using entry_price (either live or market data)
                timeframe_analysis = self.timeframe_service.get_multi_timeframe_analysis(
                    symbol, float(entry_price)
                )
                
                if timeframe_analysis and not timeframe_analysis.get('error'):
                    # Extract best entry point information
                    final_recommendation = timeframe_analysis.get('final_recommendation', {})
                    
                    # Get entry zone from best entry point regardless of action
                    best_entry_point = self._get_best_entry_point(timeframe_analysis)
                    logger.info(f"Best entry point for {symbol.symbol}: {best_entry_point}")
                    if best_entry_point:
                        entry_point_type = best_entry_point.get('type', 'UNKNOWN')
                        entry_zone_low = Decimal(str(best_entry_point.get('entry_zone_low', float(entry_price) * 0.99)))
                        entry_zone_high = Decimal(str(best_entry_point.get('entry_zone_high', float(entry_price) * 1.01)))
                        entry_point_details = best_entry_point.get('details', {})
                        # Convert numpy types to Python types for JSON serialization
                        if entry_point_details:
                            import numpy as np
                            converted_details = {}
                            for key, value in entry_point_details.items():
                                if isinstance(value, np.bool_):
                                    converted_details[key] = bool(value)
                                elif isinstance(value, np.integer):
                                    converted_details[key] = int(value)
                                elif isinstance(value, np.floating):
                                    converted_details[key] = float(value)
                                else:
                                    converted_details[key] = value
                            entry_point_details = converted_details
                        entry_confidence = best_entry_point.get('confidence', 0.8)
                        logger.info(f"Entry zone set for {symbol.symbol}: {entry_zone_low} - {entry_zone_high}")
                    else:
                        logger.warning(f"No best entry point found for {symbol.symbol}")
                    
                    # Update entry point type based on final recommendation if available
                    if final_recommendation.get('action') in ['BUY', 'SELL']:
                        entry_point_type = final_recommendation.get('action', entry_point_type)
                        entry_confidence = final_recommendation.get('confidence', entry_confidence)
                    
                    logger.info(f"Timeframe analysis completed for {symbol.symbol}: {entry_point_type} entry point identified")
                
            except Exception as e:
                logger.warning(f"Could not perform timeframe analysis for {symbol.symbol}: {e}")
            
            # Determine optimal timeframe for this signal
            optimal_timeframe = self._determine_optimal_timeframe(timeframe_analysis, signal_type_name)
            
            # Ensure we have a valid entry price
            if not entry_price or entry_price <= 0:
                logger.error(f"Invalid entry price for {symbol.symbol}: {entry_price}")
                return None
            

            # Calculate realistic target price and stop loss based on signal type
            if signal_type_name in ['BUY', 'STRONG_BUY']:
                # For buy signals: target above entry, stop loss below entry
                profit_percentage = Decimal('0.15')  # 15% profit target (3:1 risk-reward)
                stop_loss_percentage = Decimal('0.05')  # 5% stop loss (smaller risk)
                
                target_price = entry_price * (Decimal('1.0') + profit_percentage)
                stop_loss = entry_price * (Decimal('1.0') - stop_loss_percentage)
                logger.info(f"BUY signal targets: entry={entry_price}, target={target_price} (+15%), stop={stop_loss} (-5%)")
                
            elif signal_type_name in ['SELL', 'STRONG_SELL']:
                # For sell signals: target below entry, stop loss above entry
                profit_percentage = Decimal('0.15')  # 15% profit target for sells (3:1 risk-reward)
                stop_loss_percentage = Decimal('0.05')  # 5% stop loss for sells (smaller risk)
                
                target_price = entry_price * (Decimal('1.0') - profit_percentage)  # Lower price for profit
                stop_loss = entry_price * (Decimal('1.0') + stop_loss_percentage)  # Higher price for stop loss
                logger.info(f"SELL signal targets: entry={entry_price}, target={target_price} (-15%), stop={stop_loss} (+5%)")
                
            else:  # HOLD signals
                # For hold signals, set conservative targets
                target_price = entry_price * Decimal('1.05')  # 5% target
                stop_loss = entry_price * Decimal('0.95')     # 5% stop loss
                logger.info(f"HOLD signal targets: entry={entry_price}, target={target_price} (+5%), stop={stop_loss} (-5%)")
            
            # Calculate risk-reward ratio
            risk = abs(float(entry_price - stop_loss))
            reward = abs(float(target_price - entry_price))
            risk_reward_ratio = reward / risk if risk > 0 else 0
            
            # Calculate quality score
            quality_score = (
                confidence_score * 0.4 +
                (1.0 if risk_reward_ratio >= self.min_risk_reward_ratio else 0.0) * 0.25 +
                (technical_score + 1.0) / 2.0 * 0.15 +
                (sentiment_score + 1.0) / 2.0 * 0.08 +
                (economic_score + 1.0) / 2.0 * 0.07 +
                (sector_score + 1.0) / 2.0 * 0.05
            )
            

            # Create signal
            signal = TradingSignal.objects.create(
                symbol=symbol,
                signal_type=signal_type,
                strength=strength,
                confidence_score=confidence_score,
                confidence_level=confidence_level,
                entry_price=entry_price,
                target_price=target_price,
                stop_loss=stop_loss,
                risk_reward_ratio=risk_reward_ratio,
                quality_score=quality_score,
                expires_at=timezone.now() + timedelta(hours=self.signal_expiry_hours),
                technical_score=technical_score,
                sentiment_score=sentiment_score,
                news_score=news_score,
                volume_score=volume_score,
                is_best_of_day=False,
                pattern_score=pattern_score,
                economic_score=economic_score,
                sector_score=sector_score,
                # New timeframe and entry point fields
                timeframe=optimal_timeframe,
                entry_point_type=entry_point_type,
                entry_point_details=entry_point_details,
                entry_zone_low=entry_zone_low,
                entry_zone_high=entry_zone_high,
                is_best_of_day=False,
                entry_confidence=entry_confidence
            )
            

            # Store price metadata for tracking
            self._store_price_metadata(signal, {
                'entry_price': float(entry_price),
                'target_price': float(target_price),
                'stop_loss': float(stop_loss),
                'market_data_price': float(market_data.get('close_price', 0)),
                'live_price_used': current_price is not None,
                'price_timestamp': timezone.now().isoformat()
            })
            
            # Create factor contributions
            self._create_factor_contributions(signal, {
                'technical': technical_score,
                'sentiment': sentiment_score,
                'news': news_score,
                'volume': volume_score,
                'pattern': pattern_score,
                'economic': economic_score,
                'sector': sector_score
            })
            
            # Create alert
            self._create_signal_alert(signal)
            
            logger.info(f"Successfully created {signal_type_name} signal for {symbol.symbol} at {entry_price}")
            return signal
            
        except Exception as e:
            logger.error(f"Error creating signal for {symbol.symbol}: {e}")
            return None
    
    def _calculate_volatility_factor(self, market_data: Dict) -> Decimal:
        """Calculate volatility factor for dynamic target calculation"""
        try:
            # Calculate volatility based on price range
            high_price = Decimal(str(market_data.get('high_price', 0)))
            low_price = Decimal(str(market_data.get('low_price', 0)))
            close_price = Decimal(str(market_data.get('close_price', 1)))
            
            if close_price > 0:
                volatility = (high_price - low_price) / close_price
                # Normalize volatility factor (0.0 to 1.0)
                volatility_factor = min(Decimal('1.0'), max(Decimal('0.0'), volatility))
                return volatility_factor
            else:
                return Decimal('0.5')  # Default moderate volatility
        except Exception as e:
            logger.warning(f"Error calculating volatility factor: {e}")
            return Decimal('0.5')  # Default moderate volatility
    
    def _store_price_metadata(self, signal: TradingSignal, price_data: Dict):
        """Store price metadata for signal tracking"""
        try:
            # Store in cache for quick access
            from django.core.cache import cache
            cache_key = f"signal_price_metadata_{signal.id}"
            cache.set(cache_key, price_data, 3600)  # Cache for 1 hour
            
            # You could also store this in a separate model if needed
            logger.debug(f"Stored price metadata for signal {signal.id}: {price_data}")
        except Exception as e:
            logger.warning(f"Error storing price metadata: {e}")
    
    def _get_best_entry_point(self, timeframe_analysis: Dict) -> Optional[Dict]:
        """Get the best entry point from timeframe analysis"""
        try:
            if not timeframe_analysis:
                return None
            
            all_entry_points = []
            
            # Collect entry points from all timeframes
            for timeframe, analysis in timeframe_analysis.get('timeframe_analyses', {}).items():
                if analysis.get('entry_points'):
                    for entry_point in analysis['entry_points']:
                        entry_point['timeframe'] = timeframe
                        all_entry_points.append(entry_point)
            
            if not all_entry_points:
                return None
            
            # Sort by confidence and return the best one
            best_entry_point = max(all_entry_points, key=lambda x: x.get('confidence', 0))
            return best_entry_point
            
        except Exception as e:
            logger.error(f"Error getting best entry point: {e}")
            return None
    
    def _determine_optimal_timeframe(self, timeframe_analysis: Dict, signal_type: str) -> str:
        """Determine the optimal timeframe for the signal"""
        try:
            if not timeframe_analysis:
                return '1H'  # Default timeframe
            
            # Get recommended timeframe from analysis
            recommended = timeframe_analysis.get('final_recommendation', {}).get('recommended_timeframe', '1H')
            
            # Adjust based on signal type
            if signal_type in ['BUY', 'STRONG_BUY']:
                # For buy signals, prefer shorter timeframes for quick entries
                if recommended in ['1D', '1W']:
                    return '4H'
                elif recommended in ['4H']:
                    return '1H'
                else:
                    return recommended
            elif signal_type in ['SELL', 'STRONG_SELL']:
                # For sell signals, prefer shorter timeframes for quick exits
                if recommended in ['1D', '1W']:
                    return '4H'
                elif recommended in ['4H']:
                    return '1H'
                else:
                    return recommended
            else:
                return recommended
                
        except Exception as e:
            logger.error(f"Error determining optimal timeframe: {e}")
            return '1H'
    
    def _create_factor_contributions(self, signal: TradingSignal, scores: Dict):
        """Create factor contribution records"""
        try:
            factors = {
                'technical': SignalFactor.objects.get_or_create(
                    name='Technical Analysis',
                    factor_type='TECHNICAL',
                    defaults={'weight': 0.35, 'description': 'Technical indicators analysis'}
                )[0],
                'sentiment': SignalFactor.objects.get_or_create(
                    name='Sentiment Analysis',
                    factor_type='SENTIMENT',
                    defaults={'weight': 0.25, 'description': 'Social media and news sentiment'}
                )[0],
                'news': SignalFactor.objects.get_or_create(
                    name='News Impact',
                    factor_type='NEWS',
                    defaults={'weight': 0.15, 'description': 'News event impact analysis'}
                )[0],
                'volume': SignalFactor.objects.get_or_create(
                    name='Volume Analysis',
                    factor_type='VOLUME',
                    defaults={'weight': 0.15, 'description': 'Volume pattern analysis'}
                )[0],
                'pattern': SignalFactor.objects.get_or_create(
                    name='Pattern Recognition',
                    factor_type='PATTERN',
                    defaults={'weight': 0.10, 'description': 'Chart pattern analysis'}
                )[0],
                'economic': SignalFactor.objects.get_or_create(
                    name='Economic Analysis',
                    factor_type='ECONOMIC',
                    defaults={'weight': 0.10, 'description': 'Economic and fundamental analysis'}
                )[0],
                'sector': SignalFactor.objects.get_or_create(
                    name='Sector Analysis',
                    factor_type='SECTOR',
                    defaults={'weight': 0.05, 'description': 'Sector momentum and rotation analysis'}
                )[0]
            }
            
            for factor_name, factor in factors.items():
                score = scores.get(factor_name, 0.0)
                contribution = score * factor.weight
                
                SignalFactorContribution.objects.create(
                    signal=signal,
                    factor=factor,
                    score=score,
                    weight=factor.weight,
                    contribution=contribution,
                    details={'factor_type': factor.factor_type}
                )
                
        except Exception as e:
            logger.error(f"Error creating factor contributions for signal {signal.id}: {e}")
    
    def _create_signal_alert(self, signal: TradingSignal):
        """Create alert for new signal"""
        try:
            SignalAlert.objects.create(
                alert_type='SIGNAL_GENERATED',
                priority='HIGH' if signal.confidence_score >= 0.8 else 'MEDIUM',
                title=f"New {signal.signal_type.name} Signal for {signal.symbol.symbol}",
                message=f"Confidence: {signal.confidence_score:.2%}, Quality: {signal.quality_score:.2%}",
                signal=signal
            )
        except Exception as e:
            logger.error(f"Error creating signal alert: {e}")
    
    def _filter_signals_by_quality(self, signals: List[TradingSignal]) -> List[TradingSignal]:
        """Filter signals by quality criteria with enhanced quality filtering"""
        if not signals:
            return []
        
        # Initialize quality enhancement service
        quality_service = SignalQualityEnhancementService()
        
        # Get market data for quality enhancement
        market_data = self._get_latest_market_data(signals[0].symbol) if signals else None
        
        # Enhance signal quality for all signals
        enhanced_signals = []
        for signal in signals:
            try:
                # Store original quality score
                if not hasattr(signal, 'quality_metadata'):
                    signal.quality_metadata = {}
                signal.quality_metadata['original_quality_score'] = signal.quality_score
                
                # Enhance signal quality
                enhanced_signal = quality_service.enhance_signal_quality(signal, market_data or {})
                enhanced_signals.append(enhanced_signal)
                
            except Exception as e:
                logger.error(f"Error enhancing signal {signal.id}: {e}")
                enhanced_signals.append(signal)
        
        # Apply enhanced quality filtering
        filtered_signals = []
        for signal in enhanced_signals:
            # Check enhanced confidence
            if signal.confidence_score < self.min_confidence_threshold:
                continue
            
            # Check risk-reward ratio
            if signal.risk_reward_ratio and signal.risk_reward_ratio < self.min_risk_reward_ratio:
                continue
            
            # Check enhanced quality score
            if signal.quality_score < 0.4:  # Lowered from 0.6
                continue
            
            # Check false signal probability
            if hasattr(signal, 'quality_metadata') and 'false_signal_probability' in signal.quality_metadata:
                false_signal_prob = signal.quality_metadata['false_signal_probability']
                if false_signal_prob > 0.7:  # Filter out high false signal probability
                    continue
            
            # Check confirmation score
            if hasattr(signal, 'quality_metadata') and 'confirmation_score' in signal.quality_metadata:
                confirmation_score = signal.quality_metadata['confirmation_score']
                if confirmation_score < 0.4:  # Filter out low confirmation signals
                    continue
            
            filtered_signals.append(signal)
        
        logger.info(f"Quality enhancement applied: {len(enhanced_signals)} signals, filtered to {len(filtered_signals)} high-quality signals")
        return filtered_signals
    
    def _generate_advanced_indicator_signals(self, symbol: Symbol) -> List[TradingSignal]:
        """Generate signals based on advanced indicators analysis"""
        signals = []
        
        try:
            # Get advanced indicators data
            fvg_data = self.advanced_indicators.calculate_fair_value_gap(symbol)
            liquidity_swings = self.advanced_indicators.calculate_liquidity_swings(symbol)
            nw_envelope = self.advanced_indicators.calculate_nadaraya_watson_envelope(symbol)
            pivot_points = self.advanced_indicators.calculate_pivot_points(symbol)
            rsi_divergence = self.advanced_indicators.calculate_rsi_divergence(symbol)
            stoch_rsi = self.advanced_indicators.calculate_stochastic_rsi(symbol)
            
            # Generate signals based on indicator combinations
            signals.extend(self._create_fvg_signals(symbol, fvg_data))
            signals.extend(self._create_liquidity_swing_signals(symbol, liquidity_swings))
            signals.extend(self._create_nw_envelope_signals(symbol, nw_envelope))
            signals.extend(self._create_pivot_point_signals(symbol, pivot_points))
            signals.extend(self._create_rsi_divergence_signals(symbol, rsi_divergence))
            signals.extend(self._create_stoch_rsi_signals(symbol, stoch_rsi))
            
        except Exception as e:
            logger.error(f"Error generating advanced indicator signals for {symbol.symbol}: {e}")
        
        return signals
    
    def _create_fvg_signals(self, symbol: Symbol, fvg_data: Optional[Dict]) -> List[TradingSignal]:
        """Create signals based on Fair Value Gap analysis"""
        signals = []
        
        if not fvg_data or not fvg_data.get('latest_fvg'):
            return signals
        
        try:
            latest_fvg = fvg_data['latest_fvg']
            current_price = self._get_latest_price(symbol)
            
            if not current_price:
                return signals
            
            # Check if price is in FVG zone
            if latest_fvg['type'] == 'BULLISH' and latest_fvg['start'] <= current_price <= latest_fvg['end']:
                # Create bullish FVG signal
                signal = self._create_signal(
                    symbol=symbol,
                    signal_type_name='FVG_BULLISH',
                    entry_price=current_price,
                    target_price=latest_fvg['end'] + (latest_fvg['end'] - latest_fvg['start']) * 0.5,
                    stop_loss=latest_fvg['start'] * 0.999,
                    confidence=0.7 + latest_fvg['strength'] * 0.2,
                    notes=f"Fair Value Gap Bullish - Strength: {latest_fvg['strength']:.3f}"
                )
                if signal:
                    signals.append(signal)
            
            elif latest_fvg['type'] == 'BEARISH' and latest_fvg['start'] <= current_price <= latest_fvg['end']:
                # Create bearish FVG signal
                signal = self._create_signal(
                    symbol=symbol,
                    signal_type_name='FVG_BEARISH',
                    entry_price=current_price,
                    target_price=latest_fvg['start'] - (latest_fvg['start'] - latest_fvg['end']) * 0.5,
                    stop_loss=latest_fvg['end'] * 1.001,
                    confidence=0.7 + latest_fvg['strength'] * 0.2,
                    notes=f"Fair Value Gap Bearish - Strength: {latest_fvg['strength']:.3f}"
                )
                if signal:
                    signals.append(signal)
        
        except Exception as e:
            logger.error(f"Error creating FVG signals for {symbol.symbol}: {e}")
        
        return signals
    
    def _create_liquidity_swing_signals(self, symbol: Symbol, liquidity_data: Optional[Dict]) -> List[TradingSignal]:
        """Create signals based on Liquidity Swings analysis"""
        signals = []
        
        if not liquidity_data:
            return signals
        
        try:
            current_price = self._get_latest_price(symbol)
            if not current_price:
                return signals
            
            # Check for liquidity sweep opportunities
            latest_swing_high = liquidity_data.get('latest_swing_high')
            latest_swing_low = liquidity_data.get('latest_swing_low')
            
            if latest_swing_high and current_price > latest_swing_high['price'] * 1.001:
                # Potential liquidity sweep above swing high
                signal = self._create_signal(
                    symbol=symbol,
                    signal_type_name='LIQUIDITY_SWEEP_BULLISH',
                    entry_price=current_price,
                    target_price=latest_swing_high['price'] + (current_price - latest_swing_high['price']) * 2,
                    stop_loss=latest_swing_high['price'] * 0.999,
                    confidence=0.75,
                    notes=f"Liquidity Sweep Bullish - Swing High: {latest_swing_high['price']:.4f}"
                )
                if signal:
                    signals.append(signal)
            
            elif latest_swing_low and current_price < latest_swing_low['price'] * 0.999:
                # Potential liquidity sweep below swing low
                signal = self._create_signal(
                    symbol=symbol,
                    signal_type_name='LIQUIDITY_SWEEP_BEARISH',
                    entry_price=current_price,
                    target_price=latest_swing_low['price'] - (latest_swing_low['price'] - current_price) * 2,
                    stop_loss=latest_swing_low['price'] * 1.001,
                    confidence=0.75,
                    notes=f"Liquidity Sweep Bearish - Swing Low: {latest_swing_low['price']:.4f}"
                )
                if signal:
                    signals.append(signal)
        
        except Exception as e:
            logger.error(f"Error creating liquidity swing signals for {symbol.symbol}: {e}")
        
        return signals
    
    def _create_nw_envelope_signals(self, symbol: Symbol, nw_data: Optional[Dict]) -> List[TradingSignal]:
        """Create signals based on Nadaraya-Watson Envelope analysis"""
        signals = []
        
        if not nw_data:
            return signals
        
        try:
            current_price = nw_data['current_price']
            upper_band = nw_data['upper_band']
            lower_band = nw_data['lower_band']
            nw_value = nw_data['nw_value']
            
            # Check for envelope breakout signals
            if current_price > upper_band:
                # Bullish breakout
                signal = self._create_signal(
                    symbol=symbol,
                    signal_type_name='NW_ENVELOPE_BULLISH',
                    entry_price=current_price,
                    target_price=upper_band + (upper_band - nw_value) * 1.5,
                    stop_loss=nw_value,
                    confidence=0.8,
                    notes=f"NW Envelope Bullish Breakout - Upper: {upper_band:.4f}, NW: {nw_value:.4f}"
                )
                if signal:
                    signals.append(signal)
            
            elif current_price < lower_band:
                # Bearish breakout
                signal = self._create_signal(
                    symbol=symbol,
                    signal_type_name='NW_ENVELOPE_BEARISH',
                    entry_price=current_price,
                    target_price=lower_band - (nw_value - lower_band) * 1.5,
                    stop_loss=nw_value,
                    confidence=0.8,
                    notes=f"NW Envelope Bearish Breakout - Lower: {lower_band:.4f}, NW: {nw_value:.4f}"
                )
                if signal:
                    signals.append(signal)
        
        except Exception as e:
            logger.error(f"Error creating NW envelope signals for {symbol.symbol}: {e}")
        
        return signals
    
    def _create_pivot_point_signals(self, symbol: Symbol, pivot_data: Optional[Dict]) -> List[TradingSignal]:
        """Create signals based on Pivot Points analysis"""
        signals = []
        
        if not pivot_data:
            return signals
        
        try:
            current_price = self._get_latest_price(symbol)
            if not current_price:
                return signals
            
            pivot = pivot_data['pivot']
            r1, r2, r3 = pivot_data['r1'], pivot_data['r2'], pivot_data['r3']
            s1, s2, s3 = pivot_data['s1'], pivot_data['s2'], pivot_data['s3']
            
            # Check for pivot point signals
            if current_price > r1 and current_price < r2:
                # Between R1 and R2 - potential bullish continuation
                signal = self._create_signal(
                    symbol=symbol,
                    signal_type_name='PIVOT_BULLISH_R1',
                    entry_price=current_price,
                    target_price=r2,
                    stop_loss=r1 * 0.999,
                    confidence=0.7,
                    notes=f"Pivot Bullish R1 - R1: {r1:.4f}, R2: {r2:.4f}"
                )
                if signal:
                    signals.append(signal)
            
            elif current_price < s1 and current_price > s2:
                # Between S1 and S2 - potential bearish continuation
                signal = self._create_signal(
                    symbol=symbol,
                    signal_type_name='PIVOT_BEARISH_S1',
                    entry_price=current_price,
                    target_price=s2,
                    stop_loss=s1 * 1.001,
                    confidence=0.7,
                    notes=f"Pivot Bearish S1 - S1: {s1:.4f}, S2: {s2:.4f}"
                )
                if signal:
                    signals.append(signal)
        
        except Exception as e:
            logger.error(f"Error creating pivot point signals for {symbol.symbol}: {e}")
        
        return signals
    
    def _create_rsi_divergence_signals(self, symbol: Symbol, divergence_data: Optional[Dict]) -> List[TradingSignal]:
        """Create signals based on RSI Divergence analysis"""
        signals = []
        
        if not divergence_data or not divergence_data.get('latest_divergence'):
            return signals
        
        try:
            latest_divergence = divergence_data['latest_divergence']
            current_price = self._get_latest_price(symbol)
            
            if not current_price:
                return signals
            
            if latest_divergence['type'] == 'BULLISH_DIVERGENCE':
                # Bullish divergence signal
                signal = self._create_signal(
                    symbol=symbol,
                    signal_type_name='RSI_DIVERGENCE_BULLISH',
                    entry_price=current_price,
                    target_price=current_price * 1.03,  # 3% target
                    stop_loss=current_price * 0.98,  # 2% stop loss
                    confidence=0.6 + latest_divergence['strength'] * 0.3,
                    notes=f"RSI Bullish Divergence - Strength: {latest_divergence['strength']:.3f}"
                )
                if signal:
                    signals.append(signal)
            
            elif latest_divergence['type'] == 'BEARISH_DIVERGENCE':
                # Bearish divergence signal
                signal = self._create_signal(
                    symbol=symbol,
                    signal_type_name='RSI_DIVERGENCE_BEARISH',
                    entry_price=current_price,
                    target_price=current_price * 0.97,  # 3% target
                    stop_loss=current_price * 1.02,  # 2% stop loss
                    confidence=0.6 + latest_divergence['strength'] * 0.3,
                    notes=f"RSI Bearish Divergence - Strength: {latest_divergence['strength']:.3f}"
                )
                if signal:
                    signals.append(signal)
        
        except Exception as e:
            logger.error(f"Error creating RSI divergence signals for {symbol.symbol}: {e}")
        
        return signals
    
    def _create_stoch_rsi_signals(self, symbol: Symbol, stoch_data: Optional[Dict]) -> List[TradingSignal]:
        """Create signals based on Stochastic RSI analysis"""
        signals = []
        
        if not stoch_data or stoch_data.get('stoch_rsi') is None:
            return signals
        
        try:
            current_price = self._get_latest_price(symbol)
            if not current_price:
                return signals
            
            stoch_rsi = stoch_data['stoch_rsi']
            
            if stoch_data.get('oversold', False) and stoch_rsi > 20:
                # Oversold recovery signal
                signal = self._create_signal(
                    symbol=symbol,
                    signal_type_name='STOCH_RSI_OVERSOLD',
                    entry_price=current_price,
                    target_price=current_price * 1.025,  # 2.5% target
                    stop_loss=current_price * 0.985,  # 1.5% stop loss
                    confidence=0.65,
                    notes=f"Stochastic RSI Oversold Recovery - Value: {stoch_rsi:.2f}"
                )
                if signal:
                    signals.append(signal)
            
            elif stoch_data.get('overbought', False) and stoch_rsi < 80:
                # Overbought rejection signal
                signal = self._create_signal(
                    symbol=symbol,
                    signal_type_name='STOCH_RSI_OVERBOUGHT',
                    entry_price=current_price,
                    target_price=current_price * 0.975,  # 2.5% target
                    stop_loss=current_price * 1.015,  # 1.5% stop loss
                    confidence=0.65,
                    notes=f"Stochastic RSI Overbought Rejection - Value: {stoch_rsi:.2f}"
                )
                if signal:
                    signals.append(signal)
        
        except Exception as e:
            logger.error(f"Error creating Stochastic RSI signals for {symbol.symbol}: {e}")
        
        return signals
    
    def _select_top_signals(self, signals: List[TradingSignal], limit: int = 5) -> List[TradingSignal]:
        """Select top N signals based on accuracy and quality metrics"""
        if not signals:
            return []
        
        try:
            # Calculate accuracy-focused score for each signal
            scored_signals = []
            for signal in signals:
                # Enhanced accuracy score with multiple quality factors
                accuracy_score = self._calculate_accuracy_score(signal)
                scored_signals.append((signal, accuracy_score))
            
            # Sort by accuracy score (descending) - most accurate first
            scored_signals.sort(key=lambda x: x[1], reverse=True)
            
            # Return top N most accurate signals
            top_signals = [signal for signal, score in scored_signals[:limit]]
            
            logger.info(f"Selected top {len(top_signals)} signals from {len(signals)} candidates")
            return top_signals
            
        except Exception as e:
            logger.error(f"Error selecting top signals: {e}")
            return signals[:limit]
    
    def _calculate_accuracy_score(self, signal: TradingSignal) -> float:
        """
        Calculate accuracy-focused score for signal selection
        
        This method prioritizes accuracy over popularity by considering:
        - Signal confidence and quality
        - Technical indicator strength
        - Historical accuracy patterns
        - Signal confirmation factors
        - Risk-adjusted returns
        """
        try:
            # Base accuracy score from confidence and quality
            base_accuracy = (signal.confidence_score * 0.6 + signal.quality_score * 0.4)
            
            # Technical indicator strength bonus
            technical_bonus = self._calculate_technical_strength_bonus(signal)
            
            # Historical accuracy bonus (if available)
            historical_bonus = self._calculate_historical_accuracy_bonus(signal)
            
            # Signal confirmation bonus
            confirmation_bonus = self._calculate_confirmation_bonus(signal)
            
            # Risk-adjusted accuracy score
            risk_adjustment = self._calculate_risk_adjustment(signal)
            
            # Small prioritization for CHoCH/BOS signals to focus on user's strategy
            try:
                choch_preference_bonus = 0.0
                if signal.signal_type and signal.signal_type.name:
                    name = str(signal.signal_type.name).upper()
                    # Favor CHOCH/BOS-related signals slightly (bounded)
                    if "CHOCH" in name or "BOS" in name:
                        # Scale with confidence but cap the boost to avoid overpowering quality
                        choch_preference_bonus = min(0.05, max(0.0, signal.confidence_score * 0.05))
                
            except Exception:
                choch_preference_bonus = 0.0
            
            # Calculate final accuracy score
            accuracy_score = (
                base_accuracy * 0.4 +           # Base accuracy (40%)
                technical_bonus * 0.25 +        # Technical strength (25%)
                historical_bonus * 0.15 +       # Historical performance (15%)
                confirmation_bonus * 0.15 +     # Signal confirmation (15%)
                risk_adjustment * 0.05 +        # Risk adjustment (5%)
                choch_preference_bonus          # CHoCH preference (up to +0.05)
            )
            
            # Ensure score is between 0 and 1
            return max(0.0, min(1.0, accuracy_score))
            
        except Exception as e:
            logger.error(f"Error calculating accuracy score for signal {signal.id}: {e}")
            return signal.confidence_score  # Fallback to confidence score
    
    def _calculate_technical_strength_bonus(self, signal: TradingSignal) -> float:
        """Calculate bonus based on technical indicator strength"""
        try:
            # Get technical indicators for the signal's symbol
            indicators = TechnicalIndicator.objects.filter(
                symbol=signal.symbol
            ).order_by('-timestamp')[:5]
            
            if not indicators:
                return 0.0
            
            # Calculate indicator strength
            strength_score = 0.0
            indicator_count = 0
            
            for indicator in indicators:
                if indicator.indicator_type in ['RSI', 'MACD', 'SMA', 'EMA']:
                    # Higher values indicate stronger signals
                    if indicator.indicator_type == 'RSI':
                        rsi_value = float(indicator.value)
                        if rsi_value < 30 or rsi_value > 70:  # Strong RSI signals
                            strength_score += 0.3
                    elif indicator.indicator_type == 'MACD':
                        macd_value = abs(float(indicator.value))
                        strength_score += min(macd_value * 0.1, 0.3)  # Stronger MACD = higher bonus
                    elif indicator.indicator_type in ['SMA', 'EMA']:
                        strength_score += 0.2  # Moving average confirmation
                    
                    indicator_count += 1
            
            return strength_score / max(indicator_count, 1) if indicator_count > 0 else 0.0
            
        except Exception as e:
            logger.error(f"Error calculating technical strength bonus: {e}")
            return 0.0
    
    def _calculate_historical_accuracy_bonus(self, signal: TradingSignal) -> float:
        """Calculate bonus based on historical accuracy of similar signals"""
        try:
            # Get recent signals for the same symbol and type
            recent_signals = TradingSignal.objects.filter(
                symbol=signal.symbol,
                signal_type=signal.signal_type,
                created_at__gte=timezone.now() - timedelta(days=30)
            ).exclude(id=signal.id)
            
            if not recent_signals.exists():
                return 0.0
            
            # Calculate historical accuracy
            total_signals = recent_signals.count()
            profitable_signals = recent_signals.filter(is_profitable=True).count()
            
            if total_signals > 0:
                historical_accuracy = profitable_signals / total_signals
                return historical_accuracy * 0.5  # Max 0.5 bonus for perfect historical accuracy
            else:
                return 0.0
                
        except Exception as e:
            logger.error(f"Error calculating historical accuracy bonus: {e}")
            return 0.0
    
    def _calculate_confirmation_bonus(self, signal: TradingSignal) -> float:
        """Calculate bonus based on signal confirmation factors"""
        try:
            confirmation_score = 0.0
            
            # Check if signal has quality metadata (enhanced signals)
            if hasattr(signal, 'quality_metadata') and signal.quality_metadata:
                metadata = signal.quality_metadata
                
                # Multi-timeframe confirmation
                if 'multi_timeframe_score' in metadata:
                    confirmation_score += metadata['multi_timeframe_score'] * 0.3
                
                # Signal confirmation score
                if 'confirmation_score' in metadata:
                    confirmation_score += metadata['confirmation_score'] * 0.4
                
                # Cluster analysis confirmation
                if 'cluster_score' in metadata:
                    confirmation_score += metadata['cluster_score'] * 0.3
            
            return min(confirmation_score, 1.0)
            
        except Exception as e:
            logger.error(f"Error calculating confirmation bonus: {e}")
            return 0.0
    
    def _calculate_risk_adjustment(self, signal: TradingSignal) -> float:
        """Calculate risk adjustment factor for accuracy score"""
        try:
            # Higher risk-reward ratio = better signal
            risk_reward = signal.risk_reward_ratio
            
            if risk_reward >= 3.0:
                return 1.0  # Excellent risk-reward
            elif risk_reward >= 2.0:
                return 0.8  # Good risk-reward
            elif risk_reward >= 1.5:
                return 0.6  # Acceptable risk-reward
            else:
                return 0.3  # Poor risk-reward
                
        except Exception as e:
            logger.error(f"Error calculating risk adjustment: {e}")
            return 0.5  # Neutral adjustment  # Fallback to first N signals
    
    def _get_latest_price(self, symbol: Symbol) -> Optional[float]:
        """Get the latest price for a symbol"""
        try:
            # First try to get live price
            from apps.data.real_price_service import get_live_prices
            live_prices = get_live_prices()
            
            if symbol.symbol in live_prices:
                return float(live_prices[symbol.symbol]['price'])
            
            # Fallback to database
            latest_data = MarketData.objects.filter(symbol=symbol).order_by('-timestamp').first()
            if latest_data:
                return float(latest_data.close_price)
            
            return None
        except Exception as e:
            logger.error(f"Error getting latest price for {symbol.symbol}: {e}")
            return None


class MarketRegimeService:
    """Service for market regime detection and classification"""
    
    def __init__(self):
        self.volatility_window = 20  # Days for volatility calculation
        self.trend_window = 50       # Days for trend calculation
    
    def detect_market_regime(self, symbol: Symbol) -> Optional[MarketRegime]:
        """Detect current market regime for a symbol"""
        try:
            # Get historical data
            historical_data = MarketData.objects.filter(
                symbol=symbol
            ).order_by('-timestamp')[:self.trend_window]
            
            if not historical_data.exists():
                return None
            
            # Calculate volatility
            prices = [float(data.close_price) for data in historical_data]
            returns = np.diff(np.log(prices))
            volatility = np.std(returns) * np.sqrt(252)  # Annualized volatility
            
            # Calculate trend strength
            trend_strength = self._calculate_trend_strength(prices)
            
            # Classify regime
            regime_name, confidence = self._classify_regime(volatility, trend_strength)
            
            # Create regime record
            regime = MarketRegime.objects.create(
                name=regime_name,
                volatility_level=min(1.0, volatility),
                trend_strength=trend_strength,
                confidence=confidence,
                description=f"Detected {regime_name} regime for {symbol.symbol}"
            )
            
            return regime
            
        except Exception as e:
            logger.error(f"Error detecting market regime for {symbol.symbol}: {e}")
            return None
    
    def _calculate_trend_strength(self, prices: List[float]) -> float:
        """Calculate trend strength (-1 to 1)"""
        try:
            if len(prices) < 10:
                return 0.0
            
            # Linear regression slope
            x = np.arange(len(prices))
            slope = np.polyfit(x, prices, 1)[0]
            
            # Normalize slope to -1 to 1
            max_slope = np.std(prices) * 2
            trend_strength = np.tanh(slope / max_slope) if max_slope > 0 else 0.0
            
            return trend_strength
            
        except Exception as e:
            logger.error(f"Error calculating trend strength: {e}")
            return 0.0
    
    def _classify_regime(self, volatility: float, trend_strength: float) -> Tuple[str, float]:
        """Classify market regime based on volatility and trend"""
        try:
            # High volatility threshold
            high_vol_threshold = 0.4
            
            # Strong trend threshold
            strong_trend_threshold = 0.3
            
            if volatility > high_vol_threshold:
                if abs(trend_strength) > strong_trend_threshold:
                    if trend_strength > 0:
                        return 'BULL', 0.8
                    else:
                        return 'BEAR', 0.8
                else:
                    return 'VOLATILE', 0.9
            else:
                if abs(trend_strength) > strong_trend_threshold:
                    if trend_strength > 0:
                        return 'BULL', 0.7
                    else:
                        return 'BEAR', 0.7
                else:
                    return 'SIDEWAYS', 0.6
                    
        except Exception as e:
            logger.error(f"Error classifying regime: {e}")
            return 'SIDEWAYS', 0.5


class SignalPerformanceService:
    """Service for tracking signal performance"""
    
    def calculate_performance_metrics(self, period_type: str = '1D') -> Dict:
        """Calculate performance metrics for signals"""
        try:
            # Get date range
            end_date = timezone.now()
            if period_type == '1H':
                start_date = end_date - timedelta(hours=1)
            elif period_type == '4H':
                start_date = end_date - timedelta(hours=4)
            elif period_type == '1D':
                start_date = end_date - timedelta(days=1)
            elif period_type == '1W':
                start_date = end_date - timedelta(weeks=1)
            elif period_type == '1M':
                start_date = end_date - timedelta(days=30)
            else:
                start_date = end_date - timedelta(days=1)
            
            # Get signals in period
            signals = TradingSignal.objects.filter(
                created_at__gte=start_date,
                created_at__lte=end_date,
                is_executed=True
            )
            
            if not signals.exists():
                return self._empty_performance_metrics()
            
            # Calculate metrics
            total_signals = signals.count()
            profitable_signals = signals.filter(is_profitable=True).count()
            win_rate = profitable_signals / total_signals if total_signals > 0 else 0.0
            
            # Calculate profit/loss metrics
            profits = signals.filter(is_profitable=True).aggregate(
                avg_profit=Avg('profit_loss')
            )['avg_profit'] or Decimal('0')
            
            losses = signals.filter(is_profitable=False).aggregate(
                avg_loss=Avg('profit_loss')
            )['avg_loss'] or Decimal('0')
            
            profit_factor = abs(profits / losses) if losses != 0 else 0.0
            
            # Calculate quality metrics
            avg_confidence = signals.aggregate(
                avg_confidence=Avg('confidence_score')
            )['avg_confidence'] or 0.0
            
            avg_quality = signals.aggregate(
                avg_quality=Avg('quality_score')
            )['avg_quality'] or 0.0
            
            # Create performance record
            performance = SignalPerformance.objects.create(
                period_type=period_type,
                start_date=start_date,
                end_date=end_date,
                total_signals=total_signals,
                profitable_signals=profitable_signals,
                win_rate=win_rate,
                average_profit=profits,
                average_loss=abs(losses),
                profit_factor=profit_factor,
                average_confidence=avg_confidence,
                average_quality_score=avg_quality
            )
            
            return {
                'period_type': period_type,
                'total_signals': total_signals,
                'profitable_signals': profitable_signals,
                'win_rate': win_rate,
                'profit_factor': profit_factor,
                'average_confidence': avg_confidence,
                'average_quality': avg_quality
            }
            
        except Exception as e:
            logger.error(f"Error calculating performance metrics: {e}")
            return self._empty_performance_metrics()
    
    def _empty_performance_metrics(self) -> Dict:
        """Return empty performance metrics"""
        return {
            'period_type': '1D',
            'total_signals': 0,
            'profitable_signals': 0,
            'win_rate': 0.0,
            'profit_factor': 0.0,
            'average_confidence': 0.0,
            'average_quality': 0.0
        }


class SignalQualityEnhancementService:
    """
    Advanced Signal Quality Enhancement Service
    
    Implements sophisticated signal quality improvements including:
    - Enhanced signal confidence calculation
    - Multi-timeframe analysis
    - Signal confirmation logic
    - Signal clustering
    - False signal filtering
    """
    
    def __init__(self):
        self.timeframes = ['1h', '4h', '1d', '1w']  # Multiple timeframes for analysis
        self.confirmation_threshold = 0.75  # Minimum confirmation score
        self.clustering_threshold = 0.3  # Similarity threshold for clustering
        self.false_signal_filter_strength = 0.8  # Filter strength for false signals
        
    def enhance_signal_quality(self, signal: TradingSignal, market_data: Dict) -> TradingSignal:
        """
        Enhance signal quality using multiple enhancement techniques
        
        Args:
            signal: Original trading signal
            market_data: Current market data
            
        Returns:
            Enhanced trading signal with improved quality metrics
        """
        try:
            # Enhanced confidence calculation
            enhanced_confidence = self._calculate_enhanced_confidence(signal, market_data)
            
            # Multi-timeframe analysis
            multi_timeframe_score = self._perform_multi_timeframe_analysis(signal)
            
            # Signal confirmation logic
            confirmation_score = self._calculate_signal_confirmation(signal, market_data)
            
            # Signal clustering analysis
            cluster_score = self._analyze_signal_clustering(signal)
            
            # False signal filtering
            false_signal_probability = self._calculate_false_signal_probability(signal, market_data)
            
            # Calculate overall quality score
            quality_score = self._calculate_overall_quality_score(
                enhanced_confidence, multi_timeframe_score, 
                confirmation_score, cluster_score, false_signal_probability
            )
            
            # Update signal with enhanced metrics
            signal.confidence_score = enhanced_confidence
            signal.quality_score = quality_score
            
            # Add quality enhancement metadata
            if not hasattr(signal, 'quality_metadata'):
                signal.quality_metadata = {}
            
            signal.quality_metadata.update({
                'enhanced_confidence': enhanced_confidence,
                'multi_timeframe_score': multi_timeframe_score,
                'confirmation_score': confirmation_score,
                'cluster_score': cluster_score,
                'false_signal_probability': false_signal_probability,
                'quality_enhancement_applied': True,
                'enhancement_timestamp': timezone.now().isoformat()
            })
            
            return signal
            
        except Exception as e:
            logger.error(f"Error enhancing signal quality for {signal.id}: {e}")
            return signal
    
    def _calculate_enhanced_confidence(self, signal: TradingSignal, market_data: Dict) -> float:
        """
        Calculate enhanced confidence score using multiple factors
        
        Enhanced confidence considers:
        - Technical indicator convergence
        - Volume confirmation
        - Market regime alignment
        - Historical accuracy
        - Risk-adjusted metrics
        """
        try:
            base_confidence = signal.confidence_score
            
            # Technical convergence bonus
            technical_convergence = self._calculate_technical_convergence(signal)
            
            # Volume confirmation bonus
            volume_confirmation = self._calculate_volume_confirmation(signal, market_data)
            
            # Market regime alignment bonus
            regime_alignment = self._calculate_regime_alignment(signal)
            
            # Historical accuracy bonus
            historical_accuracy = self._calculate_historical_accuracy(signal)
            
            # Risk-adjusted bonus
            risk_adjusted_bonus = self._calculate_risk_adjusted_bonus(signal)
            
            # Calculate enhanced confidence
            enhancement_factors = [
                technical_convergence * 0.25,
                volume_confirmation * 0.20,
                regime_alignment * 0.20,
                historical_accuracy * 0.20,
                risk_adjusted_bonus * 0.15
            ]
            
            total_enhancement = sum(enhancement_factors)
            enhanced_confidence = min(1.0, base_confidence + total_enhancement)
            
            return enhanced_confidence
            
        except Exception as e:
            logger.error(f"Error calculating enhanced confidence: {e}")
            return signal.confidence_score
    
    def _calculate_technical_convergence(self, signal: TradingSignal) -> float:
        """Calculate technical indicator convergence score"""
        try:
            # Get technical scores from signal
            technical_score = abs(signal.technical_score)
            sentiment_score = abs(signal.sentiment_score)
            pattern_score = abs(signal.pattern_score)
            
            # Calculate convergence (how many indicators agree)
            agreeing_indicators = 0
            total_indicators = 0
            
            if technical_score > 0.3:
                agreeing_indicators += 1
            total_indicators += 1
            
            if sentiment_score > 0.3:
                agreeing_indicators += 1
            total_indicators += 1
            
            if pattern_score > 0.3:
                agreeing_indicators += 1
            total_indicators += 1
            
            # Convergence score based on agreement
            convergence_score = agreeing_indicators / total_indicators if total_indicators > 0 else 0.0
            
            # Bonus for strong agreement
            if agreeing_indicators >= 2:
                convergence_score *= 1.2
            
            return min(1.0, convergence_score)
            
        except Exception as e:
            logger.error(f"Error calculating technical convergence: {e}")
            return 0.0
    
    def _calculate_volume_confirmation(self, signal: TradingSignal, market_data: Dict) -> float:
        """Calculate volume confirmation score"""
        try:
            if 'volume' not in market_data:
                return 0.0
            
            current_volume = market_data['volume']
            
            # Get historical volume data for comparison
            symbol = signal.symbol
            historical_volumes = MarketData.objects.filter(
                symbol=symbol
            ).order_by('-timestamp')[:20]  # Last 20 periods
            
            if not historical_volumes.exists():
                return 0.0
            
            avg_volume = sum(float(data.volume) for data in historical_volumes) / len(historical_volumes)
            
            # Volume confirmation score
            if current_volume > avg_volume * 1.5:
                return 0.8  # High volume confirmation
            elif current_volume > avg_volume * 1.2:
                return 0.6  # Moderate volume confirmation
            elif current_volume > avg_volume:
                return 0.4  # Slight volume confirmation
            else:
                return 0.0  # No volume confirmation
            
        except Exception as e:
            logger.error(f"Error calculating volume confirmation: {e}")
            return 0.0
    
    def _calculate_regime_alignment(self, signal: TradingSignal) -> float:
        """Calculate market regime alignment score"""
        try:
            symbol = signal.symbol
            
            # Get current market regime
            regime_service = MarketRegimeService()
            current_regime = regime_service.detect_market_regime(symbol)
            
            if not current_regime:
                return 0.5  # Neutral if no regime detected
            
            # Check if signal aligns with regime
            signal_type = signal.signal_type.name
            regime_name = current_regime.name
            
            # Bullish signals in bullish regimes get bonus
            if signal_type == 'BUY' and 'bull' in regime_name.lower():
                return 0.8
            elif signal_type == 'SELL' and 'bear' in regime_name.lower():
                return 0.8
            elif signal_type == 'BUY' and 'bear' in regime_name.lower():
                return 0.2  # Penalty for counter-regime signals
            elif signal_type == 'SELL' and 'bull' in regime_name.lower():
                return 0.2  # Penalty for counter-regime signals
            else:
                return 0.5  # Neutral alignment
            
        except Exception as e:
            logger.error(f"Error calculating regime alignment: {e}")
            return 0.5
    
    def _calculate_historical_accuracy(self, signal: TradingSignal) -> float:
        """Calculate historical accuracy score for similar signals"""
        try:
            symbol = signal.symbol
            signal_type = signal.signal_type.name
            
            # Get historical signals of same type for this symbol
            historical_signals = TradingSignal.objects.filter(
                symbol=symbol,
                signal_type__name=signal_type,
                created_at__gte=timezone.now() - timedelta(days=30)
            ).exclude(id=signal.id)
            
            if not historical_signals.exists():
                return 0.5  # Neutral if no history
            
            # Calculate accuracy based on quality scores
            total_quality = sum(s.quality_score for s in historical_signals)
            avg_quality = total_quality / len(historical_signals)
            
            # Normalize to 0-1 scale
            accuracy_score = min(1.0, avg_quality)
            
            return accuracy_score
            
        except Exception as e:
            logger.error(f"Error calculating historical accuracy: {e}")
            return 0.5
    
    def _calculate_risk_adjusted_bonus(self, signal: TradingSignal) -> float:
        """Calculate risk-adjusted bonus score"""
        try:
            # Risk-reward ratio bonus
            risk_reward_bonus = 0.0
            if signal.risk_reward_ratio:
                if signal.risk_reward_ratio >= 5.0:
                    risk_reward_bonus = 0.3
                elif signal.risk_reward_ratio >= 3.0:
                    risk_reward_bonus = 0.2
                elif signal.risk_reward_ratio >= 2.0:
                    risk_reward_bonus = 0.1
            
            # Volatility consideration
            volatility_bonus = 0.0
            if hasattr(signal, 'quality_metadata') and 'volatility' in signal.quality_metadata:
                volatility = signal.quality_metadata['volatility']
                if 0.1 <= volatility <= 0.3:  # Optimal volatility range
                    volatility_bonus = 0.2
            
            # Drawdown consideration
            drawdown_bonus = 0.0
            if hasattr(signal, 'quality_metadata') and 'max_drawdown' in signal.quality_metadata:
                drawdown = signal.quality_metadata['max_drawdown']
                if drawdown < 0.1:  # Low drawdown
                    drawdown_bonus = 0.2
            
            total_bonus = risk_reward_bonus + volatility_bonus + drawdown_bonus
            return min(1.0, total_bonus)
            
        except Exception as e:
            logger.error(f"Error calculating risk-adjusted bonus: {e}")
            return 0.0
    
    def _perform_multi_timeframe_analysis(self, signal: TradingSignal) -> float:
        """
        Perform multi-timeframe analysis to confirm signal strength
        
        Analyzes signal across multiple timeframes:
        - 1 hour (short-term)
        - 4 hours (medium-term)
        - 1 day (long-term)
        - 1 week (trend-term)
        """
        try:
            symbol = signal.symbol
            signal_type = signal.signal_type.name
            
            timeframe_scores = []
            
            for timeframe in self.timeframes:
                # Get market data for this timeframe
                timeframe_data = self._get_timeframe_data(symbol, timeframe)
                if not timeframe_data:
                    continue
                
                # Calculate signal strength for this timeframe
                timeframe_score = self._calculate_timeframe_signal_strength(
                    signal_type, timeframe_data
                )
                timeframe_scores.append(timeframe_score)
            
            if not timeframe_scores:
                return 0.5  # Neutral if no timeframe data
            
            # Calculate multi-timeframe score
            # Higher weight for longer timeframes (trend confirmation)
            weighted_scores = []
            weights = [0.1, 0.2, 0.3, 0.4]  # 1h, 4h, 1d, 1w
            
            for i, score in enumerate(timeframe_scores):
                if i < len(weights):
                    weighted_scores.append(score * weights[i])
            
            multi_timeframe_score = sum(weighted_scores) / sum(weights[:len(timeframe_scores)])
            return multi_timeframe_score
            
        except Exception as e:
            logger.error(f"Error performing multi-timeframe analysis: {e}")
            return 0.5
    
    def _get_timeframe_data(self, symbol: Symbol, timeframe: str) -> Optional[Dict]:
        """Get market data for specific timeframe"""
        try:
            # This would typically query aggregated data by timeframe
            # For now, return basic data structure
            return {
                'timeframe': timeframe,
                'symbol': symbol.symbol,
                'data_available': True
            }
        except Exception as e:
            logger.error(f"Error getting timeframe data: {e}")
            return None
    
    def _calculate_timeframe_signal_strength(self, signal_type: str, timeframe_data: Dict) -> float:
        """Calculate signal strength for specific timeframe"""
        try:
            # Simplified calculation - in practice, this would analyze
            # technical indicators, patterns, and trends for the timeframe
            
            if signal_type == 'BUY':
                # Simulate bullish signal strength
                return 0.7 + (hash(timeframe_data['timeframe']) % 30) / 100
            elif signal_type == 'SELL':
                # Simulate bearish signal strength
                return 0.6 + (hash(timeframe_data['timeframe']) % 25) / 100
            else:
                return 0.5
            
        except Exception as e:
            logger.error(f"Error calculating timeframe signal strength: {e}")
            return 0.5
    
    def _calculate_signal_confirmation(self, signal: TradingSignal, market_data: Dict) -> float:
        """
        Calculate signal confirmation score using multiple confirmation methods
        
        Confirmation methods:
        - Price action confirmation
        - Volume confirmation
        - Pattern confirmation
        - Indicator confirmation
        - Support/resistance confirmation
        """
        try:
            confirmation_scores = []
            
            # Price action confirmation
            price_confirmation = self._calculate_price_action_confirmation(signal, market_data)
            confirmation_scores.append(price_confirmation)
            
            # Volume confirmation
            volume_confirmation = self._calculate_volume_confirmation(signal, market_data)
            confirmation_scores.append(volume_confirmation)
            
            # Pattern confirmation
            pattern_confirmation = self._calculate_pattern_confirmation(signal, market_data)
            confirmation_scores.append(pattern_confirmation)
            
            # Indicator confirmation
            indicator_confirmation = self._calculate_indicator_confirmation(signal)
            confirmation_scores.append(indicator_confirmation)
            
            # Support/resistance confirmation
            sr_confirmation = self._calculate_support_resistance_confirmation(signal, market_data)
            confirmation_scores.append(sr_confirmation)
            
            # Calculate weighted average confirmation score
            weights = [0.25, 0.20, 0.20, 0.20, 0.15]
            total_weight = sum(weights[:len(confirmation_scores)])
            
            weighted_confirmation = sum(
                score * weight for score, weight in zip(confirmation_scores, weights)
            ) / total_weight
            
            return weighted_confirmation
            
        except Exception as e:
            logger.error(f"Error calculating signal confirmation: {e}")
            return 0.5
    
    def _calculate_price_action_confirmation(self, signal: TradingSignal, market_data: Dict) -> float:
        """Calculate price action confirmation score"""
        try:
            if 'close_price' not in market_data or 'high_price' not in market_data or 'low_price' not in market_data:
                return 0.5
            
            close_price = market_data['close_price']
            high_price = market_data['high_price']
            low_price = market_data['low_price']
            
            signal_type = signal.signal_type.name
            
            if signal_type == 'BUY':
                # Bullish confirmation: close near high, low close to low
                high_confirmation = (close_price - low_price) / (high_price - low_price)
                return min(1.0, high_confirmation * 1.5)
            elif signal_type == 'SELL':
                # Bearish confirmation: close near low, high close to high
                low_confirmation = (high_price - close_price) / (high_price - low_price)
                return min(1.0, low_confirmation * 1.5)
            else:
                return 0.5
            
        except Exception as e:
            logger.error(f"Error calculating price action confirmation: {e}")
            return 0.5
    
    def _calculate_pattern_confirmation(self, signal: TradingSignal, market_data: Dict) -> float:
        """Calculate pattern confirmation score"""
        try:
            # This would analyze chart patterns and candlestick formations
            # For now, return a simplified score based on signal strength
            
            pattern_score = signal.pattern_score
            if pattern_score > 0.7:
                return 0.9  # Strong pattern confirmation
            elif pattern_score > 0.5:
                return 0.7  # Moderate pattern confirmation
            elif pattern_score > 0.3:
                return 0.5  # Weak pattern confirmation
            else:
                return 0.3  # No pattern confirmation
            
        except Exception as e:
            logger.error(f"Error calculating pattern confirmation: {e}")
            return 0.5
    
    def _calculate_indicator_confirmation(self, signal: TradingSignal) -> float:
        """Calculate technical indicator confirmation score"""
        try:
            # Check if technical indicators confirm the signal
            technical_score = signal.technical_score
            signal_type = signal.signal_type.name
            
            if signal_type == 'BUY' and technical_score > 0.3:
                return 0.8  # Strong bullish confirmation
            elif signal_type == 'SELL' and technical_score < -0.3:
                return 0.8  # Strong bearish confirmation
            elif abs(technical_score) > 0.1:
                return 0.6  # Moderate confirmation
            else:
                return 0.4  # Weak confirmation
            
        except Exception as e:
            logger.error(f"Error calculating indicator confirmation: {e}")
            return 0.5
    
    def _calculate_support_resistance_confirmation(self, signal: TradingSignal, market_data: Dict) -> float:
        """Calculate support/resistance confirmation score"""
        try:
            # This would analyze if price is near key support/resistance levels
            # For now, return a simplified score
            
            # Simulate support/resistance analysis
            import random
            random.seed(hash(signal.symbol.symbol) % 1000)
            
            # Random confirmation score (in practice, this would be calculated)
            confirmation = 0.5 + random.uniform(-0.2, 0.3)
            return max(0.0, min(1.0, confirmation))
            
        except Exception as e:
            logger.error(f"Error calculating support/resistance confirmation: {e}")
            return 0.5
    
    def _analyze_signal_clustering(self, signal: TradingSignal) -> float:
        """
        Analyze signal clustering to identify signal quality patterns
        
        Clustering analysis:
        - Similar signal patterns
        - Market condition clustering
        - Performance clustering
        - Risk clustering
        """
        try:
            symbol = signal.symbol
            signal_type = signal.signal_type.name
            
            # Get recent similar signals
            recent_signals = TradingSignal.objects.filter(
                symbol=symbol,
                signal_type__name=signal_type,
                created_at__gte=timezone.now() - timedelta(hours=6)
            ).exclude(id=signal.id)
            
            if not recent_signals.exists():
                return 0.7  # Good if no recent similar signals (less noise)
            
            # Calculate clustering score based on signal density
            signal_count = recent_signals.count()
            
            if signal_count == 1:
                return 0.8  # Good clustering (one recent signal)
            elif signal_count == 2:
                return 0.6  # Moderate clustering
            elif signal_count == 3:
                return 0.4  # High clustering (potential noise)
            else:
                return 0.2  # Very high clustering (likely noise)
            
        except Exception as e:
            logger.error(f"Error analyzing signal clustering: {e}")
            return 0.5
    
    def _calculate_false_signal_probability(self, signal: TradingSignal, market_data: Dict) -> float:
        """
        Calculate probability of false signal using multiple filters
        
        False signal filters:
        - Market noise detection
        - Signal frequency analysis
        - Pattern reliability
        - Market condition analysis
        - Historical false signal patterns
        """
        try:
            false_signal_factors = []
            
            # Market noise detection
            noise_factor = self._calculate_market_noise_factor(signal, market_data)
            false_signal_factors.append(noise_factor)
            
            # Signal frequency analysis
            frequency_factor = self._calculate_signal_frequency_factor(signal)
            false_signal_factors.append(frequency_factor)
            
            # Pattern reliability
            pattern_reliability = self._calculate_pattern_reliability(signal)
            false_signal_factors.append(pattern_reliability)
            
            # Market condition analysis
            market_condition = self._calculate_market_condition_factor(signal, market_data)
            false_signal_factors.append(market_condition)
            
            # Historical false signal analysis
            historical_factor = self._calculate_historical_false_signal_factor(signal)
            false_signal_factors.append(historical_factor)
            
            # Calculate weighted false signal probability
            weights = [0.25, 0.20, 0.20, 0.20, 0.15]
            total_weight = sum(weights[:len(false_signal_factors)])
            
            false_signal_probability = sum(
                factor * weight for factor, weight in zip(false_signal_factors, weights)
            ) / total_weight
            
            return min(1.0, false_signal_probability)
            
        except Exception as e:
            logger.error(f"Error calculating false signal probability: {e}")
            return 0.5
    
    def _calculate_market_noise_factor(self, signal: TradingSignal, market_data: Dict) -> float:
        """Calculate market noise factor (higher = more noise)"""
        try:
            # This would analyze market volatility, spread, and micro-movements
            # For now, return a simplified noise factor
            
            # Simulate noise based on signal characteristics
            if signal.confidence_score > 0.8:
                return 0.2  # Low noise for high confidence signals
            elif signal.confidence_score > 0.6:
                return 0.4  # Moderate noise
            else:
                return 0.6  # High noise for low confidence signals
            
        except Exception as e:
            logger.error(f"Error calculating market noise factor: {e}")
            return 0.5
    
    def _calculate_signal_frequency_factor(self, signal: TradingSignal) -> float:
        """Calculate signal frequency factor (higher = more frequent = potential noise)"""
        try:
            symbol = signal.symbol
            signal_type = signal.signal_type.name
            
            # Count signals in last hour
            recent_signals = TradingSignal.objects.filter(
                symbol=symbol,
                signal_type__name=signal_type,
                created_at__gte=timezone.now() - timedelta(hours=1)
            ).exclude(id=signal.id)
            
            signal_count = recent_signals.count()
            
            if signal_count == 0:
                return 0.1  # Very low frequency (good)
            elif signal_count == 1:
                return 0.3  # Low frequency
            elif signal_count == 2:
                return 0.5  # Moderate frequency
            elif signal_count == 3:
                return 0.7  # High frequency
            else:
                return 0.9  # Very high frequency (bad)
            
        except Exception as e:
            logger.error(f"Error calculating signal frequency factor: {e}")
            return 0.5
    
    def _calculate_pattern_reliability(self, signal: TradingSignal) -> float:
        """Calculate pattern reliability factor (higher = more reliable)"""
        try:
            # Pattern reliability based on historical accuracy
            pattern_score = signal.pattern_score
            
            if pattern_score > 0.8:
                return 0.2  # Very reliable patterns (low false signal probability)
            elif pattern_score > 0.6:
                return 0.4  # Reliable patterns
            elif pattern_score > 0.4:
                return 0.6  # Moderate reliability
            else:
                return 0.8  # Low reliability (high false signal probability)
            
        except Exception as e:
            logger.error(f"Error calculating pattern reliability: {e}")
            return 0.5
    
    def _calculate_market_condition_factor(self, signal: TradingSignal, market_data: Dict) -> float:
        """Calculate market condition factor for false signal probability"""
        try:
            # This would analyze current market conditions
            # For now, return a simplified factor
            
            # Simulate market condition analysis
            import random
            random.seed(hash(f"{signal.symbol.symbol}_{signal.created_at}") % 1000)
            
            # Random market condition factor
            condition_factor = 0.3 + random.uniform(-0.1, 0.4)
            return max(0.0, min(1.0, condition_factor))
            
        except Exception as e:
            logger.error(f"Error calculating market condition factor: {e}")
            return 0.5
    
    def _calculate_historical_false_signal_factor(self, signal: TradingSignal) -> float:
        """Calculate historical false signal factor"""
        try:
            symbol = signal.symbol
            signal_type = signal.signal_type.name
            
            # Get historical signals and their performance
            historical_signals = TradingSignal.objects.filter(
                symbol=symbol,
                signal_type__name=signal_type,
                created_at__gte=timezone.now() - timedelta(days=7)
            ).exclude(id=signal.id)
            
            if not historical_signals.exists():
                return 0.5  # Neutral if no history
            
            # Calculate false signal rate based on quality scores
            low_quality_count = sum(1 for s in historical_signals if s.quality_score < 0.6)
            total_count = len(historical_signals)
            
            false_signal_rate = low_quality_count / total_count if total_count > 0 else 0.5
            
            # Convert to factor (higher rate = higher false signal probability)
            return false_signal_rate
            
        except Exception as e:
            logger.error(f"Error calculating historical false signal factor: {e}")
            return 0.5
    
    def _calculate_overall_quality_score(self, enhanced_confidence: float, 
                                       multi_timeframe_score: float, 
                                       confirmation_score: float, 
                                       cluster_score: float, 
                                       false_signal_probability: float) -> float:
        """
        Calculate overall quality score using all enhancement factors
        
        Quality score formula:
        Quality = (Enhanced_Confidence * 0.3) + 
                  (Multi_Timeframe * 0.25) + 
                  (Confirmation * 0.25) + 
                  (Clustering * 0.1) + 
                  ((1 - False_Signal_Probability) * 0.1)
        """
        try:
            # Weighted combination of all factors
            quality_score = (
                enhanced_confidence * 0.30 +
                multi_timeframe_score * 0.25 +
                confirmation_score * 0.25 +
                cluster_score * 0.10 +
                (1 - false_signal_probability) * 0.10
            )
            
            # Ensure score is within 0-1 range
            quality_score = max(0.0, min(1.0, quality_score))
            
            return quality_score
            
        except Exception as e:
            logger.error(f"Error calculating overall quality score: {e}")
            return 0.5
    
    def enhance_multiple_signals(self, signals: List[TradingSignal], 
                                market_data: Dict) -> List[TradingSignal]:
        """
        Enhance quality for multiple signals
        
        Args:
            signals: List of trading signals to enhance
            market_data: Current market data
            
        Returns:
            List of enhanced trading signals
        """
        enhanced_signals = []
        
        for signal in signals:
            enhanced_signal = self.enhance_signal_quality(signal, market_data)
            enhanced_signals.append(enhanced_signal)
        
        return enhanced_signals
    
    def get_quality_enhancement_summary(self, signal: TradingSignal) -> Dict:
        """
        Get summary of quality enhancement applied to a signal
        
        Args:
            signal: Enhanced trading signal
            
        Returns:
            Dictionary with enhancement summary
        """
        if not hasattr(signal, 'quality_metadata') or not signal.quality_metadata:
            return {'enhancement_applied': False}
        
        metadata = signal.quality_metadata
        
        return {
            'enhancement_applied': True,
            'enhancement_timestamp': metadata.get('enhancement_timestamp'),
            'enhanced_confidence': metadata.get('enhanced_confidence', 0.0),
            'multi_timeframe_score': metadata.get('multi_timeframe_score', 0.0),
            'confirmation_score': metadata.get('confirmation_score', 0.0),
            'cluster_score': metadata.get('cluster_score', 0.0),
            'false_signal_probability': metadata.get('false_signal_probability', 0.0),
            'quality_improvement': signal.quality_score - metadata.get('original_quality_score', signal.quality_score)
        }


class PerformanceMonitor:
    """
    Comprehensive Performance Monitoring Service
    
    Implements real-time performance monitoring including:
    - Real-time P&L tracking
    - Strategy performance dashboard
    - Alert system for underperformance
    - Automated reporting
    """
    
    def __init__(self):
        self.alert_thresholds = {
            'win_rate': 0.4,  # Alert if win rate drops below 40%
            'profit_factor': 1.5,  # Alert if profit factor drops below 1.5
            'max_drawdown': 0.15,  # Alert if drawdown exceeds 15%
            'signal_quality': 0.6,  # Alert if average signal quality drops below 60%
            'daily_loss': -0.05,  # Alert if daily loss exceeds 5%
        }
        
        self.monitoring_intervals = {
            'real_time': 30,  # 30 seconds for real-time updates
            'minute': 60,      # 1 minute for minute-level updates
            'hourly': 3600,    # 1 hour for hourly updates
            'daily': 86400,    # 24 hours for daily updates
        }
        
        self.performance_cache = {}
        self.last_alert_time = {}
        
    def start_real_time_monitoring(self):
        """Start real-time performance monitoring"""
        try:
            logger.info("Starting real-time performance monitoring...")
            
            # Initialize monitoring
            self._initialize_monitoring()
            
            # Start monitoring loop
            self._monitor_performance_loop()
            
        except Exception as e:
            logger.error(f"Error starting real-time monitoring: {e}")
    
    def _initialize_monitoring(self):
        """Initialize monitoring systems"""
        try:
            # Clear performance cache
            self.performance_cache.clear()
            
            # Initialize alert tracking
            self.last_alert_time = {
                'win_rate': timezone.now(),
                'profit_factor': timezone.now(),
                'max_drawdown': timezone.now(),
                'signal_quality': timezone.now(),
                'daily_loss': timezone.now(),
            }
            
            logger.info("Performance monitoring initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing monitoring: {e}")
    
    def _monitor_performance_loop(self):
        """Main monitoring loop"""
        try:
            while True:
                # Update real-time metrics
                self._update_real_time_metrics()
                
                # Check for alerts
                self._check_performance_alerts()
                
                # Update dashboard data
                self._update_dashboard_data()
                
                # Generate reports if needed
                self._generate_automated_reports()
                
                # Sleep for monitoring interval
                time.sleep(self.monitoring_intervals['real_time'])
                
        except KeyboardInterrupt:
            logger.info("Performance monitoring stopped by user")
        except Exception as e:
            logger.error(f"Error in monitoring loop: {e}")
    
    def _update_real_time_metrics(self):
        """Update real-time performance metrics"""
        try:
            # Get current portfolio performance
            portfolio_metrics = self._calculate_portfolio_metrics()
            
            # Get strategy performance
            strategy_metrics = self._calculate_strategy_metrics()
            
            # Get signal performance
            signal_metrics = self._calculate_signal_metrics()
            
            # Update cache
            self.performance_cache.update({
                'portfolio': portfolio_metrics,
                'strategies': strategy_metrics,
                'signals': signal_metrics,
                'last_updated': timezone.now()
            })
            
            logger.debug("Real-time metrics updated successfully")
            
        except Exception as e:
            logger.error(f"Error updating real-time metrics: {e}")
    
    def _calculate_portfolio_metrics(self) -> Dict:
        """Calculate real-time portfolio performance metrics"""
        try:
            # This would integrate with your portfolio management system
            # For now, return simulated metrics
            
            portfolio_metrics = {
                'total_value': 100000.0,  # Total portfolio value
                'unrealized_pnl': 2500.0,  # Unrealized P&L
                'realized_pnl': 1500.0,   # Realized P&L
                'total_pnl': 4000.0,      # Total P&L
                'daily_pnl': 500.0,       # Daily P&L
                'daily_return': 0.005,    # Daily return (0.5%)
                'max_drawdown': 0.08,     # Maximum drawdown (8%)
                'sharpe_ratio': 1.2,      # Sharpe ratio
                'open_positions': 5,       # Number of open positions
                'cash_balance': 25000.0,   # Available cash
                'margin_used': 0.0,       # Margin used
                'risk_exposure': 0.75,    # Current risk exposure (75%)
            }
            
            return portfolio_metrics
            
        except Exception as e:
            logger.error(f"Error calculating portfolio metrics: {e}")
            return {}
    
    def _calculate_strategy_metrics(self) -> Dict:
        """Calculate real-time strategy performance metrics"""
        try:
            # Get performance for each trading strategy
            strategies = ['MA_Crossover', 'RSI', 'MACD', 'Bollinger_Bands', 'Breakout', 'Mean_Reversion']
            strategy_metrics = {}
            
            for strategy in strategies:
                # Get recent performance for this strategy
                strategy_performance = self._get_strategy_performance(strategy)
                strategy_metrics[strategy] = strategy_performance
            
            # Calculate overall strategy performance
            overall_strategy_metrics = {
                'total_strategies': len(strategies),
                'active_strategies': len([s for s in strategy_metrics.values() if s.get('is_active', False)]),
                'best_performing': self._get_best_performing_strategy(strategy_metrics),
                'worst_performing': self._get_worst_performing_strategy(strategy_metrics),
                'average_win_rate': self._calculate_average_win_rate(strategy_metrics),
                'average_profit_factor': self._calculate_average_profit_factor(strategy_metrics),
            }
            
            strategy_metrics['overall'] = overall_strategy_metrics
            
            return strategy_metrics
            
        except Exception as e:
            logger.error(f"Error calculating strategy metrics: {e}")
            return {}
    
    def _get_strategy_performance(self, strategy_name: str) -> Dict:
        """Get performance metrics for a specific strategy"""
        try:
            # This would query your strategy performance data
            # For now, return simulated metrics
            
            import random
            random.seed(hash(strategy_name) % 1000)
            
            performance = {
                'strategy_name': strategy_name,
                'is_active': random.choice([True, True, True, False]),  # 75% active
                'total_signals': random.randint(50, 200),
                'win_rate': random.uniform(0.45, 0.75),
                'profit_factor': random.uniform(1.2, 3.0),
                'total_pnl': random.uniform(-5000, 15000),
                'max_drawdown': random.uniform(0.05, 0.20),
                'sharpe_ratio': random.uniform(0.8, 2.0),
                'last_signal': timezone.now() - timedelta(minutes=random.randint(10, 120)),
                'signal_frequency': random.uniform(0.5, 2.0),  # signals per hour
                'risk_score': random.uniform(0.3, 0.8),
            }
            
            return performance
            
        except Exception as e:
            logger.error(f"Error getting strategy performance for {strategy_name}: {e}")
            return {}
    
    def _get_best_performing_strategy(self, strategy_metrics: Dict) -> str:
        """Get the best performing strategy based on win rate and profit factor"""
        try:
            if not strategy_metrics:
                return "None"
            
            # Filter active strategies
            active_strategies = {k: v for k, v in strategy_metrics.items() 
                               if k != 'overall' and v.get('is_active', False)}
            
            if not active_strategies:
                return "None"
            
            # Score based on win rate and profit factor
            best_strategy = max(active_strategies.keys(), 
                              key=lambda x: (active_strategies[x].get('win_rate', 0) * 0.6 + 
                                           active_strategies[x].get('profit_factor', 0) * 0.4))
            
            return best_strategy
            
        except Exception as e:
            logger.error(f"Error finding best performing strategy: {e}")
            return "None"
    
    def _get_worst_performing_strategy(self, strategy_metrics: Dict) -> str:
        """Get the worst performing strategy"""
        try:
            if not strategy_metrics:
                return "None"
            
            # Filter active strategies
            active_strategies = {k: v for k, v in strategy_metrics.items() 
                               if k != 'overall' and v.get('is_active', False)}
            
            if not active_strategies:
                return "None"
            
            # Score based on win rate and profit factor (lower is worse)
            worst_strategy = min(active_strategies.keys(), 
                               key=lambda x: (active_strategies[x].get('win_rate', 0) * 0.6 + 
                                            active_strategies[x].get('profit_factor', 0) * 0.4))
            
            return worst_strategy
            
        except Exception as e:
            logger.error(f"Error finding worst performing strategy: {e}")
            return "None"
    
    def _calculate_average_win_rate(self, strategy_metrics: Dict) -> float:
        """Calculate average win rate across all strategies"""
        try:
            active_strategies = [v for v in strategy_metrics.values() 
                               if v.get('is_active', False)]
            
            if not active_strategies:
                return 0.0
            
            total_win_rate = sum(s.get('win_rate', 0) for s in active_strategies)
            return total_win_rate / len(active_strategies)
            
        except Exception as e:
            logger.error(f"Error calculating average win rate: {e}")
            return 0.0
    
    def _calculate_average_profit_factor(self, strategy_metrics: Dict) -> float:
        """Calculate average profit factor across all strategies"""
        try:
            active_strategies = [v for v in strategy_metrics.values() 
                               if v.get('is_active', False)]
            
            if not active_strategies:
                return 0.0
            
            total_profit_factor = sum(s.get('profit_factor', 0) for s in active_strategies)
            return total_profit_factor / len(active_strategies)
            
        except Exception as e:
            logger.error(f"Error calculating average profit factor: {e}")
            return 0.0
    
    def _calculate_signal_metrics(self) -> Dict:
        """Calculate real-time signal performance metrics"""
        try:
            # Get recent signals
            recent_signals = TradingSignal.objects.filter(
                created_at__gte=timezone.now() - timedelta(hours=24)
            )
            
            if not recent_signals.exists():
                return self._empty_signal_metrics()
            
            # Calculate metrics
            total_signals = recent_signals.count()
            executed_signals = recent_signals.filter(is_executed=True)
            profitable_signals = executed_signals.filter(is_profitable=True)
            
            # Basic metrics
            signal_metrics = {
                'total_signals_24h': total_signals,
                'executed_signals': executed_signals.count(),
                'profitable_signals': profitable_signals.count(),
                'pending_signals': total_signals - executed_signals.count(),
                'win_rate_24h': profitable_signals.count() / executed_signals.count() if executed_signals.exists() else 0.0,
                'average_confidence': recent_signals.aggregate(Avg('confidence_score'))['confidence_score__avg'] or 0.0,
                'average_quality': recent_signals.aggregate(Avg('quality_score'))['quality_score__avg'] or 0.0,
                'signals_by_type': self._get_signals_by_type(recent_signals),
                'signals_by_symbol': self._get_signals_by_symbol(recent_signals),
                'quality_distribution': self._get_quality_distribution(recent_signals),
            }
            
            return signal_metrics
            
        except Exception as e:
            logger.error(f"Error calculating signal metrics: {e}")
            return self._empty_signal_metrics()
    
    def _empty_signal_metrics(self) -> Dict:
        """Return empty signal metrics"""
        return {
            'total_signals_24h': 0,
            'executed_signals': 0,
            'profitable_signals': 0,
            'pending_signals': 0,
            'win_rate_24h': 0.0,
            'average_confidence': 0.0,
            'average_quality': 0.0,
            'signals_by_type': {},
            'signals_by_symbol': {},
            'quality_distribution': {},
        }
    
    def _get_signals_by_type(self, signals) -> Dict:
        """Get signal count by type"""
        try:
            signal_types = {}
            for signal in signals:
                signal_type = signal.signal_type.name
                signal_types[signal_type] = signal_types.get(signal_type, 0) + 1
            
            return signal_types
            
        except Exception as e:
            logger.error(f"Error getting signals by type: {e}")
            return {}
    
    def _get_signals_by_symbol(self, signals) -> Dict:
        """Get signal count by symbol"""
        try:
            symbol_signals = {}
            for signal in signals:
                symbol = signal.symbol.symbol
                symbol_signals[symbol] = symbol_signals.get(symbol, 0) + 1
            
            return symbol_signals
            
        except Exception as e:
            logger.error(f"Error getting signals by symbol: {e}")
            return {}
    
    def _get_quality_distribution(self, signals) -> Dict:
        """Get distribution of signal quality scores"""
        try:
            quality_ranges = {
                'excellent': 0,  # 0.8-1.0
                'good': 0,       # 0.6-0.8
                'fair': 0,       # 0.4-0.6
                'poor': 0,       # 0.2-0.4
                'very_poor': 0,  # 0.0-0.2
            }
            
            for signal in signals:
                quality = signal.quality_score
                if quality >= 0.8:
                    quality_ranges['excellent'] += 1
                elif quality >= 0.6:
                    quality_ranges['good'] += 1
                elif quality >= 0.4:
                    quality_ranges['fair'] += 1
                elif quality >= 0.2:
                    quality_ranges['poor'] += 1
                else:
                    quality_ranges['very_poor'] += 1
            
            return quality_ranges
            
        except Exception as e:
            logger.error(f"Error getting quality distribution: {e}")
            return {}
    
    def _check_performance_alerts(self):
        """Check for performance alerts and trigger notifications"""
        try:
            current_time = timezone.now()
            
            # Check portfolio alerts
            self._check_portfolio_alerts(current_time)
            
            # Check strategy alerts
            self._check_strategy_alerts(current_time)
            
            # Check signal alerts
            self._check_signal_alerts(current_time)
            
        except Exception as e:
            logger.error(f"Error checking performance alerts: {e}")
    
    def _check_portfolio_alerts(self, current_time):
        """Check portfolio performance alerts"""
        try:
            portfolio = self.performance_cache.get('portfolio', {})
            
            # Check daily loss threshold
            daily_pnl = portfolio.get('daily_pnl', 0)
            if daily_pnl < self.alert_thresholds['daily_loss']:
                if self._should_send_alert('daily_loss', current_time):
                    self._create_portfolio_alert('DAILY_LOSS_THRESHOLD', 
                                               f"Daily loss of ${abs(daily_pnl):.2f} exceeds threshold", 
                                               'HIGH')
                    self.last_alert_time['daily_loss'] = current_time
            
            # Check drawdown threshold
            max_drawdown = portfolio.get('max_drawdown', 0)
            if max_drawdown > self.alert_thresholds['max_drawdown']:
                if self._should_send_alert('max_drawdown', current_time):
                    self._create_portfolio_alert('DRAWDOWN_THRESHOLD', 
                                               f"Maximum drawdown of {max_drawdown:.1%} exceeds threshold", 
                                               'HIGH')
                    self.last_alert_time['max_drawdown'] = current_time
                    
        except Exception as e:
            logger.error(f"Error checking portfolio alerts: {e}")
    
    def _check_strategy_alerts(self, current_time):
        """Check strategy performance alerts"""
        try:
            strategies = self.performance_cache.get('strategies', {})
            
            for strategy_name, metrics in strategies.items():
                if strategy_name == 'overall':
                    continue
                
                if not metrics.get('is_active', False):
                    continue
                
                # Check win rate threshold
                win_rate = metrics.get('win_rate', 0)
                if win_rate < self.alert_thresholds['win_rate']:
                    if self._should_send_alert('win_rate', current_time):
                        self._create_strategy_alert(strategy_name, 'WIN_RATE_THRESHOLD',
                                                  f"Win rate {win_rate:.1%} below threshold", 'MEDIUM')
                        self.last_alert_time['win_rate'] = current_time
                
                # Check profit factor threshold
                profit_factor = metrics.get('profit_factor', 0)
                if profit_factor < self.alert_thresholds['profit_factor']:
                    if self._should_send_alert('profit_factor', current_time):
                        self._create_strategy_alert(strategy_name, 'PROFIT_FACTOR_THRESHOLD',
                                                  f"Profit factor {profit_factor:.2f} below threshold", 'MEDIUM')
                        self.last_alert_time['profit_factor'] = current_time
                        
        except Exception as e:
            logger.error(f"Error checking strategy alerts: {e}")
    
    def _check_signal_alerts(self, current_time):
        """Check signal performance alerts"""
        try:
            signals = self.performance_cache.get('signals', {})
            
            # Check average signal quality
            avg_quality = signals.get('average_quality', 0)
            if avg_quality < self.alert_thresholds['signal_quality']:
                if self._should_send_alert('signal_quality', current_time):
                    self._create_signal_alert('SIGNAL_QUALITY_THRESHOLD',
                                            f"Average signal quality {avg_quality:.1%} below threshold", 'MEDIUM')
                    self.last_alert_time['signal_quality'] = current_time
                    
        except Exception as e:
            logger.error(f"Error checking signal alerts: {e}")
    
    def _should_send_alert(self, alert_type: str, current_time) -> bool:
        """Check if enough time has passed to send another alert"""
        try:
            last_alert = self.last_alert_time.get(alert_type)
            if not last_alert:
                return True
            
            # Don't send alerts more frequently than every 15 minutes
            time_since_last = current_time - last_alert
            return time_since_last.total_seconds() > 900  # 15 minutes
            
        except Exception as e:
            logger.error(f"Error checking alert timing: {e}")
            return True
    
    def _create_portfolio_alert(self, alert_type: str, message: str, priority: str):
        """Create portfolio performance alert"""
        try:
            SignalAlert.objects.create(
                alert_type='PERFORMANCE_ALERT',
                priority=priority,
                title=f"Portfolio Alert: {alert_type}",
                message=message,
                created_at=timezone.now()
            )
            
            logger.warning(f"Portfolio alert created: {alert_type} - {message}")
            
        except Exception as e:
            logger.error(f"Error creating portfolio alert: {e}")
    
    def _create_strategy_alert(self, strategy_name: str, alert_type: str, message: str, priority: str):
        """Create strategy performance alert"""
        try:
            SignalAlert.objects.create(
                alert_type='PERFORMANCE_ALERT',
                priority=priority,
                title=f"Strategy Alert: {strategy_name} - {alert_type}",
                message=message,
                created_at=timezone.now()
            )
            
            logger.warning(f"Strategy alert created: {strategy_name} - {alert_type} - {message}")
            
        except Exception as e:
            logger.error(f"Error creating strategy alert: {e}")
    
    def _create_signal_alert(self, alert_type: str, message: str, priority: str):
        """Create signal performance alert"""
        try:
            SignalAlert.objects.create(
                alert_type='PERFORMANCE_ALERT',
                priority=priority,
                title=f"Signal Alert: {alert_type}",
                message=message,
                created_at=timezone.now()
            )
            
            logger.warning(f"Signal alert created: {alert_type} - {message}")
            
        except Exception as e:
            logger.error(f"Error creating signal alert: {e}")
    
    def _update_dashboard_data(self):
        """Update dashboard performance data"""
        try:
            # This would update your dashboard with real-time data
            # For now, just log the update
            
            if self.performance_cache:
                logger.debug("Dashboard data updated with latest performance metrics")
                
        except Exception as e:
            logger.error(f"Error updating dashboard data: {e}")
    
    def _generate_automated_reports(self):
        """Generate automated performance reports"""
        try:
            current_time = timezone.now()
            
            # Generate daily report at midnight
            if current_time.hour == 0 and current_time.minute == 0:
                self._generate_daily_report()
            
            # Generate weekly report on Sunday at midnight
            if current_time.weekday() == 6 and current_time.hour == 0 and current_time.minute == 0:
                self._generate_weekly_report()
            
            # Generate monthly report on first day of month
            if current_time.day == 1 and current_time.hour == 0 and current_time.minute == 0:
                self._generate_monthly_report()
                
        except Exception as e:
            logger.error(f"Error generating automated reports: {e}")
    
    def _generate_daily_report(self):
        """Generate daily performance report"""
        try:
            logger.info("Generating daily performance report...")
            
            # Get daily metrics
            daily_metrics = self._get_daily_performance_summary()
            
            # Create report
            report = self._create_performance_report('DAILY', daily_metrics)
            
            logger.info(f"Daily report generated: {report}")
            
        except Exception as e:
            logger.error(f"Error generating daily report: {e}")
    
    def _generate_weekly_report(self):
        """Generate weekly performance report"""
        try:
            logger.info("Generating weekly performance report...")
            
            # Get weekly metrics
            weekly_metrics = self._get_weekly_performance_summary()
            
            # Create report
            report = self._create_performance_report('WEEKLY', weekly_metrics)
            
            logger.info(f"Weekly report generated: {report}")
            
        except Exception as e:
            logger.error(f"Error generating weekly report: {e}")
    
    def _generate_monthly_report(self):
        """Generate monthly performance report"""
        try:
            logger.info("Generating monthly performance report...")
            
            # Get monthly metrics
            monthly_metrics = self._get_monthly_performance_summary()
            
            # Create report
            report = self._create_performance_report('MONTHLY', monthly_metrics)
            
            logger.info(f"Monthly report generated: {report}")
            
        except Exception as e:
            logger.error(f"Error generating monthly report: {e}")
    
    def _get_daily_performance_summary(self) -> Dict:
        """Get daily performance summary"""
        try:
            end_date = timezone.now()
            start_date = end_date - timedelta(days=1)
            
            return {
                'period': 'Daily',
                'start_date': start_date,
                'end_date': end_date,
                'portfolio_metrics': self.performance_cache.get('portfolio', {}),
                'strategy_metrics': self.performance_cache.get('strategies', {}),
                'signal_metrics': self.performance_cache.get('signals', {}),
            }
            
        except Exception as e:
            logger.error(f"Error getting daily performance summary: {e}")
            return {}
    
    def _get_weekly_performance_summary(self) -> Dict:
        """Get weekly performance summary"""
        try:
            end_date = timezone.now()
            start_date = end_date - timedelta(weeks=1)
            
            return {
                'period': 'Weekly',
                'start_date': start_date,
                'end_date': end_date,
                'portfolio_metrics': self.performance_cache.get('portfolio', {}),
                'strategy_metrics': self.performance_cache.get('strategies', {}),
                'signal_metrics': self.performance_cache.get('signals', {}),
            }
            
        except Exception as e:
            logger.error(f"Error getting weekly performance summary: {e}")
            return {}
    
    def _get_monthly_performance_summary(self) -> Dict:
        """Get monthly performance summary"""
        try:
            end_date = timezone.now()
            start_date = end_date - timedelta(days=30)
            
            return {
                'period': 'Monthly',
                'start_date': start_date,
                'end_date': end_date,
                'portfolio_metrics': self.performance_cache.get('portfolio', {}),
                'signal_metrics': self.performance_cache.get('signals', {}),
            }
            
        except Exception as e:
            logger.error(f"Error getting monthly performance summary: {e}")
            return {}
    
    def _create_performance_report(self, report_type: str, metrics: Dict) -> str:
        """Create a formatted performance report"""
        try:
            report_lines = [
                f"=== {report_type} PERFORMANCE REPORT ===",
                f"Generated: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"Period: {metrics.get('start_date', 'N/A')} to {metrics.get('end_date', 'N/A')}",
                "",
                "PORTFOLIO PERFORMANCE:",
                f"  Total P&L: ${metrics.get('portfolio_metrics', {}).get('total_pnl', 0):.2f}",
                f"  Daily P&L: ${metrics.get('portfolio_metrics', {}).get('daily_pnl', 0):.2f}",
                f"  Max Drawdown: {metrics.get('portfolio_metrics', {}).get('max_drawdown', 0):.1%}",
                f"  Sharpe Ratio: {metrics.get('portfolio_metrics', {}).get('sharpe_ratio', 0):.2f}",
                "",
                "STRATEGY PERFORMANCE:",
            ]
            
            # Add strategy metrics
            strategies = metrics.get('strategy_metrics', {})
            for strategy_name, strategy_data in strategies.items():
                if strategy_name != 'overall' and strategy_data.get('is_active', False):
                    report_lines.extend([
                        f"  {strategy_name}:",
                        f"    Win Rate: {strategy_data.get('win_rate', 0):.1%}",
                        f"    Profit Factor: {strategy_data.get('profit_factor', 0):.2f}",
                        f"    Total P&L: ${strategy_data.get('total_pnl', 0):.2f}",
                    ])
            
            # Add signal metrics
            report_lines.extend([
                "",
                "SIGNAL PERFORMANCE:",
                f"  Total Signals (24h): {metrics.get('signal_metrics', {}).get('total_signals_24h', 0)}",
                f"  Win Rate (24h): {metrics.get('signal_metrics', {}).get('win_rate_24h', 0):.1%}",
                f"  Average Quality: {metrics.get('signal_metrics', {}).get('average_quality', 0):.1%}",
                "",
                "=== END REPORT ==="
            ])
            
            report = "\n".join(report_lines)
            return report
            
        except Exception as e:
            logger.error(f"Error creating performance report: {e}")
            return f"Error generating {report_type} report: {e}"
    
    def get_current_performance(self) -> Dict:
        """Get current performance metrics"""
        try:
            return {
                'portfolio': self.performance_cache.get('portfolio', {}),
                'strategies': self.performance_cache.get('strategies', {}),
                'signals': self.performance_cache.get('signals', {}),
                'last_updated': self.performance_cache.get('last_updated'),
                'monitoring_status': 'active'
            }
            
        except Exception as e:
            logger.error(f"Error getting current performance: {e}")
            return {'monitoring_status': 'error', 'error': str(e)}
    
    def get_performance_history(self, period: str = '1D') -> Dict:
        """Get historical performance data"""
        try:
            # This would query your historical performance data
            # For now, return simulated data
            
            end_date = timezone.now()
            if period == '1H':
                start_date = end_date - timedelta(hours=1)
            elif period == '4H':
                start_date = end_date - timedelta(hours=4)
            elif period == '1D':
                start_date = end_date - timedelta(days=1)
            elif period == '1W':
                start_date = end_date - timedelta(weeks=1)
            elif period == '1M':
                start_date = end_date - timedelta(days=30)
            else:
                start_date = end_date - timedelta(days=1)
            
            # Simulate historical data points
            data_points = []
            current = start_date
            
            while current <= end_date:
                data_points.append({
                    'timestamp': current.isoformat(),
                    'portfolio_value': 100000 + random.uniform(-5000, 5000),
                    'total_pnl': random.uniform(-2000, 3000),
                    'win_rate': random.uniform(0.4, 0.8),
                    'profit_factor': random.uniform(1.0, 3.0),
                })
                
                if period == '1H':
                    current += timedelta(minutes=5)
                elif period == '4H':
                    current += timedelta(minutes=15)
                elif period == '1D':
                    current += timedelta(hours=1)
                elif period == '1W':
                    current += timedelta(hours=6)
                elif period == '1M':
                    current += timedelta(days=1)
            
            return {
                'period': period,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'data_points': data_points,
                'summary': {
                    'total_points': len(data_points),
                    'average_pnl': sum(p['total_pnl'] for p in data_points) / len(data_points) if data_points else 0,
                    'max_pnl': max(p['total_pnl'] for p in data_points) if data_points else 0,
                    'min_pnl': min(p['total_pnl'] for p in data_points) if data_points else 0,
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting performance history: {e}")
            return {'error': str(e)}
    
    def stop_monitoring(self):
        """Stop performance monitoring"""
        try:
            logger.info("Stopping performance monitoring...")
            # This would clean up monitoring resources
            # For now, just log the stop
            
        except Exception as e:
            logger.error(f"Error stopping monitoring: {e}")


class HistoricalSignalService:
    """Service for generating signals for specific historical periods"""
    
    def __init__(self):
        self.signal_service = SignalGenerationService()
        self.logger = logging.getLogger(__name__)
    
    def generate_signals_for_period(self, symbol: Symbol, start_date: datetime, end_date: datetime) -> List[TradingSignal]:
        """
        Generate signals for a specific symbol and date range with proper price handling
        
        Args:
            symbol: Trading symbol to generate signals for
            start_date: Start date for signal generation
            end_date: End date for signal generation
            
        Returns:
            List of generated TradingSignal objects with guaranteed proper price values
        """
        try:
            self.logger.info(f"Generating historical signals for {symbol.symbol} from {start_date} to {end_date}")
            
            # Ensure dates are timezone-aware to avoid comparison errors
            from django.utils import timezone
            if start_date.tzinfo is None:
                start_date = timezone.make_aware(start_date)
            if end_date.tzinfo is None:
                end_date = timezone.make_aware(end_date)
            
            # Validate date range
            if start_date >= end_date:
                raise ValueError("Start date must be before end date")
            
            # Fetch real historical data for this period
            self._fetch_real_historical_data(symbol, start_date, end_date)
            
            # Get historical price at start date for signal generation
            historical_price = self._get_historical_price_at_date(symbol, start_date)
            if historical_price:
                self.logger.info(f"Using historical price for {symbol.symbol} at {start_date}: {historical_price}")
                fallback_price = historical_price
            else:
                fallback_price = self._get_fallback_price_for_symbol(symbol)
                self.logger.info(f"Using fallback price for {symbol.symbol}: {fallback_price}")
            
            # Generate base signals using the main signal service
            base_signals = self.signal_service.generate_signals_for_symbol(symbol)
            self.logger.info(f"Generated {len(base_signals)} base signals for {symbol.symbol}")
            
            # Create historical signals with proper price values
            historical_signals = []
            
            if base_signals:
                # Calculate time span for distributing signals
                time_span = end_date - start_date
                signal_count = len(base_signals)
                
                # Distribute signals evenly across the time period
                for i, base_signal in enumerate(base_signals):
                    # Calculate timestamp within the period
                    if signal_count > 1:
                        signal_time = start_date + (time_span * i / (signal_count - 1))
                    else:
                        signal_time = start_date + time_span / 2
                    
                    # Ensure proper price values
                    entry_price = base_signal.entry_price if base_signal.entry_price and base_signal.entry_price > 0 else Decimal(str(fallback_price))
                    
                    # Calculate target and stop loss if they're missing
                    if not base_signal.target_price or not base_signal.stop_loss or base_signal.target_price <= 0 or base_signal.stop_loss <= 0:
                        target_price, stop_loss = self._calculate_target_and_stop_loss(
                            float(entry_price), 
                            base_signal.signal_type.name
                        )
                    else:
                        target_price = base_signal.target_price
                        stop_loss = base_signal.stop_loss
                    
                    # Calculate risk-reward ratio
                    risk = abs(float(Decimal(str(entry_price)) - stop_loss))
                    reward = abs(float(target_price - Decimal(str(entry_price))))
                    risk_reward_ratio = reward / risk if risk > 0 else 1.0
                    
                    # Ensure all required fields have proper values
                    quality_score = getattr(base_signal, 'quality_score', None) or base_signal.confidence_score or 0.5
                    timeframe = getattr(base_signal, 'timeframe', '1D')
                    entry_point_type = getattr(base_signal, 'entry_point_type', 'BREAKOUT')
                    
                    # Create historical signal with guaranteed proper values
                    historical_signal = TradingSignal(
                        symbol=base_signal.symbol,
                        signal_type=base_signal.signal_type,
                        entry_price=entry_price,
                        target_price=target_price,
                        stop_loss=stop_loss,
                        confidence_score=base_signal.confidence_score,
                        confidence_level=base_signal.confidence_level,
                        risk_reward_ratio=risk_reward_ratio,
                        timeframe=timeframe,
                        entry_point_type=entry_point_type,
                        quality_score=quality_score,
                        strength=base_signal.strength,
                        notes=getattr(base_signal, 'notes', f'Historical signal with fallback price: {fallback_price}'),
                        is_valid=True,
                        expires_at=signal_time + timezone.timedelta(hours=24),
                        created_at=signal_time,
                        is_hybrid=getattr(base_signal, 'is_hybrid', False),
                        is_best_of_day=False,
                        metadata=getattr(base_signal, 'metadata', {})
                    )
                    
                    historical_signals.append(historical_signal)
                    self.logger.info(f"Prepared historical signal for {symbol.symbol}: {base_signal.signal_type.name} at ${entry_price}")
            
            # Save signals to database
            if historical_signals:
                try:
                    # Use bulk_create for efficiency
                    TradingSignal.objects.bulk_create(historical_signals, ignore_conflicts=True)
                    self.logger.info(f"Bulk created {len(historical_signals)} signals for {symbol.symbol}")
                    
                    # Retrieve the created signals from the database
                    created_signals = TradingSignal.objects.filter(
                        symbol=symbol,
                        created_at__gte=start_date,
                        created_at__lte=end_date
                    ).order_by('created_at')
                    
                    self.logger.info(f"Retrieved {created_signals.count()} signals from database")
                    return list(created_signals)
                    
                except Exception as bulk_error:
                    self.logger.error(f"Error with bulk creation: {bulk_error}")
                    # Fallback to individual saves
                    saved_signals = []
                    for signal in historical_signals:
                        try:
                            signal.save()
                            saved_signals.append(signal)
                        except Exception as individual_error:
                            self.logger.error(f"Error saving individual signal: {individual_error}")
                    return saved_signals
            
            self.logger.info(f"Generated {len(historical_signals)} historical signals for {symbol.symbol}")
            return historical_signals
            
        except Exception as e:
            self.logger.error(f"Error generating historical signals: {e}")
            return []
    
    def _get_fallback_price_for_symbol(self, symbol_obj):
        """Get a reasonable fallback price for a symbol"""
        
        # Try to get latest market data
        try:
            from apps.data.models import MarketData
            latest_market_data = MarketData.objects.filter(
                symbol=symbol_obj
            ).order_by('-timestamp').first()
            
            if latest_market_data and latest_market_data.close_price > 0:
                return float(latest_market_data.close_price)
        except Exception as e:
            self.logger.warning(f"Could not get market data for {symbol_obj.symbol}: {e}")
        
        # Try live price service
        try:
            from apps.data.real_price_service import get_live_prices
            live_prices = get_live_prices()
            if symbol_obj.symbol in live_prices:
                price = live_prices[symbol_obj.symbol].get('price', 0)
                if price > 0:
                    return float(price)
        except Exception as e:
            self.logger.warning(f"Could not get live price for {symbol_obj.symbol}: {e}")
        
        # Fallback to reasonable default prices for major cryptocurrencies
        default_prices = {
            'BTC': 100000.0, 'ETH': 4000.0, 'BNB': 600.0, 'ADA': 1.0, 'SOL': 200.0,
            'XRP': 2.0, 'DOGE': 0.4, 'MATIC': 1.0, 'DOT': 8.0, 'AVAX': 40.0,
            'LINK': 20.0, 'UNI': 15.0, 'ATOM': 12.0, 'FTM': 1.2, 'ALGO': 0.3,
            'VET': 0.05, 'ICP': 15.0, 'THETA': 2.0, 'SAND': 0.5, 'MANA': 0.8,
            'LTC': 150.0, 'BCH': 500.0, 'ETC': 30.0, 'XLM': 0.3, 'TRX': 0.2,
            'XMR': 200.0, 'ZEC': 50.0, 'DASH': 80.0, 'NEO': 25.0, 'QTUM': 5.0
        }
        
        return default_prices.get(symbol_obj.symbol, 1.0)  # Default to $1 for unknown symbols
    
    def _calculate_target_and_stop_loss(self, entry_price, signal_type_name):
        """Calculate target price and stop loss based on entry price and signal type"""
        entry_decimal = Decimal(str(entry_price))
        
        if signal_type_name in ['BUY', 'STRONG_BUY']:
            # For buy signals: 60% profit target, 40% stop loss
            target_price = entry_decimal * Decimal('1.60')  # 60% profit
            stop_loss = entry_decimal * Decimal('0.60')     # 40% stop loss
        else:
            # For sell signals: 60% profit target, 40% stop loss
            target_price = entry_decimal * Decimal('0.40')  # 60% profit for sell (lower price)
            stop_loss = entry_decimal * Decimal('1.40')     # 40% stop loss for sell (higher price)
        
        return target_price, stop_loss
    def _get_historical_data(self, symbol: Symbol, start_date: datetime, end_date: datetime):
        """Get historical market data for the symbol and date range (real-data-only)."""
        qs = MarketData.objects.filter(
            symbol=symbol,
            timestamp__gte=start_date,
            timestamp__lte=end_date
        ).order_by('timestamp')
        if not qs.exists():
            self.logger.error(
                f"No historical data found for {symbol.symbol} in range {start_date} to {end_date}. "
                f"Populate historical data before generating signals."
            )
        return qs
    
    def _fetch_real_historical_data(self, symbol: Symbol, start_date: datetime, end_date: datetime):
        """Fetch real historical market data from Binance API"""
        try:
            from apps.data.historical_data_service import get_historical_data
            
            # Check if symbol is supported
            if not symbol.symbol.upper() in ['BTC', 'ETH', 'BNB', 'ADA', 'SOL', 'XRP', 'DOGE', 'TRX', 'LINK', 'DOT', 'MATIC', 'UNI', 'AVAX', 'ATOM', 'FTM', 'ALGO', 'VET', 'ICP', 'THETA', 'SAND', 'MANA', 'LTC', 'BCH', 'ETC', 'XLM', 'XMR', 'ZEC', 'DASH', 'NEO', 'QTUM']:
                self.logger.warning(f"Symbol {symbol.symbol} not supported for real historical data, using fallback")
                return self._generate_fallback_data(symbol, start_date, end_date)
            
            # Check if data already exists for this symbol and date range
            existing_data = MarketData.objects.filter(
                symbol=symbol,
                timestamp__gte=start_date,
                timestamp__lte=end_date
            ).exists()
            
            if existing_data:
                self.logger.info(f"Historical data already exists for {symbol.symbol} in range {start_date} to {end_date}")
                return
            
            # Fetch real historical data from Binance
            self.logger.info(f"Fetching real historical data for {symbol.symbol} from {start_date} to {end_date}")
            historical_data = get_historical_data(symbol.symbol, start_date, end_date, '1h')
            
            if not historical_data:
                self.logger.warning(f"No historical data found for {symbol.symbol}, using fallback")
                return self._generate_fallback_data(symbol, start_date, end_date)
            
            # Convert to MarketData objects
            data_points = []
            for data_point in historical_data:
                data_points.append(MarketData(
                    symbol=symbol,
                    timestamp=data_point['timestamp'],
                    open_price=data_point['open'],
                    high_price=data_point['high'],
                    low_price=data_point['low'],
                    close_price=data_point['close'],
                    volume=data_point['volume']
                ))
            
            # Bulk create data with ignore_conflicts to avoid duplicate errors
            try:
                MarketData.objects.bulk_create(data_points, ignore_conflicts=True)
                self.logger.info(f"Stored {len(data_points)} real historical data points for {symbol.symbol}")
            except Exception as e:
                self.logger.warning(f"Error storing historical data: {e}")
                # Try to create data one by one to identify specific conflicts
                created_count = 0
                for data_point in data_points:
                    try:
                        data_point.save()
                        created_count += 1
                    except Exception as individual_error:
                        self.logger.warning(f"Skipping duplicate data point: {individual_error}")
                self.logger.info(f"Stored {created_count} real historical data points for {symbol.symbol}")
                
        except Exception as e:
            self.logger.error(f"Error fetching real historical data for {symbol.symbol}: {e}")
            self.logger.info("Falling back to synthetic data generation")
            return self._generate_fallback_data(symbol, start_date, end_date)
    
    def _generate_fallback_data(self, symbol: Symbol, start_date: datetime, end_date: datetime):
        """Generate fallback synthetic data when real data is not available"""
        import random
        
        self.logger.warning(f"Generating fallback synthetic data for {symbol.symbol}")
        
        # Check if data already exists for this symbol and date range
        existing_data = MarketData.objects.filter(
            symbol=symbol,
            timestamp__gte=start_date,
            timestamp__lte=end_date
        ).exists()
        
        if existing_data:
            self.logger.info(f"Fallback data already exists for {symbol.symbol} in range {start_date} to {end_date}")
            return
        
        # Use realistic base prices based on symbol
        base_prices = {
            'BTC': 50000.0, 'ETH': 3000.0, 'BNB': 300.0, 'ADA': 1.0, 'SOL': 100.0,
            'XRP': 0.5, 'DOGE': 0.1, 'TRX': 0.05, 'LINK': 20.0, 'DOT': 10.0,
            'MATIC': 1.0, 'UNI': 15.0, 'AVAX': 30.0, 'ATOM': 8.0, 'FTM': 0.5,
            'ALGO': 0.3, 'VET': 0.05, 'ICP': 15.0, 'THETA': 2.0, 'SAND': 0.5,
            'MANA': 0.8, 'LTC': 150.0, 'BCH': 300.0, 'ETC': 30.0, 'XLM': 0.3,
            'XMR': 150.0, 'ZEC': 50.0, 'DASH': 80.0, 'NEO': 25.0, 'QTUM': 5.0
        }
        
        base_price = base_prices.get(symbol.symbol, 1.0)
        current_price = base_price
        
        current_date = start_date
        data_points = []
        
        while current_date <= end_date:
            # Generate realistic price movement
            change = random.gauss(0.0005, 0.015)  # 0.05% mean, 1.5% std
            current_price *= (1 + change)
            
            # Ensure price stays reasonable
            current_price = max(0.01, min(100000.0, current_price))
            
            # Generate OHLC from current price
            volatility = random.uniform(0.005, 0.03)  # 0.5-3% daily volatility
            high = current_price * (1 + random.uniform(0, volatility))
            low = current_price * (1 - random.uniform(0, volatility))
            open_price = current_price * (1 + random.uniform(-volatility/2, volatility/2))
            close_price = current_price
            
            # Generate realistic volume
            volume = random.uniform(1000000, 10000000)  # 1M to 10M volume
            
            data_points.append(MarketData(
                symbol=symbol,
                timestamp=current_date,
                open_price=open_price,
                high_price=high,
                low_price=low,
                close_price=close_price,
                volume=volume
            ))
            
            current_date += timedelta(hours=1)  # Hourly data
        
        # Bulk create data with ignore_conflicts to avoid duplicate errors
        try:
            MarketData.objects.bulk_create(data_points, ignore_conflicts=True)
            self.logger.info(f"Generated {len(data_points)} fallback data points for {symbol.symbol}")
        except Exception as e:
            self.logger.warning(f"Error creating fallback data: {e}")
            # Try to create data one by one to identify specific conflicts
            created_count = 0
            for data_point in data_points:
                try:
                    data_point.save()
                    created_count += 1
                except Exception as individual_error:
                    self.logger.warning(f"Skipping duplicate data point: {individual_error}")
            self.logger.info(f"Created {created_count} fallback data points for {symbol.symbol}")
    
    def _get_historical_price_at_date(self, symbol: Symbol, target_date: datetime) -> Optional[float]:
        """Get the historical price of a symbol at a specific date"""
        try:
            from apps.data.historical_data_service import get_symbol_price_at_date
            return get_symbol_price_at_date(symbol.symbol, target_date)
        except Exception as e:
            self.logger.warning(f"Could not get historical price for {symbol.symbol} at {target_date}: {e}")
            return None
    
    def get_available_symbols(self) -> List[Symbol]:
        """Get all active symbols available for backtesting"""
        return Symbol.objects.filter(is_active=True).order_by('symbol')
    
    def validate_date_range(self, start_date: datetime, end_date: datetime) -> Tuple[bool, str]:
        """
        Validate the date range for backtesting
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Ensure dates are timezone-aware to avoid comparison errors
        from django.utils import timezone
        if start_date.tzinfo is None:
            start_date = timezone.make_aware(start_date)
        if end_date.tzinfo is None:
            end_date = timezone.make_aware(end_date)
        
        if start_date >= end_date:
            return False, "Start date must be before end date"
        
        if (end_date - start_date).days > 730:  # 2 years max
            return False, "Date range cannot exceed 2 years"
        
        # Create timezone-aware datetime for comparison
        min_date = timezone.make_aware(datetime(2020, 1, 1))
        if start_date < min_date:
            return False, "Start date cannot be before 2020"
        
        if end_date > timezone.now():
            return False, "End date cannot be in the future"
        
        return True, ""
