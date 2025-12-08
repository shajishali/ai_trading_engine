"""
Spot Trading Strategy Engine
Long-term spot trading strategies for cryptocurrency accumulation and investment
"""

import logging
from typing import List, Dict, Optional
from decimal import Decimal
from django.utils import timezone
from datetime import datetime, timedelta

from apps.trading.models import Symbol
from apps.data.models import MarketData, TechnicalIndicator
from apps.signals.models import SpotTradingSignal, TradingSignal, SignalType
from apps.sentiment.models import SentimentAggregate

logger = logging.getLogger(__name__)


class SpotFundamentalAnalysis:
    """Fundamental analysis for spot trading"""
    
    def __init__(self):
        self.factor_weights = {
            'team_strength': 0.15,
            'technology_innovation': 0.20,
            'market_adoption': 0.20,
            'tokenomics': 0.15,
            'competitive_advantage': 0.10,
            'regulatory_environment': 0.10,
            'partnerships': 0.05,
            'community_strength': 0.05,
        }
    
    def analyze_project_fundamentals(self, symbol: Symbol) -> Dict:
        """Analyze project fundamentals"""
        factors = {
            'team_strength': self._analyze_team(symbol),
            'technology_innovation': self._analyze_technology(symbol),
            'market_adoption': self._analyze_adoption(symbol),
            'tokenomics': self._analyze_tokenomics(symbol),
            'competitive_advantage': self._analyze_competition(symbol),
            'regulatory_environment': self._analyze_regulation(symbol),
            'partnerships': self._analyze_partnerships(symbol),
            'community_strength': self._analyze_community(symbol),
        }
        return factors
    
    def calculate_fundamental_score(self, factors: Dict) -> float:
        """Calculate overall fundamental score"""
        score = sum(factors[key] * self.factor_weights[key] for key in self.factor_weights)
        return min(1.0, max(0.0, score))
    
    def _analyze_team(self, symbol: Symbol) -> float:
        """Analyze team strength (placeholder implementation)"""
        # In a real implementation, this would analyze:
        # - Team experience and track record
        # - Technical expertise
        # - Previous project success
        # - Industry reputation
        
        # For now, use market cap rank as a proxy
        if symbol.market_cap_rank:
            if symbol.market_cap_rank <= 10:
                return 0.9  # Top 10 projects
            elif symbol.market_cap_rank <= 50:
                return 0.7  # Top 50 projects
            elif symbol.market_cap_rank <= 100:
                return 0.5  # Top 100 projects
            else:
                return 0.3  # Lower ranked projects
        
        return 0.5  # Default score
    
    def _analyze_technology(self, symbol: Symbol) -> float:
        """Analyze technology innovation"""
        # Analyze based on symbol characteristics
        if symbol.symbol in ['BTC', 'ETH']:
            return 0.9  # Established technologies
        elif symbol.symbol in ['SOL', 'ADA', 'DOT', 'AVAX']:
            return 0.8  # Innovative layer 1s
        elif symbol.symbol in ['LINK', 'UNI', 'AAVE', 'COMP']:
            return 0.7  # DeFi protocols
        else:
            return 0.6  # Default score
    
    def _analyze_adoption(self, symbol: Symbol) -> float:
        """Analyze market adoption"""
        # Use market cap rank and trading volume as proxies
        if symbol.market_cap_rank:
            if symbol.market_cap_rank <= 20:
                return 0.8
            elif symbol.market_cap_rank <= 100:
                return 0.6
            else:
                return 0.4
        
        return 0.5
    
    def _analyze_tokenomics(self, symbol: Symbol) -> float:
        """Analyze tokenomics"""
        # Analyze supply characteristics
        if symbol.circulating_supply and symbol.total_supply:
            circulating_ratio = float(symbol.circulating_supply / symbol.total_supply)
            if circulating_ratio > 0.8:
                return 0.8  # High circulating supply
            elif circulating_ratio > 0.5:
                return 0.6  # Moderate circulating supply
            else:
                return 0.4  # Low circulating supply
        
        return 0.5
    
    def _analyze_competition(self, symbol: Symbol) -> float:
        """Analyze competitive advantage"""
        # Simple analysis based on market position
        if symbol.market_cap_rank:
            if symbol.market_cap_rank <= 10:
                return 0.9
            elif symbol.market_cap_rank <= 50:
                return 0.7
            else:
                return 0.5
        
        return 0.5
    
    def _analyze_regulation(self, symbol: Symbol) -> float:
        """Analyze regulatory environment"""
        # For now, assume all crypto has similar regulatory risk
        return 0.6
    
    def _analyze_partnerships(self, symbol: Symbol) -> float:
        """Analyze partnerships and ecosystem"""
        # Major projects likely have better partnerships
        if symbol.market_cap_rank and symbol.market_cap_rank <= 50:
            return 0.7
        return 0.5
    
    def _analyze_community(self, symbol: Symbol) -> float:
        """Analyze community strength"""
        # Larger projects typically have stronger communities
        if symbol.market_cap_rank and symbol.market_cap_rank <= 100:
            return 0.7
        return 0.5


