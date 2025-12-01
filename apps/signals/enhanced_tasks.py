"""
Celery tasks for enhanced signal generation
"""

from celery import shared_task
from django.utils import timezone
from datetime import datetime, timedelta
import logging

from apps.signals.enhanced_signal_generation_service import enhanced_signal_service

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def generate_enhanced_signals_task(self):
    """Celery task to generate enhanced signals every 2 hours"""
    try:
        logger.info("Starting enhanced signal generation task")
        
        # Generate signals
        result = enhanced_signal_service.generate_best_signals_for_all_coins()
        
        logger.info(
            f"Enhanced signal generation completed: "
            f"{result['total_signals_generated']} total signals, "
            f"{result['best_signals_selected']} best signals selected, "
            f"{result['processed_symbols']} symbols processed"
        )
        
        # Log best signals
        if result['best_signals']:
            logger.info("Best 5 signals generated:")
            for i, signal in enumerate(result['best_signals'], 1):
                logger.info(
                    f"{i}. {signal['symbol'].symbol} {signal['signal_type']} - "
                    f"Confidence: {signal['confidence_score']:.1%}, "
                    f"Entry: ${signal['entry_price']:.2f}, "
                    f"Target: ${signal['target_price']:.2f}, "
                    f"Stop: ${signal['stop_loss']:.2f}"
                )
        
        return {
            'success': True,
            'total_signals': result['total_signals_generated'],
            'best_signals': result['best_signals_selected'],
            'processed_symbols': result['processed_symbols']
        }
        
    except Exception as e:
        logger.error(f"Error in enhanced signal generation task: {e}")
        
        # Retry the task
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying enhanced signal generation task (attempt {self.request.retries + 1})")
            raise self.retry(countdown=300)  # Retry after 5 minutes
        
        return {
            'success': False,
            'error': str(e)
        }


@shared_task
def cleanup_old_signals_task():
    """Task to clean up old signals and move them to history"""
    try:
        logger.info("Starting signal cleanup task")
        
        from apps.signals.models import TradingSignal
        
        # Find signals older than 48 hours
        cutoff_time = timezone.now() - timedelta(hours=48)
        old_signals = TradingSignal.objects.filter(
            is_valid=True,
            created_at__lt=cutoff_time
        )
        
        archived_count = 0
        for signal in old_signals:
            signal.is_executed = True
            signal.executed_at = timezone.now()
            signal.is_valid = False
            signal.save()
            archived_count += 1
        
        logger.info(f"Archived {archived_count} old signals")
        
        return {
            'success': True,
            'archived_count': archived_count
        }
        
    except Exception as e:
        logger.error(f"Error in signal cleanup task: {e}")
        return {
            'success': False,
            'error': str(e)
        }















































