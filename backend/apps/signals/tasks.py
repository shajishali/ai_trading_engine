import logging
from datetime import datetime, timedelta
from typing import List, Dict
from celery import shared_task
from django.utils import timezone
from django.db.models import Q

from apps.signals.models import (
    TradingSignal, SignalType, SignalAlert, SignalPerformance,
    MarketRegime
)
from apps.signals.services import (
    SignalGenerationService, MarketRegimeService, SignalPerformanceService
)
from apps.trading.models import Symbol
from apps.data.models import MarketData

logger = logging.getLogger(__name__)


@shared_task
def generate_signals_for_all_symbols():
    """Generate signals for all active symbols and select top 10 best signals"""
    logger.info("Starting signal generation for all symbols...")
    
    signal_service = SignalGenerationService()
    active_symbols = Symbol.objects.filter(is_active=True, is_crypto_symbol=True)
    
    total_signals = 0
    generated_signals = []
    
    for symbol in active_symbols:
        try:
            signals = signal_service.generate_signals_for_symbol(symbol)
            generated_signals.extend(signals)
            total_signals += len(signals)
            
            if len(signals) > 0:
                logger.debug(f"Generated {len(signals)} signals for {symbol.symbol}")
            
        except Exception as e:
            logger.error(f"Error generating signals for {symbol.symbol}: {e}")
    
    logger.info(f"Signal generation completed. Total signals: {total_signals}")
    
    # Select top 10 best signals
    if generated_signals:
        from apps.signals.unified_signal_task import _select_top_10_signals
        best_signals = _select_top_10_signals(generated_signals)
        
        # Save top 10 signals
        saved_count = 0
        for signal in best_signals:
            try:
                signal.save()
                saved_count += 1
            except Exception as e:
                logger.error(f"Error saving signal: {e}")
        
        logger.info(f"Selected and saved top {saved_count} best signals")
        
        return {
            'total_signals': total_signals,
            'symbols_processed': active_symbols.count(),
            'signals_generated': len(generated_signals),
            'best_signals_selected': saved_count
        }
    
    return {
        'total_signals': total_signals,
        'symbols_processed': active_symbols.count(),
        'signals_generated': 0,
        'best_signals_selected': 0
    }


@shared_task
def generate_signals_for_symbol(symbol_id: int):
    """Generate signals for a specific symbol"""
    try:
        symbol = Symbol.objects.get(id=symbol_id)
        signal_service = SignalGenerationService()
        
        signals = signal_service.generate_signals_for_symbol(symbol)
        
        logger.info(f"Generated {len(signals)} signals for {symbol.symbol}")
        
        return {
            'symbol': symbol.symbol,
            'signals_generated': len(signals),
            'signals': [signal.id for signal in signals]
        }
        
    except Symbol.DoesNotExist:
        logger.error(f"Symbol with id {symbol_id} not found")
        return {'error': 'Symbol not found'}
    except Exception as e:
        logger.error(f"Error generating signals for symbol {symbol_id}: {e}")
        return {'error': str(e)}


@shared_task
def detect_market_regimes():
    """Detect market regimes for all active symbols"""
    logger.info("Starting market regime detection...")
    
    regime_service = MarketRegimeService()
    active_symbols = Symbol.objects.filter(is_active=True)
    
    regimes_detected = 0
    
    for symbol in active_symbols:
        try:
            regime = regime_service.detect_market_regime(symbol)
            if regime:
                regimes_detected += 1
                logger.info(f"Detected {regime.name} regime for {symbol.symbol}")
            
        except Exception as e:
            logger.error(f"Error detecting regime for {symbol.symbol}: {e}")
    
    logger.info(f"Market regime detection completed. Regimes detected: {regimes_detected}")
    return {
        'regimes_detected': regimes_detected,
        'symbols_processed': active_symbols.count()
    }