class SpotTechnicalAnalysis:
    """Long-term technical analysis for spot trading"""
    
    def __init__(self):
        self.timeframe_weights = {
            'trend_direction': 0.25,
            'support_resistance': 0.20,
            'volume_profile': 0.15,
            'momentum_indicators': 0.15,
            'volatility_analysis': 0.15,
            'market_cycles': 0.10,
        }
    
    def analyze_long_term_trends(self, symbol: Symbol) -> Dict:
        """Analyze long-term trends (1D, 1W, 1M timeframes)"""
        analysis = {
            'trend_direction': self._analyze_trend_direction(symbol),
            'support_resistance': self._analyze_support_resistance(symbol),
            'volume_profile': self._analyze_volume_profile(symbol),
            'momentum_indicators': self._analyze_momentum(symbol),
            'volatility_analysis': self._analyze_volatility(symbol),
            'market_cycles': self._analyze_market_cycles(symbol),
        }
        return analysis
    
    def calculate_technical_score(self, analysis: Dict) -> float:
        """Calculate technical score for spot trading"""
        score = sum(analysis[key] * self.timeframe_weights[key] for key in self.timeframe_weights)
        return min(1.0, max(0.0, score))
    
    def _analyze_trend_direction(self, symbol: Symbol) -> float:
        """Analyze long-term trend direction"""
        try:
            # Get recent market data for trend analysis
            recent_data = MarketData.objects.filter(symbol=symbol).order_by('-timestamp')[:200]
            
            if len(recent_data) < 50:
                return 0.5  # Not enough data
            
            # Calculate moving averages
            prices = [float(d.close_price) for d in recent_data]
            
            # Simple trend analysis
            sma_20 = sum(prices[:20]) / 20
            sma_50 = sum(prices[:50]) / 50
            
            current_price = prices[0]
            
            # Trend scoring
            if current_price > sma_20 > sma_50:
                return 0.8  # Strong uptrend
            elif current_price > sma_20:
                return 0.6  # Moderate uptrend
            elif current_price < sma_20 < sma_50:
                return 0.2  # Downtrend
            else:
                return 0.4  # Sideways/uncertain
                
        except Exception as e:
            logger.warning(f"Error analyzing trend for {symbol.symbol}: {e}")
            return 0.5
    
    def _analyze_support_resistance(self, symbol: Symbol) -> float:
        """Analyze support and resistance levels"""
        try:
            recent_data = MarketData.objects.filter(symbol=symbol).order_by('-timestamp')[:100]
            
            if len(recent_data) < 20:
                return 0.5
            
            prices = [float(d.close_price) for d in recent_data]
            current_price = prices[0]
            
            # Find support and resistance levels
            high_prices = [float(d.high_price) for d in recent_data]
            low_prices = [float(d.low_price) for d in recent_data]
            
            resistance = max(high_prices)
            support = min(low_prices)
            
            # Score based on distance from key levels
            price_range = resistance - support
            if price_range > 0:
                distance_from_support = (current_price - support) / price_range
                
                if distance_from_support > 0.7:
                    return 0.7  # Near resistance, potential reversal
                elif distance_from_support < 0.3:
                    return 0.8  # Near support, potential bounce
                else:
                    return 0.6  # Middle range
            
            return 0.5
            
        except Exception as e:
            logger.warning(f"Error analyzing support/resistance for {symbol.symbol}: {e}")
            return 0.5
    
    def _analyze_volume_profile(self, symbol: Symbol) -> float:
        """Analyze volume profile"""
        try:
            recent_data = MarketData.objects.filter(symbol=symbol).order_by('-timestamp')[:50]
            
            if len(recent_data) < 10:
                return 0.5
            
            volumes = [float(d.volume) for d in recent_data]
            avg_volume = sum(volumes) / len(volumes)
            current_volume = volumes[0]
            
            # Volume analysis
            if current_volume > avg_volume * 1.5:
                return 0.8  # High volume
            elif current_volume > avg_volume:
                return 0.6  # Above average volume
            else:
                return 0.4  # Low volume
                
        except Exception as e:
            logger.warning(f"Error analyzing volume for {symbol.symbol}: {e}")
            return 0.5
    
    def _analyze_momentum(self, symbol: Symbol) -> float:
        """Analyze momentum indicators"""
        try:
            # Get RSI indicator
            rsi_indicator = TechnicalIndicator.objects.filter(
                symbol=symbol,
                indicator_type='RSI'
            ).order_by('-timestamp').first()
            
            if rsi_indicator:
                rsi_value = float(rsi_indicator.value)
                
                # RSI analysis for long-term
                if 30 <= rsi_value <= 70:
                    return 0.7  # Neutral zone, good for accumulation
                elif rsi_value < 30:
                    return 0.8  # Oversold, good buying opportunity
                elif rsi_value > 70:
                    return 0.3  # Overbought, potential selling
                else:
                    return 0.5
            
            return 0.5
            
        except Exception as e:
            logger.warning(f"Error analyzing momentum for {symbol.symbol}: {e}")
            return 0.5
    
    def _analyze_volatility(self, symbol: Symbol) -> float:
        """Analyze volatility for long-term positioning"""
        try:
            recent_data = MarketData.objects.filter(symbol=symbol).order_by('-timestamp')[:30]
            
            if len(recent_data) < 10:
                return 0.5
            
            prices = [float(d.close_price) for d in recent_data]
            
            # Calculate volatility
            returns = []
            for i in range(1, len(prices)):
                returns.append((prices[i-1] - prices[i]) / prices[i])
            
            if returns:
                volatility = sum(abs(r) for r in returns) / len(returns)
                
                # For spot trading, moderate volatility is preferred
                if 0.02 <= volatility <= 0.05:
                    return 0.8  # Good volatility for DCA
                elif volatility < 0.02:
                    return 0.6  # Low volatility
                else:
                    return 0.4  # High volatility
            
            return 0.5
            
        except Exception as e:
            logger.warning(f"Error analyzing volatility for {symbol.symbol}: {e}")
            return 0.5
    
    def _analyze_market_cycles(self, symbol: Symbol) -> float:
        """Analyze market cycle position"""
        # This would typically involve more complex cycle analysis
        # For now, use a simple heuristic based on recent performance
        
        try:
            recent_data = MarketData.objects.filter(symbol=symbol).order_by('-timestamp')[:100]
            
            if len(recent_data) < 50:
                return 0.5
            
            prices = [float(d.close_price) for d in recent_data]
            current_price = prices[0]
            price_50_days_ago = prices[49]
            
            # Calculate 50-day return
            return_50d = (current_price - price_50_days_ago) / price_50_days_ago
            
            # Cycle analysis
            if return_50d > 0.2:
                return 0.3  # Strong rally, potential top
            elif return_50d < -0.2:
                return 0.8  # Strong decline, potential bottom
            else:
                return 0.6  # Neutral cycle position
            
        except Exception as e:
            logger.warning(f"Error analyzing market cycles for {symbol.symbol}: {e}")
            return 0.5


