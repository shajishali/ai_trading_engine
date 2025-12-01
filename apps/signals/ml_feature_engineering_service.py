"""
ML Feature Engineering Service
Combines strategy signals, sentiment, and fundamental news into ML features
"""

import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from django.utils import timezone
from django.db.models import Q, Avg, Max, Min

from apps.trading.models import Symbol
from apps.data.models import MarketData, TechnicalIndicator
from apps.signals.models import TradingSignal
from apps.sentiment.models import SentimentAggregate, CryptoMention, NewsArticle

logger = logging.getLogger(__name__)


class MLFeatureEngineeringService:
    """Service to engineer features from strategy, sentiment, and news data"""
    
    def __init__(self):
        self.lookback_periods = [1, 4, 12, 24, 48, 168]  # 1h, 4h, 12h, 24h, 48h, 1w
    
    def prepare_features_for_symbol(
        self, 
        symbol: Symbol, 
        prediction_horizon_hours: int = 24
    ) -> pd.DataFrame:
        """
        Prepare comprehensive feature set for ML model
        
        Features include:
        1. Technical indicators (RSI, MACD, Moving Averages, etc.)
        2. Strategy signals (from rule-based engine)
        3. Sentiment scores (aggregated sentiment data)
        4. News features (news count, sentiment, impact scores)
        5. Fundamental data (economic indicators, market regime)
        6. Price action features (volatility, momentum, patterns)
        """
        try:
            # Get market data
            end_date = timezone.now()
            start_date = end_date - timedelta(hours=max(self.lookback_periods) + prediction_horizon_hours)
            
            market_data = self._get_market_data(symbol, start_date, end_date)
            if market_data.empty:
                logger.warning(f"No market data for {symbol.symbol}")
                return pd.DataFrame()
            
            # Initialize feature dictionary
            features = {}
            
            # 1. Technical Indicator Features
            features.update(self._extract_technical_features(symbol, market_data))
            
            # 2. Strategy Signal Features (from current rule-based engine)
            features.update(self._extract_strategy_features(symbol, market_data))
            
            # 3. Sentiment Features
            features.update(self._extract_sentiment_features(symbol, end_date))
            
            # 4. News Features
            features.update(self._extract_news_features(symbol, end_date))
            
            # 5. Fundamental/Economic Features
            features.update(self._extract_fundamental_features(symbol, end_date))
            
            # 6. Price Action Features
            features.update(self._extract_price_action_features(market_data))
            
            # 7. Multi-timeframe Features
            features.update(self._extract_multi_timeframe_features(symbol, market_data))
            
            # Convert to DataFrame
            feature_df = pd.DataFrame([features])
            
            return feature_df
            
        except Exception as e:
            logger.error(f"Error preparing features for {symbol.symbol}: {e}", exc_info=True)
            return pd.DataFrame()
    
    def _extract_technical_features(self, symbol: Symbol, market_data: pd.DataFrame) -> Dict:
        """Extract technical indicator features"""
        features = {}
        
        try:
            # RSI
            rsi_indicators = TechnicalIndicator.objects.filter(
                symbol=symbol,
                indicator_type='RSI'
            ).order_by('-timestamp')[:5]
            
            if rsi_indicators.exists():
                rsi_values = [float(ind.value) for ind in rsi_indicators]
                features['rsi_current'] = rsi_values[0] if rsi_values else 50.0
                features['rsi_ma_5'] = np.mean(rsi_values) if rsi_values else 50.0
                features['rsi_trend'] = (rsi_values[0] - rsi_values[-1]) if len(rsi_values) > 1 else 0.0
            else:
                features['rsi_current'] = 50.0
                features['rsi_ma_5'] = 50.0
                features['rsi_trend'] = 0.0
            
            # MACD
            macd_indicators = TechnicalIndicator.objects.filter(
                symbol=symbol,
                indicator_type='MACD'
            ).order_by('-timestamp')[:5]
            
            if macd_indicators.exists():
                macd_values = [float(ind.value) for ind in macd_indicators]
                features['macd_current'] = macd_values[0] if macd_values else 0.0
                signal_value = getattr(macd_indicators[0], 'signal_value', None)
                features['macd_signal'] = float(signal_value) if signal_value else 0.0
                features['macd_histogram'] = features['macd_current'] - features['macd_signal']
            else:
                features['macd_current'] = 0.0
                features['macd_signal'] = 0.0
                features['macd_histogram'] = 0.0
            
            # Moving Averages - Calculate from market data if not in TechnicalIndicator
            if market_data is not None and not market_data.empty:
                current_price = float(market_data.iloc[-1]['close_price'])
                
                for period in [10, 20, 50, 200]:
                    if len(market_data) >= period:
                        ma_value = market_data['close_price'].tail(period).mean()
                        features[f'sma_{period}'] = float(ma_value)
                        features[f'price_vs_sma_{period}'] = (current_price - ma_value) / ma_value * 100
                    else:
                        features[f'sma_{period}'] = current_price
                        features[f'price_vs_sma_{period}'] = 0.0
            
        except Exception as e:
            logger.error(f"Error extracting technical features: {e}", exc_info=True)
        
        return features
    
    def _extract_strategy_features(self, symbol: Symbol, market_data: pd.DataFrame) -> Dict:
        """Extract features from current rule-based strategy engine"""
        features = {}
        
        try:
            from apps.signals.strategy_engine import StrategyEngine
            from apps.signals.timeframe_analysis_service import TimeframeAnalysisService
            
            strategy_engine = StrategyEngine()
            timeframe_service = TimeframeAnalysisService()
            
            if market_data is not None and not market_data.empty:
                current_price = float(market_data.iloc[-1]['close_price'])
                
                # Get strategy evaluation
                strategy_signals = strategy_engine.evaluate_symbol(symbol)
                
                # Count signals by type
                buy_signals = sum(1 for s in strategy_signals if hasattr(s, 'signal_type') and s.signal_type.name in ['BUY', 'STRONG_BUY'])
                sell_signals = sum(1 for s in strategy_signals if hasattr(s, 'signal_type') and s.signal_type.name in ['SELL', 'STRONG_SELL'])
                
                features['strategy_buy_count'] = buy_signals
                features['strategy_sell_count'] = sell_signals
                features['strategy_signal_ratio'] = buy_signals / (sell_signals + 1)
                
                # Average confidence from strategy
                if strategy_signals:
                    confidences = [getattr(s, 'confidence_score', 0.0) for s in strategy_signals if hasattr(s, 'confidence_score')]
                    features['strategy_avg_confidence'] = np.mean(confidences) if confidences else 0.0
                else:
                    features['strategy_avg_confidence'] = 0.0
                
                # Multi-timeframe analysis
                for tf in ['1D', '4H', '1H', '15M']:
                    try:
                        analysis = timeframe_service.analyze_timeframe(symbol, tf, current_price)
                        trend = analysis.get('price_analysis', {}).get('trend', 'NEUTRAL') if isinstance(analysis, dict) else 'NEUTRAL'
                        
                        features[f'{tf}_trend_bullish'] = 1.0 if trend == 'BULLISH' else 0.0
                        features[f'{tf}_trend_bearish'] = 1.0 if trend == 'BEARISH' else 0.0
                        features[f'{tf}_trend_neutral'] = 1.0 if trend == 'NEUTRAL' else 0.0
                    except:
                        features[f'{tf}_trend_bullish'] = 0.0
                        features[f'{tf}_trend_bearish'] = 0.0
                        features[f'{tf}_trend_neutral'] = 1.0
                
        except Exception as e:
            logger.error(f"Error extracting strategy features: {e}", exc_info=True)
        
        return features
    
    def _extract_sentiment_features(self, symbol: Symbol, end_date: datetime) -> Dict:
        """Extract sentiment analysis features"""
        features = {}
        
        try:
            # Get recent sentiment aggregates
            start_date = end_date - timedelta(hours=24)
            
            sentiment_data = SentimentAggregate.objects.filter(
                asset=symbol,
                created_at__gte=start_date,
                created_at__lte=end_date
            ).order_by('-created_at')
            
            if sentiment_data.exists():
                latest = sentiment_data.first()
                
                features['sentiment_score'] = float(latest.combined_sentiment_score) if latest.combined_sentiment_score else 0.0
                
                # Calculate ratios from mentions
                total = latest.total_mentions if latest.total_mentions > 0 else 1
                features['sentiment_positive_ratio'] = float(latest.bullish_mentions) / total if latest.bullish_mentions else 0.0
                features['sentiment_negative_ratio'] = float(latest.bearish_mentions) / total if latest.bearish_mentions else 0.0
                features['sentiment_volume'] = int(latest.total_mentions) if latest.total_mentions else 0
                
                # Sentiment trend
                if sentiment_data.count() > 1:
                    old_sentiment = sentiment_data.last().combined_sentiment_score or 0.0
                    features['sentiment_trend'] = float(latest.combined_sentiment_score) - float(old_sentiment)
                else:
                    features['sentiment_trend'] = 0.0
            else:
                features['sentiment_score'] = 0.0
                features['sentiment_positive_ratio'] = 0.0
                features['sentiment_negative_ratio'] = 0.0
                features['sentiment_volume'] = 0
                features['sentiment_trend'] = 0.0
            
        except Exception as e:
            logger.error(f"Error extracting sentiment features: {e}", exc_info=True)
        
        return features
    
    def _extract_news_features(self, symbol: Symbol, end_date: datetime) -> Dict:
        """Extract news and fundamental features"""
        features = {}
        
        try:
            start_date = end_date - timedelta(hours=24)
            
            # Get news through CryptoMention relationship
            crypto_mentions = CryptoMention.objects.filter(
                asset=symbol,
                news_article__isnull=False,
                created_at__gte=start_date,
                created_at__lte=end_date
            ).select_related('news_article')
            
            features['news_count_24h'] = crypto_mentions.count()
            
            if crypto_mentions.exists():
                # Get news articles from mentions
                news_articles = [mention.news_article for mention in crypto_mentions if mention.news_article]
                
                # News sentiment
                news_sentiments = [float(n.sentiment_score) for n in news_articles if n and n.sentiment_score is not None]
                features['news_avg_sentiment'] = np.mean(news_sentiments) if news_sentiments else 0.0
                features['news_max_sentiment'] = max(news_sentiments) if news_sentiments else 0.0
                features['news_min_sentiment'] = min(news_sentiments) if news_sentiments else 0.0
                
                # Impact scores
                impact_scores = [float(n.impact_score) for n in news_articles if n and n.impact_score is not None]
                features['news_avg_impact'] = np.mean(impact_scores) if impact_scores else 0.0
                features['news_max_impact'] = max(impact_scores) if impact_scores else 0.0
            else:
                features['news_avg_sentiment'] = 0.0
                features['news_max_sentiment'] = 0.0
                features['news_min_sentiment'] = 0.0
                features['news_avg_impact'] = 0.0
                features['news_max_impact'] = 0.0
            
        except Exception as e:
            logger.error(f"Error extracting news features: {e}", exc_info=True)
        
        return features
    
    def _extract_fundamental_features(self, symbol: Symbol, end_date: datetime) -> Dict:
        """Extract fundamental and economic features"""
        features = {}
        
        try:
            # Economic data (if EconomicDataService exists)
            try:
                from apps.data.services import EconomicDataService
                economic_service = EconomicDataService()
                economic_score = economic_service.get_market_impact_score(symbol_country='US')
                features['economic_market_impact'] = float(economic_score) if economic_score else 0.0
            except:
                features['economic_market_impact'] = 0.0
            
            # Market regime (if available)
            try:
                from apps.signals.models import MarketRegime
                regime = MarketRegime.objects.filter(
                    symbol=symbol
                ).order_by('-detected_at').first()
                
                if regime:
                    features['market_regime_bull'] = 1.0 if regime.name == 'BULL' else 0.0
                    features['market_regime_bear'] = 1.0 if regime.name == 'BEAR' else 0.0
                    features['market_regime_sideways'] = 1.0 if regime.name == 'SIDEWAYS' else 0.0
                else:
                    features['market_regime_bull'] = 0.0
                    features['market_regime_bear'] = 0.0
                    features['market_regime_sideways'] = 0.0
            except:
                features['market_regime_bull'] = 0.0
                features['market_regime_bear'] = 0.0
                features['market_regime_sideways'] = 0.0
            
        except Exception as e:
            logger.error(f"Error extracting fundamental features: {e}", exc_info=True)
        
        return features
    
    def _extract_price_action_features(self, market_data: pd.DataFrame) -> Dict:
        """Extract price action features"""
        features = {}
        
        try:
            if market_data is None or market_data.empty:
                return features
            
            # Calculate returns
            market_data = market_data.copy()
            market_data['returns'] = market_data['close_price'].pct_change()
            market_data['log_returns'] = np.log(market_data['close_price'] / market_data['close_price'].shift(1))
            
            # Volatility
            for period in [1, 4, 12, 24]:
                if len(market_data) >= period:
                    returns = market_data['returns'].tail(period)
                    if not returns.empty and returns.std() > 0:
                        features[f'volatility_{period}h'] = float(returns.std() * np.sqrt(period))
                    else:
                        features[f'volatility_{period}h'] = 0.0
                else:
                    features[f'volatility_{period}h'] = 0.0
            
            # Momentum
            for period in [4, 12, 24]:
                if len(market_data) >= period:
                    current_price = float(market_data.iloc[-1]['close_price'])
                    past_price = float(market_data.iloc[-period]['close_price'])
                    if past_price > 0:
                        features[f'momentum_{period}h'] = (current_price - past_price) / past_price * 100
                    else:
                        features[f'momentum_{period}h'] = 0.0
                else:
                    features[f'momentum_{period}h'] = 0.0
            
            # Price position in range
            if len(market_data) >= 24:
                recent_high = float(market_data['high_price'].tail(24).max())
                recent_low = float(market_data['low_price'].tail(24).min())
                current_price = float(market_data.iloc[-1]['close_price'])
                
                if recent_high != recent_low:
                    features['price_position_in_range'] = (current_price - recent_low) / (recent_high - recent_low)
                else:
                    features['price_position_in_range'] = 0.5
            else:
                features['price_position_in_range'] = 0.5
            
            # Volume features
            if 'volume' in market_data.columns:
                volume_ma = market_data['volume'].tail(24).mean()
                features['volume_ma_24'] = float(volume_ma) if not pd.isna(volume_ma) else 0.0
                current_volume = float(market_data.iloc[-1]['volume'])
                if features['volume_ma_24'] > 0:
                    features['volume_ratio'] = current_volume / features['volume_ma_24']
                else:
                    features['volume_ratio'] = 1.0
            else:
                features['volume_ma_24'] = 0.0
                features['volume_ratio'] = 1.0
            
        except Exception as e:
            logger.error(f"Error extracting price action features: {e}", exc_info=True)
        
        return features
    
    def _extract_multi_timeframe_features(self, symbol: Symbol, market_data: pd.DataFrame) -> Dict:
        """Extract multi-timeframe features"""
        features = {}
        
        try:
            if market_data is None or market_data.empty:
                return features
            
            # Add features for different lookback periods
            for period in self.lookback_periods:
                if len(market_data) >= period:
                    period_data = market_data.tail(period)
                    
                    # Returns
                    start_price = float(period_data.iloc[0]['close_price'])
                    end_price = float(period_data.iloc[-1]['close_price'])
                    if start_price > 0:
                        period_return = (end_price - start_price) / start_price
                        features[f'return_{period}h'] = float(period_return)
                    else:
                        features[f'return_{period}h'] = 0.0
                    
                    # Volatility
                    period_returns = period_data['close_price'].pct_change()
                    if not period_returns.empty and period_returns.std() > 0:
                        features[f'volatility_{period}h'] = float(period_returns.std() * np.sqrt(period))
                    else:
                        features[f'volatility_{period}h'] = 0.0
                else:
                    features[f'return_{period}h'] = 0.0
                    features[f'volatility_{period}h'] = 0.0
        
        except Exception as e:
            logger.error(f"Error extracting multi-timeframe features: {e}", exc_info=True)
        
        return features
    
    def _get_market_data(self, symbol: Symbol, start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """Get market data as DataFrame"""
        try:
            market_data = MarketData.objects.filter(
                symbol=symbol,
                timeframe='1h',
                timestamp__gte=start_date,
                timestamp__lte=end_date
            ).order_by('timestamp')
            
            if not market_data.exists():
                return pd.DataFrame()
            
            data_list = []
            for md in market_data:
                data_list.append({
                    'timestamp': md.timestamp,
                    'open_price': float(md.open_price),
                    'high_price': float(md.high_price),
                    'low_price': float(md.low_price),
                    'close_price': float(md.close_price),
                    'volume': float(md.volume) if md.volume else 0.0
                })
            
            df = pd.DataFrame(data_list)
            if not df.empty:
                df.set_index('timestamp', inplace=True)
            
            return df
            
        except Exception as e:
            logger.error(f"Error getting market data: {e}", exc_info=True)
            return pd.DataFrame()

