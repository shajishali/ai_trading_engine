import logging
from datetime import datetime, timedelta, date
from typing import List, Dict, Set
from celery import shared_task
from django.utils import timezone
from django.db.models import Q
from django.core.management import call_command
from django.core.cache import cache

from apps.signals.models import (
    TradingSignal, SignalType, SignalAlert, SignalPerformance,
    MarketRegime, HourlyBestSignal
)
from apps.signals.services import (
    SignalGenerationService, MarketRegimeService, SignalPerformanceService
)
from apps.trading.models import Symbol
from apps.data.models import MarketData

logger = logging.getLogger(__name__)


def _cleanup_non_binance_futures_signals(valid_base_assets: Set[str]) -> Dict:
    """
    Delete TradingSignal rows for crypto symbols that are NOT Binance futures-eligible.
    (Includes: non-Binance coins and spot-only Binance coins.)
    """
    try:
        qs = TradingSignal.objects.filter(symbol__is_crypto_symbol=True).exclude(symbol__symbol__in=valid_base_assets)
        signals_to_delete = qs.count()
        if signals_to_delete == 0:
            return {"signals_deleted": 0}
        qs.delete()
        return {"signals_deleted": signals_to_delete}
    except Exception as e:
        logger.error(f"Failed to cleanup non-Binance-futures signals: {e}", exc_info=True)
        return {"signals_deleted": 0, "error": str(e)}


def _active_signal_symbol_ids() -> List[int]:
    """
    Return symbol IDs that currently have an active signal.
    Must match the "active" definition used by the API (views.py):
    - is_valid=True and (expires_at >= now OR (expires_at is null AND created_at within last 48h))
    """
    now = timezone.now()
    legacy_cutoff = now - timedelta(hours=48)
    return list(
        TradingSignal.objects.filter(is_valid=True, is_executed=False).filter(
            Q(expires_at__gte=now) |
            Q(expires_at__isnull=True, created_at__gte=legacy_cutoff)
        ).values_list("symbol_id", flat=True).distinct()
    )


def _symbol_ids_with_signal_on_date(today: date) -> List[int]:
    """
    Return symbol IDs that already have a signal for the given date.
    Uses signal_date when set (new logic), else created_at date for backward compatibility.
    Enforces: one coin only once per day.
    """
    from django.db.models import Q
    return list(
        TradingSignal.objects.filter(
            Q(signal_date=today) | Q(signal_date__isnull=True, created_at__date=today)
        ).values_list("symbol_id", flat=True).distinct()
    )


def _symbol_ids_with_signal_created_today() -> List[int]:
    """Alias for _symbol_ids_with_signal_on_date(timezone.now().date())."""
    return _symbol_ids_with_signal_on_date(timezone.now().date())


def _count_signals_for_hour(signal_date: date, signal_hour: int) -> int:
    """
    Count hourly-best slots for this (date, hour). Used to skip generation if
    this hour already has 5 (never regenerate). Source of truth: HourlyBestSignal.
    """
    return HourlyBestSignal.objects.filter(
        signal_date=signal_date,
        signal_hour=signal_hour,
    ).count()


def _symbol_ids_in_hourly_best_for_hour(signal_date: date, signal_hour: int) -> Set[int]:
    """Symbol IDs that already have an entry in HourlyBestSignal for this (date, hour)."""
    return set(
        HourlyBestSignal.objects.filter(
            signal_date=signal_date,
            signal_hour=signal_hour,
        ).values_list("symbol_id", flat=True)
    )


def _symbol_ids_with_signal_in_last_hour() -> List[int]:
    """
    Return symbol IDs that have a signal created in the last hour.
    Used so we do not double-generate for the same symbol within the same hour,
    but each new hour we can generate fresh signals (duplicate cleanup keeps latest).
    """
    last_hour = timezone.now() - timedelta(hours=1)
    return list(
        TradingSignal.objects.filter(created_at__gte=last_hour)
        .values_list("symbol_id", flat=True)
        .distinct()
    )