class SpotTradingStrategyEngine:
    """Strategy engine for spot trading signals"""
    
    def __init__(self):
        self.fundamental_analyzer = SpotFundamentalAnalysis()
        self.technical_analyzer = SpotTechnicalAnalysis()
    
    def generate_spot_signals(self, symbol: Symbol) -> List[SpotTradingSignal]:
        """Generate long-term spot trading signals"""
        logger.info(f"Generating spot signals for {symbol.symbol}")
        
        signals = []
        
        try:
            # 1. Fundamental Analysis
            fundamental_factors = self.fundamental_analyzer.analyze_project_fundamentals(symbol)
            fundamental_score = self.fundamental_analyzer.calculate_fundamental_score(fundamental_factors)
            
            # 2. Technical Analysis
            technical_analysis = self.technical_analyzer.analyze_long_term_trends(symbol)
            technical_score = self.technical_analyzer.calculate_technical_score(technical_analysis)
            
            # 3. Sentiment Analysis (placeholder)
            sentiment_score = self._analyze_sentiment(symbol)
            
            # 4. Generate signals based on combined analysis - LOWERED THRESHOLDS FOR MORE SIGNALS
            if fundamental_score >= 0.3 and technical_score >= 0.2:  # Further lowered thresholds
                signal = self._create_accumulation_signal(
                    symbol, fundamental_score, technical_score, sentiment_score,
                    fundamental_factors, technical_analysis
                )
                signal.save()  # Save to database
                signals.append(signal)
            
            elif fundamental_score >= 0.4 and technical_score >= 0.1:  # Further lowered thresholds
                signal = self._create_dca_signal(
                    symbol, fundamental_score, technical_score, sentiment_score,
                    fundamental_factors, technical_analysis
                )
                signal.save()  # Save to database
                signals.append(signal)
            
            elif fundamental_score < 0.2 or technical_score < 0.1:  # Further lowered thresholds
                signal = self._create_distribution_signal(
                    symbol, fundamental_score, technical_score, sentiment_score,
                    fundamental_factors, technical_analysis
                )
                signal.save()  # Save to database
                signals.append(signal)
            
            logger.info(f"Generated {len(signals)} spot signals for {symbol.symbol}")
            
        except Exception as e:
            logger.error(f"Error generating spot signals for {symbol.symbol}: {e}")
        
        return signals
    
    def _analyze_sentiment(self, symbol: Symbol) -> float:
        """Analyze market sentiment (placeholder implementation)"""
        try:
            # Get recent sentiment data - asset is a ForeignKey to Symbol
            sentiment = SentimentAggregate.objects.filter(asset=symbol).order_by('-created_at').first()
            
            if sentiment:
                return float(sentiment.combined_sentiment_score)
            
            return 0.5  # Neutral sentiment
            
        except Exception as e:
            logger.warning(f"Error analyzing sentiment for {symbol.symbol}: {e}")
            return 0.5
    
    def _create_accumulation_signal(self, symbol: Symbol, fundamental_score: float, 
                                 technical_score: float, sentiment_score: float,
                                 fundamental_factors: Dict, technical_analysis: Dict) -> SpotTradingSignal:
        """Create accumulation signal for strong projects"""
        
        # Calculate price targets
        current_price = self._get_current_price(symbol)
        target_price_6m = current_price * Decimal('1.5') if current_price else None
        target_price_1y = current_price * Decimal('2.0') if current_price else None
        target_price_2y = current_price * Decimal('3.0') if current_price else None
        
        return SpotTradingSignal(
            symbol=symbol,
            signal_category='ACCUMULATION',
            investment_horizon='MEDIUM_TERM',
            fundamental_score=fundamental_score,
            technical_score=technical_score,
            sentiment_score=sentiment_score,
            recommended_allocation=min(0.1, fundamental_score * 0.15),
            dca_frequency='MONTHLY',
            dca_amount_usd=Decimal('100.00'),
            target_price_6m=target_price_6m,
            target_price_1y=target_price_1y,
            target_price_2y=target_price_2y,
            max_position_size=0.15,
            stop_loss_percentage=0.30,  # 30% stop loss for long-term
            analysis_metadata={
                'signal_generation_time': timezone.now().isoformat(),
                'analysis_version': '1.0',
            },
            fundamental_factors=fundamental_factors,
            technical_factors=technical_analysis,
        )
    
    def _create_dca_signal(self, symbol: Symbol, fundamental_score: float,
                          technical_score: float, sentiment_score: float,
                          fundamental_factors: Dict, technical_analysis: Dict) -> SpotTradingSignal:
        """Create dollar-cost averaging signal"""
        
        current_price = self._get_current_price(symbol)
        target_price_6m = current_price * Decimal('1.3') if current_price else None
        target_price_1y = current_price * Decimal('1.8') if current_price else None
        target_price_2y = current_price * Decimal('2.5') if current_price else None
        
        return SpotTradingSignal(
            symbol=symbol,
            signal_category='DCA',
            investment_horizon='LONG_TERM',
            fundamental_score=fundamental_score,
            technical_score=technical_score,
            sentiment_score=sentiment_score,
            recommended_allocation=min(0.05, fundamental_score * 0.08),
            dca_frequency='WEEKLY',
            dca_amount_usd=Decimal('50.00'),
            target_price_6m=target_price_6m,
            target_price_1y=target_price_1y,
            target_price_2y=target_price_2y,
            max_position_size=0.10,
            stop_loss_percentage=0.50,  # 50% stop loss for DCA
            analysis_metadata={
                'signal_generation_time': timezone.now().isoformat(),
                'analysis_version': '1.0',
            },
            fundamental_factors=fundamental_factors,
            technical_factors=technical_analysis,
        )
    
    def _create_distribution_signal(self, symbol: Symbol, fundamental_score: float,
                                  technical_score: float, sentiment_score: float,
                                  fundamental_factors: Dict, technical_analysis: Dict) -> SpotTradingSignal:
        """Create distribution/sell signal"""
        
        return SpotTradingSignal(
            symbol=symbol,
            signal_category='DISTRIBUTION',
            investment_horizon='SHORT_TERM',
            fundamental_score=fundamental_score,
            technical_score=technical_score,
            sentiment_score=sentiment_score,
            recommended_allocation=0.0,
            dca_frequency='MONTHLY',
            max_position_size=0.0,
            stop_loss_percentage=0.20,
            analysis_metadata={
                'signal_generation_time': timezone.now().isoformat(),
                'analysis_version': '1.0',
            },
            fundamental_factors=fundamental_factors,
            technical_factors=technical_analysis,
        )
    
    def _get_current_price(self, symbol: Symbol) -> Optional[Decimal]:
        """Get current price for symbol"""
        try:
            latest_data = MarketData.objects.filter(symbol=symbol).order_by('-timestamp').first()
            if latest_data:
                return latest_data.close_price
            return None
        except Exception as e:
            logger.warning(f"Error getting current price for {symbol.symbol}: {e}")
            return None
