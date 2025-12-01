"""
Unified Signal Generation Task
Combines strategy, news, and sentiment to generate the 10 best signals
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict
from celery import shared_task
from django.utils import timezone
from django.db.models import Q, Avg

from apps.signals.models import TradingSignal, SignalType
from apps.signals.services import SignalGenerationService
from apps.trading.models import Symbol
from apps.data.models import MarketData

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def generate_unified_signals_task(self):
    """
    Unified task to generate 10 best signals combining:
    - Strategy (technical analysis)
    - Fundamental news
    - Market sentiment
    """
    try:
        logger.info("="*60)
        logger.info("Starting unified signal generation (strategy + news + sentiment)")
        logger.info("="*60)
        
        signal_service = SignalGenerationService()
        active_symbols = Symbol.objects.filter(
            is_active=True,
            is_crypto_symbol=True
        )
        
        logger.info(f"Processing {active_symbols.count()} active crypto symbols")
        
        all_signals = []
        processed_count = 0
        
        for symbol in active_symbols:
            try:
                # Generate signals using service (includes strategy, news, sentiment)
                signals = signal_service.generate_signals_for_symbol(symbol)
                all_signals.extend(signals)
                processed_count += 1
                
                if processed_count % 50 == 0:
                    logger.info(f"Processed {processed_count}/{active_symbols.count()} symbols")
                    
            except Exception as e:
                logger.error(f"Error generating signals for {symbol.symbol}: {e}")
                continue
        
        logger.info(f"Generated {len(all_signals)} total signals from {processed_count} symbols")
        
        # Select top 10 signals based on combined score
        best_signals = _select_top_10_signals(all_signals)
        
        # Save signals
        saved_count = 0
        for signal in best_signals:
            try:
                signal.save()
                saved_count += 1
                logger.info(
                    f"Saved signal #{saved_count}: {signal.symbol.symbol} - "
                    f"{signal.signal_type.name} - Confidence: {signal.confidence_score:.2%}"
                )
            except Exception as e:
                logger.error(f"Error saving signal: {e}")
        
        logger.info("="*60)
        logger.info(
            f"Unified signal generation completed: "
            f"{len(all_signals)} total signals, "
            f"{len(best_signals)} best signals selected, "
            f"{saved_count} signals saved"
        )
        logger.info("="*60)
        
        return {
            'success': True,
            'total_signals': len(all_signals),
            'best_signals': len(best_signals),
            'saved_signals': saved_count,
            'processed_symbols': processed_count
        }
        
    except Exception as e:
        logger.error(f"Unified signal generation failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise self.retry(countdown=60 * (2 ** self.request.retries))


def _select_top_10_signals(signals: List[TradingSignal]) -> List[TradingSignal]:
    """Select top 10 signals based on combined score (strategy + news + sentiment)"""
    if not signals:
        return []
    
    # Calculate combined score for each signal
    scored_signals = []
    for signal in signals:
        # Strategy confidence (40% weight)
        strategy_score = signal.confidence_score * 0.4
        
        # Quality score (30% weight)
        quality_score = (signal.quality_score if hasattr(signal, 'quality_score') and signal.quality_score else 0.5) * 0.3
        
        # News score (15% weight)
        news_score = _get_news_score_for_signal(signal) * 0.15
        
        # Sentiment score (15% weight)
        sentiment_score = _get_sentiment_score_for_signal(signal) * 0.15
        
        # Combined score
        combined_score = strategy_score + quality_score + news_score + sentiment_score
        
        # Risk-reward bonus (up to 10% bonus)
        rr_bonus = min(0.1, (signal.risk_reward_ratio or 0) / 10)
        
        final_score = combined_score + rr_bonus
        
        scored_signals.append((final_score, signal))
    
    # Sort by combined score
    scored_signals.sort(key=lambda x: x[0], reverse=True)
    
    # Return top 10 signals
    return [signal for _, signal in scored_signals[:10]]


def _get_news_score_for_signal(signal: TradingSignal) -> float:
    """Get news sentiment score for a signal's symbol"""
    try:
        from apps.sentiment.models import CryptoMention, NewsArticle
        
        # Get recent news mentions (last 24 hours)
        recent_mentions = CryptoMention.objects.filter(
            asset=signal.symbol,
            news_article__published_at__gte=timezone.now() - timedelta(hours=24),
            mention_type='news'
        )
        
        if not recent_mentions.exists():
            return 0.5  # Neutral if no news
        
        # Calculate weighted sentiment score
        total_score = 0.0
        total_weight = 0.0
        
        for mention in recent_mentions:
            hours_ago = (timezone.now() - mention.news_article.published_at).total_seconds() / 3600
            recency_weight = max(0, 1 - (hours_ago / 24))  # Decay over 24 hours
            weight = mention.confidence_score * recency_weight
            
            # Convert sentiment to score (-1 to 1, then normalize to 0-1)
            sentiment_value = mention.sentiment_score if mention.sentiment_label == 'POSITIVE' else -mention.sentiment_score
            normalized_sentiment = (sentiment_value + 1) / 2
            
            total_score += normalized_sentiment * weight
            total_weight += weight
        
        return total_score / total_weight if total_weight > 0 else 0.5
        
    except Exception as e:
        logger.debug(f"Error getting news score for {signal.symbol.symbol}: {e}")
        return 0.5


def _get_sentiment_score_for_signal(signal: TradingSignal) -> float:
    """Get market sentiment score for a signal's symbol"""
    try:
        from apps.sentiment.models import SentimentAggregate
        
        # Get recent sentiment aggregate (last 2 hours)
        recent_aggregate = SentimentAggregate.objects.filter(
            asset=signal.symbol,
            timeframe='1h',
            created_at__gte=timezone.now() - timedelta(hours=2)
        ).order_by('-created_at').first()
        
        if recent_aggregate:
            # Convert sentiment score (-1 to 1) to normalized score (0 to 1)
            normalized_score = (recent_aggregate.aggregate_sentiment_score + 1) / 2
            return normalized_score
        
        return 0.5  # Neutral if no sentiment data
        
    except Exception as e:
        logger.debug(f"Error getting sentiment score for {signal.symbol.symbol}: {e}")
        return 0.5