@shared_task
def generate_signals_for_all_symbols():
    """
    HOURLY SIGNAL GENERATION (run every hour via Celery beat).

    STRICT RULES:
    - Exactly 5 signals per hour; one signal = one unique coin.
    - A coin can appear ONLY ONCE per day (DB constraint: unique_signal_per_coin_per_day).
    - Total daily = 24 × 5 = 120 unique coins max.
    - NEVER regenerate: if this (date, hour) already has 5 signals, skip.
    - All times UTC (timezone.now()).

    Flow:
    1. Acquire cache lock for (today, hour) to avoid concurrent runs.
    2. If this hour already has 5 signals (signal_date/signal_hour), return.
    3. Exclude all coins that already have a signal on this date.
    4. Generate candidates from remaining coins, rank by score, take top 5.
    5. Set signal_date=today, signal_hour=hour on the 5; invalidate the rest.
    """
    from datetime import date
    from django.db import transaction, IntegrityError

    now = timezone.now()
    today = now.date()
    hour = now.hour  # 0-23 UTC
    logger.info(f"[Signal Queue] Starting hourly run for date={today} hour={hour} (UTC).")

    # --- Race safety: only one run per (date, hour) ---
    lock_key = f"signal_gen:{today.isoformat()}:{hour}"
    if not cache.add(lock_key, 1, timeout=3600):  # 1 hour TTL
        logger.warning(f"[Signal Queue] Skipping – another process holds lock for {today} {hour}:00.")
        return {
            'total_signals': 0,
            'skipped': 'lock',
            'date': today.isoformat(),
            'hour': hour,
        }

    try:
        # --- Never regenerate: if this hour already has 5, skip ---
        existing_count = _count_signals_for_hour(today, hour)
        if existing_count >= 5:
            logger.info(f"[Signal Queue] Skipping – hour {hour} already has {existing_count} signals for {today}.")
            return {
                'total_signals': 0,
                'skipped': 'hour_full',
                'date': today.isoformat(),
                'hour': hour,
                'existing_count': existing_count,
            }

        # --- Step 0: Binance futures eligibility ---
        valid_base_assets: Set[str] = set()
        try:
            from apps.trading.binance_futures_service import (
                get_binance_usdt_futures_base_assets,
                sync_binance_futures_symbols,
            )
            sync_result = sync_binance_futures_symbols(deactivate_non_futures=True)
            if sync_result.get("status") == "success":
                valid_base_assets = get_binance_usdt_futures_base_assets()
                logger.info(f"[Signal Queue] Binance sync ok: {sync_result.get('futures_base_assets', 0)} base assets.")
            else:
                logger.warning(f"[Signal Queue] Binance sync failed: {sync_result}")
        except Exception as e:
            logger.warning(f"[Signal Queue] Binance eligibility check failed: {e}")

        if valid_base_assets:
            cleanup_stats = _cleanup_non_binance_futures_signals(valid_base_assets)
            if cleanup_stats.get("signals_deleted"):
                logger.warning(f"[Signal Queue] Deleted {cleanup_stats['signals_deleted']} non-Binance-futures signals.")

        # --- Step 1: Exclude coins that already have a signal on this date (any hour) ---
        exclude_symbol_ids = set(_symbol_ids_with_signal_on_date(today))
        # Also exclude symbols that already appear in HourlyBestSignal today (one coin per day, 120 max)
        today_best_symbols = set(
            HourlyBestSignal.objects.filter(signal_date=today).values_list("symbol_id", flat=True)
        )
        exclude_symbol_ids |= today_best_symbols
        logger.info(
            f"[Signal Queue] Step 1 – Excluding {len(exclude_symbol_ids)} symbols that already have a signal today."
        )

        # --- Step 2: Eligible symbols = active, crypto, not already signaled today ---
        active_symbols_qs = Symbol.objects.filter(
            is_active=True,
            is_crypto_symbol=True,
            symbol_type='CRYPTO',
        )
        if valid_base_assets:
            active_symbols_qs = active_symbols_qs.filter(symbol__in=valid_base_assets)
        if exclude_symbol_ids:
            active_symbols_qs = active_symbols_qs.exclude(id__in=exclude_symbol_ids)

        active_symbols = list(active_symbols_qs.order_by('?'))
        eligible_count = len(active_symbols)
        logger.info(f"[Signal Queue] Step 2 – Eligible coins for this hour: {eligible_count} (not yet signaled today).")

        if eligible_count == 0:
            logger.warning("[Signal Queue] No eligible symbols left for today; skipping generation.")
            return {
                'total_signals': 0,
                'symbols_processed': 0,
                'signals_generated': 0,
                'best_signals_selected': 0,
                'binance_futures_filter_active': bool(valid_base_assets),
            }

        signal_service = SignalGenerationService()
        max_signals_per_hour = 5
        max_candidates_to_try = 50  # Cap to avoid long runs; from these we pick best 5
        # Generate one best signal per symbol (candidate), then pick best 5 by quality
        candidates: List[tuple] = []  # (score, signal)

        for symbol in active_symbols[:max_candidates_to_try]:
            try:
                signals = signal_service.generate_signals_for_symbol(symbol)
                if not signals:
                    continue
                best = signals[0]
                score = (float(best.quality_score) if best.quality_score else 0) * 0.5 + (
                    float(best.confidence_score) if best.confidence_score else 0
                ) * 0.5
                candidates.append((score, best))
            except Exception as e:
                logger.error(f"[Signal Queue] Error generating for {symbol.symbol}: {e}")

        # Sort by score descending; then take only symbols not already in this hour's best (no duplicate coin per hour/day)
        candidates.sort(key=lambda x: x[0], reverse=True)
        existing_in_hour = _symbol_ids_in_hourly_best_for_hour(today, hour)
        to_add: List[TradingSignal] = []
        for _, s in candidates:
            if s.symbol_id in existing_in_hour:
                continue
            to_add.append(s)
            existing_in_hour.add(s.symbol_id)
            if len(to_add) >= max_signals_per_hour:
                break
        generated_signals = to_add
        # Only use signals that are already persisted with valid id (do not save unsaved signals;
        # they may have NULL required fields like quality_score and would cause IntegrityError)
        generated_signals = [s for s in generated_signals if s.pk is not None]
        if not generated_signals:
            logger.warning("[Signal Queue] No signals with valid id to store in HourlyBestSignal; skipping.")
            return {
                'total_signals': 0,
                'symbols_processed': eligible_count,
                'signals_generated': 0,
                'best_signals_selected': 0,
                'binance_futures_filter_active': bool(valid_base_assets),
            }
        generated_symbols = [s.symbol.symbol for s in generated_signals]

        # Invalidate any other signals from this run that were not selected (only if already in DB)
        chosen_ids = {s.id for s in generated_signals}
        for _, s in candidates:
            if s.id not in chosen_ids and s.pk is not None:
                s.is_valid = False
                s.save(update_fields=['is_valid'])
                logger.debug(f"[Signal Queue] Invalidated extra signal {s.id} ({s.symbol.symbol}) from this run.")

        # --- Persist: HourlyBestSignal (source of truth for display) + signal_date/signal_hour on TradingSignal ---
        try:
            with transaction.atomic():
                for rank_one_based, s in enumerate(generated_signals, start=1):
                    signal_id = s.pk
                    if signal_id is None:
                        logger.warning(f"[Signal Queue] Skipping HourlyBestSignal for {s.symbol.symbol}: signal has no id.")
                        continue
                    HourlyBestSignal.objects.update_or_create(
                        signal_date=today,
                        signal_hour=hour,
                        symbol_id=s.symbol_id,
                        defaults={
                            "trading_signal_id": signal_id,
                            "rank": rank_one_based,
                            "quality_score": float(s.quality_score) if s.quality_score is not None else None,
                        },
                    )
                    s.signal_date = today
                    s.signal_hour = hour
                    s.save(update_fields=['signal_date', 'signal_hour'])
        except IntegrityError as e:
            logger.warning(f"[Signal Queue] DB constraint error (HourlyBestSignal): {e}. Hour may have been filled by another run.")
            return {
                'total_signals': 0,
                'skipped': 'constraint',
                'date': today.isoformat(),
                'hour': hour,
            }

        logger.info(
            f"[Signal Queue] Step 2 done – Selected best {len(generated_signals)} signals for this hour (HourlyBestSignal). "
            f"Symbols: {generated_symbols}"
        )

        # CRITICAL: Clean up any duplicates that might have been created due to race conditions
        # This ensures only the latest signal per symbol+type remains valid
        try:
            from django.db.models import Count, Max
            
            with transaction.atomic():
                # Find all symbol+type combinations with multiple valid signals
                duplicates = TradingSignal.objects.values('symbol', 'signal_type').annotate(
                    count=Count('id')
                ).filter(count__gt=1, is_valid=True, is_executed=False)
                
                cleaned_count = 0
                for dup in duplicates:
                    symbol_id = dup['symbol']
                    signal_type_id = dup['signal_type']
                    
                    # Get all valid signals, keep only the latest
                    all_signals = TradingSignal.objects.filter(
                        symbol_id=symbol_id,
                        signal_type_id=signal_type_id,
                        is_valid=True,
                        is_executed=False
                    ).order_by('-created_at', '-id')
                    
                    if all_signals.count() > 1:
                        latest = all_signals.first()
                        others = all_signals.exclude(id=latest.id)
                        count = others.update(is_valid=False)
                        cleaned_count += count
                
                if cleaned_count > 0:
                    logger.warning(f"Cleaned up {cleaned_count} duplicate signals after generation")
        except Exception as e:
            logger.error(f"Error cleaning up duplicates: {e}")
        
        # IMPORTANT: invalidate cached signals API responses so the UI updates immediately.
        try:
            cache_keys_to_clear = [
                "signal_statistics",
                "signals_api_None_None_true_50",
                "signals_api_None_None_True_50",
            ]
            cleared = 0
            for key in cache_keys_to_clear:
                if cache.get(key) is not None:
                    cache.delete(key)
                    cleared += 1

            # Also clear a few common variants (mirrors clear-cache endpoint logic)
            for symbol_val in [None, 'None']:
                for signal_type_val in [None, 'None']:
                    for is_valid_val in [True, 'True', 'true']:
                        for limit_val in [50, '50']:
                            cache_key = f"signals_api_{symbol_val}_{signal_type_val}_{is_valid_val}_{limit_val}"
                            if cache.get(cache_key) is not None:
                                cache.delete(cache_key)
                                cleared += 1

            logger.info(f"Invalidated {cleared} signal cache key(s) after generation")
        except Exception as e:
            logger.warning(f"Failed to invalidate signals cache after generation: {e}")

        return {
            'total_signals': len(generated_signals),
            'symbols_processed': eligible_count,
            'signals_generated': len(generated_signals),
            'best_signals_selected': len(generated_signals),
            'binance_futures_filter_active': bool(valid_base_assets),
        }
    finally:
        cache.delete(lock_key)


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
    # Expired if:
    # - expires_at is in the past, OR
    # - expires_at is NULL (legacy/sample rows) AND created_at older than the default expiry window.
    #   (SignalGenerationService default expiry is 48 hours.)
    legacy_expiry_cutoff = now - timedelta(hours=48)
    expired_signals = TradingSignal.objects.filter(
        is_valid=True
    ).filter(
        Q(expires_at__lt=now) |
        Q(expires_at__isnull=True, created_at__lt=legacy_expiry_cutoff)
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


@shared_task
def save_daily_best_signals_task(target_date_str=None, limit=10):
    """
    Save daily best 10 signals for a specific date (defaults to today).
    Runs at 23:55 UTC so the "Best Signals by date" view can show them.
    """
    try:
        if target_date_str:
            target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
        else:
            # Default to today (end of day task runs at 23:55)
            target_date = timezone.now().date()
        
        logger.info(f"Starting to save daily best {limit} signals for {target_date}...")
        
        # Get all signals created that day (24*5 pool), ordered by quality
        day_signals = TradingSignal.objects.filter(
            created_at__date=target_date,
            is_valid=True
        ).select_related('symbol', 'signal_type').order_by('-quality_score', '-confidence_score', '-risk_reward_ratio')
        
        logger.info(f"Found {day_signals.count()} signals for {target_date}")
        
        # One per symbol+type, top 10 by quality (final best 10 for the day)
        seen = set()
        best_signals = []
        for signal in day_signals:
            key = (signal.symbol_id, signal.signal_type_id)
            if key not in seen and len(best_signals) < limit:
                seen.add(key)
                best_signals.append(signal)
        
        # Clear previous best signals for this date
        TradingSignal.objects.filter(
            best_of_day_date=target_date,
            is_best_of_day=True
        ).update(is_best_of_day=False, best_of_day_date=None, best_of_day_rank=None)
        
        # Mark the best 10 signals
        saved_count = 0
        for rank, signal in enumerate(best_signals, start=1):
            signal.is_best_of_day = True
            signal.best_of_day_date = target_date
            signal.best_of_day_rank = rank
            signal.save()
            saved_count += 1
            logger.info(f"Marked {signal.symbol.symbol} + {signal.signal_type.name} as best signal #{rank} for {target_date}")
        
        logger.info(f"Successfully saved {saved_count} daily best signals for {target_date}")
        
        return {
            'success': True,
            'date': target_date.isoformat(),
            'limit': limit,
            'saved_count': saved_count
        }
        
    except Exception as e:
        logger.error(f"Error saving daily best signals: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e)
        }