@shared_task
def monitor_signal_performance():
    """Monitor and update signal performance metrics"""
    logger.info("Starting signal performance monitoring...")
    
    performance_service = SignalPerformanceService()
    
    # Calculate performance for different timeframes
    timeframes = ['1H', '4H', '1D', '1W', '1M']
    performance_metrics = {}
    
    for timeframe in timeframes:
        try:
            metrics = performance_service.calculate_performance_metrics(timeframe)
            performance_metrics[timeframe] = metrics
            
            logger.info(f"{timeframe} performance - Win rate: {metrics['win_rate']:.2%}, "
                       f"Profit factor: {metrics['profit_factor']:.2f}")
            
        except Exception as e:
            logger.error(f"Error calculating {timeframe} performance: {e}")
    
    return {
        'performance_metrics': performance_metrics,
        'timeframes_processed': len(timeframes)
    }


@shared_task
def cleanup_expired_signals():
    """Clean up expired signals and update their status"""
    logger.info("Starting expired signal cleanup...")
    
    now = timezone.now()
    expired_signals = TradingSignal.objects.filter(
        expires_at__lt=now,
        is_valid=True
    )
    
    expired_count = expired_signals.count()
    
    # Mark signals as invalid
    expired_signals.update(is_valid=False)
    
    # Create alerts for expired signals
    alerts_created = 0
    for signal in expired_signals:
        try:
            SignalAlert.objects.create(
                alert_type='SIGNAL_EXPIRED',
                priority='MEDIUM',
                title=f"Signal Expired for {signal.symbol.symbol}",
                message=f"{signal.signal_type.name} signal has expired",
                signal=signal
            )
            alerts_created += 1
        except Exception as e:
            logger.error(f"Error creating expired signal alert: {e}")
    
    logger.info(f"Expired signal cleanup completed. Expired: {expired_count}, Alerts: {alerts_created}")
    return {
        'expired_signals': expired_count,
        'alerts_created': alerts_created
    }


@shared_task
def validate_signal_quality():
    """Validate signal quality and create alerts for low-quality signals"""
    logger.info("Starting signal quality validation...")
    
    # Get recent signals
    recent_signals = TradingSignal.objects.filter(
        created_at__gte=timezone.now() - timedelta(hours=1),
        is_valid=True
    )
    
    low_quality_signals = []
    alerts_created = 0
    
    for signal in recent_signals:
        try:
            # Check quality criteria
            quality_issues = []
            
            if signal.confidence_score < 0.7:
                quality_issues.append("Low confidence")
            
            if signal.risk_reward_ratio and signal.risk_reward_ratio < 3.0:
                quality_issues.append("Poor risk-reward ratio")
            
            if signal.quality_score < 0.6:
                quality_issues.append("Low quality score")
            
            # Create alert for low-quality signals
            if quality_issues:
                SignalAlert.objects.create(
                    alert_type='PERFORMANCE_ALERT',
                    priority='HIGH',
                    title=f"Low Quality Signal for {signal.symbol.symbol}",
                    message=f"Quality issues: {', '.join(quality_issues)}",
                    signal=signal
                )
                alerts_created += 1
                low_quality_signals.append(signal.id)
            
        except Exception as e:
            logger.error(f"Error validating signal {signal.id}: {e}")
    
    logger.info(f"Signal quality validation completed. Low quality: {len(low_quality_signals)}, Alerts: {alerts_created}")
    return {
        'signals_checked': recent_signals.count(),
        'low_quality_signals': len(low_quality_signals),
        'alerts_created': alerts_created
    }


@shared_task
def update_signal_statistics():
    """Update signal statistics and metrics"""
    logger.info("Starting signal statistics update...")
    
    try:
        # Calculate signal statistics
        total_signals = TradingSignal.objects.count()
        active_signals = TradingSignal.objects.filter(is_valid=True).count()
        executed_signals = TradingSignal.objects.filter(is_executed=True).count()
        profitable_signals = TradingSignal.objects.filter(
            is_executed=True, is_profitable=True
        ).count()
        
        # Calculate average metrics
        avg_confidence = TradingSignal.objects.filter(
            created_at__gte=timezone.now() - timedelta(days=7)
        ).aggregate(avg_confidence=Q('confidence_score'))['avg_confidence'] or 0.0
        
        avg_quality = TradingSignal.objects.filter(
            created_at__gte=timezone.now() - timedelta(days=7)
        ).aggregate(avg_quality=Q('quality_score'))['avg_quality'] or 0.0
        
        # Calculate win rate
        win_rate = profitable_signals / executed_signals if executed_signals > 0 else 0.0
        
        statistics = {
            'total_signals': total_signals,
            'active_signals': active_signals,
            'executed_signals': executed_signals,
            'profitable_signals': profitable_signals,
            'win_rate': win_rate,
            'avg_confidence': avg_confidence,
            'avg_quality': avg_quality
        }
        
        logger.info(f"Signal statistics updated - Win rate: {win_rate:.2%}, "
                   f"Active signals: {active_signals}")
        
        return statistics
        
    except Exception as e:
        logger.error(f"Error updating signal statistics: {e}")
        return {'error': str(e)}


@shared_task
def monitor_signal_alerts():
    """Monitor and process signal alerts"""
    logger.info("Starting signal alert monitoring...")
    
    try:
        # Get unread alerts
        unread_alerts = SignalAlert.objects.filter(is_read=False)
        
        # Count alerts by priority
        critical_alerts = unread_alerts.filter(priority='CRITICAL').count()
        high_alerts = unread_alerts.filter(priority='HIGH').count()
        medium_alerts = unread_alerts.filter(priority='MEDIUM').count()
        low_alerts = unread_alerts.filter(priority='LOW').count()
        
        # Create system alert if too many critical alerts
        if critical_alerts > 5:
            SignalAlert.objects.create(
                alert_type='SYSTEM_ALERT',
                priority='CRITICAL',
                title="High Number of Critical Alerts",
                message=f"There are {critical_alerts} critical alerts requiring attention"
            )
        
        alert_summary = {
            'total_unread': unread_alerts.count(),
            'critical': critical_alerts,
            'high': high_alerts,
            'medium': medium_alerts,
            'low': low_alerts
        }
        
        logger.info(f"Alert monitoring completed - Unread: {unread_alerts.count()}, "
                   f"Critical: {critical_alerts}")
        
        return alert_summary
        
    except Exception as e:
        logger.error(f"Error monitoring signal alerts: {e}")
        return {'error': str(e)}


@shared_task
def backtest_signals():
    """Backtest signal performance using historical data"""
    logger.info("Starting signal backtesting...")
    
    try:
        # Get signals from the last 30 days
        start_date = timezone.now() - timedelta(days=30)
        test_signals = TradingSignal.objects.filter(
            created_at__gte=start_date,
            is_executed=True
        )
        
        if not test_signals.exists():
            logger.info("No executed signals found for backtesting")
            return {'signals_tested': 0}
        
        # Calculate backtest metrics
        total_signals = test_signals.count()
        profitable_signals = test_signals.filter(is_profitable=True).count()
        win_rate = profitable_signals / total_signals if total_signals > 0 else 0.0
        
        # Calculate profit factor
        total_profit = test_signals.filter(is_profitable=True).aggregate(
            total_profit=Q('profit_loss')
        )['total_profit'] or 0.0
        
        total_loss = abs(test_signals.filter(is_profitable=False).aggregate(
            total_loss=Q('profit_loss')
        )['total_loss'] or 0.0)
        
        profit_factor = total_profit / total_loss if total_loss > 0 else 0.0
        
        # Calculate average metrics
        avg_confidence = test_signals.aggregate(
            avg_confidence=Q('confidence_score')
        )['avg_confidence'] or 0.0
        
        avg_quality = test_signals.aggregate(
            avg_quality=Q('quality_score')
        )['avg_quality'] or 0.0
        
        backtest_results = {
            'signals_tested': total_signals,
            'profitable_signals': profitable_signals,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'avg_confidence': avg_confidence,
            'avg_quality': avg_quality
        }
        
        logger.info(f"Backtesting completed - Win rate: {win_rate:.2%}, "
                   f"Profit factor: {profit_factor:.2f}")
        
        return backtest_results
        
    except Exception as e:
        logger.error(f"Error during signal backtesting: {e}")
        return {'error': str(e)}


@shared_task
def optimize_signal_parameters():
    """Optimize signal generation parameters based on performance"""
    logger.info("Starting signal parameter optimization...")
    
    try:
        # Get recent performance data
        recent_performance = SignalPerformance.objects.filter(
            created_at__gte=timezone.now() - timedelta(days=7)
        ).order_by('-created_at')
        
        if not recent_performance.exists():
            logger.info("No recent performance data for optimization")
            return {'optimization_applied': False}
        
        # Analyze performance trends
        avg_win_rate = recent_performance.aggregate(
            avg_win_rate=Q('win_rate')
        )['avg_win_rate'] or 0.0
        
        avg_profit_factor = recent_performance.aggregate(
            avg_profit_factor=Q('profit_factor')
        )['avg_profit_factor'] or 0.0
        
        # Adjust parameters based on performance
        adjustments = []
        
        if avg_win_rate < 0.7:  # Below target win rate
            adjustments.append("Increase confidence threshold")
        
        if avg_profit_factor < 1.5:  # Below target profit factor
            adjustments.append("Increase risk-reward ratio requirement")
        
        if adjustments:
            logger.info(f"Parameter optimization suggested: {', '.join(adjustments)}")
            return {
                'optimization_applied': True,
                'adjustments': adjustments,
                'avg_win_rate': avg_win_rate,
                'avg_profit_factor': avg_profit_factor
            }
        else:
            logger.info("No parameter adjustments needed")
            return {
                'optimization_applied': False,
                'avg_win_rate': avg_win_rate,
                'avg_profit_factor': avg_profit_factor
            }
        
    except Exception as e:
        logger.error(f"Error during parameter optimization: {e}")
        return {'error': str(e)}


@shared_task
def signal_health_check():
    """Health check for signal generation system"""
    logger.info("Starting signal generation health check...")
    
    try:
        # Check signal generation frequency
        recent_signals = TradingSignal.objects.filter(
            created_at__gte=timezone.now() - timedelta(hours=1)
        ).count()
        
        # Check alert backlog
        unread_alerts = SignalAlert.objects.filter(is_read=False).count()
        
        # Check system health
        health_score = 100
        issues = []
        
        if recent_signals == 0:
            health_score -= 30
            issues.append("No signals generated in the last hour")
        
        if unread_alerts > 50:
            health_score -= 20
            issues.append(f"High alert backlog: {unread_alerts}")
        
        if unread_alerts > 100:
            health_score -= 30
            issues.append("Critical alert backlog")
        
        # Check for expired signals
        expired_signals = TradingSignal.objects.filter(
            expires_at__lt=timezone.now(),
            is_valid=True
        ).count()
        
        if expired_signals > 10:
            health_score -= 15
            issues.append(f"High number of expired signals: {expired_signals}")
        
        health_status = 'healthy' if health_score >= 80 else 'warning' if health_score >= 50 else 'critical'
        
        health_metrics = {
            'health_score': health_score,
            'health_status': health_status,
            'issues': issues,
            'recent_signals': recent_signals,
            'unread_alerts': unread_alerts,
            'expired_signals': expired_signals
        }
        
        logger.info(f"Signal health check completed - Score: {health_score}, Status: {health_status}")
        
        return health_metrics
        
    except Exception as e:
        logger.error(f"Error during signal health check: {e}")
        return {'error': str(e)}
