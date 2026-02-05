import logging
from datetime import datetime, timedelta
from typing import Dict, List
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views import View
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Avg, Count, Prefetch
from django.utils import timezone
from django.core.cache import cache
from django.views.decorators.cache import cache_page
from django.utils.decorators import method_decorator
import json
from django.conf import settings

from apps.signals.models import (
    TradingSignal, SignalType, SignalFactor, SignalAlert,
    MarketRegime, SignalPerformance, HourlyBestSignal
)
from apps.signals.services import (
    SignalGenerationService, MarketRegimeService, SignalPerformanceService
)
from apps.trading.models import Symbol

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
@method_decorator(login_required, name='dispatch')
class SignalAPIView(View):
    """API view for signal operations"""
    
    def get(self, request):
        """Get signals with optional filtering - with retry logic for database locks"""
        import time
        from django.db import OperationalError
        
        # Get query parameters
        symbol = request.GET.get('symbol')
        signal_type = request.GET.get('signal_type')
        is_valid = request.GET.get('is_valid', 'true').lower() == 'true'
        limit = int(request.GET.get('limit', 50))
        mode = request.GET.get('mode', '').strip().lower()

        # Main dashboard: 5 signals for current clock hour from today's pool (no cache)
        if mode == 'top5':
            return self._get_top5_signals_last_hour(request)

        # Create cache key based on parameters
        cache_key = f"signals_api_{symbol}_{signal_type}_{is_valid}_{limit}"
        cached_data = cache.get(cache_key)
        
        # Only return cached data if it's not empty (empty cache might be stale)
        # Always check database if cache is empty or if we need fresh data
        if cached_data and cached_data.get('count', 0) > 0:
            logger.info(f"Returning cached data for key: {cache_key} with {cached_data.get('count', 0)} signals")
            # Try to get fresh data in background, but return cached immediately
            try:
                # Attempt to refresh cache in background (non-blocking)
                self._refresh_cache_async(cache_key, symbol, signal_type, is_valid, limit)
            except:
                pass  # Ignore errors in background refresh
            return JsonResponse(cached_data)
        elif cached_data and cached_data.get('count', 0) == 0:
            # Cache has empty result - clear it and check database
            logger.warning(f"Cache has empty result for key: {cache_key}, clearing cache and checking database")
            cache.delete(cache_key)
        
        # If no cache, try to get fresh data with retry logic
        max_retries = 3
        retry_delay = 0.5
        
        for attempt in range(max_retries):
            try:
                # Ensure database connection is alive before querying
                from django.db import connection, connections
                try:
                    # Test connection with a simple query
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT 1")
                        cursor.fetchone()
                except Exception as conn_error:
                    error_msg = str(conn_error)
                    logger.error(f"Database connection test failed (attempt {attempt + 1}/{max_retries}): {error_msg}")
                    
                    # Close all database connections
                    try:
                        connections.close_all()
                    except:
                        pass
                    
                    if attempt < max_retries - 1:
                        logger.info(f"Retrying database connection in {retry_delay}s...")
                        time.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                    else:
                        # Return cached data if available
                        stale_cache = cache.get(cache_key)
                        if stale_cache:
                            logger.info("Returning stale cached data due to connection failure")
                            return JsonResponse(stale_cache)
                        # Log the actual error for debugging with full details
                        logger.error(
                            f"Database connection failed after {max_retries} attempts: {error_msg}",
                            exc_info=True,
                            extra={
                                'error_type': type(conn_error).__name__,
                                'error_message': error_msg,
                                'attempt': attempt + 1,
                                'max_retries': max_retries
                            }
                        )
                        # Return error response instead of raising
                        return JsonResponse({
                            'success': False,
                            'error': 'Database temporarily unavailable. Please try again in a moment.',
                            'signals': [],
                            'count': 0,
                            'error_code': 'DB_CONNECTION_FAILED'
                        }, status=503)
                
                # Build optimized query with select_related and prefetch_related
                # Use iterator() to avoid loading all into memory and reduce lock time
                queryset = TradingSignal.objects.select_related(
                    'symbol', 'signal_type'
                )
                
                if symbol:
                    queryset = queryset.filter(symbol__symbol__iexact=symbol)
                
                if signal_type:
                    queryset = queryset.filter(signal_type__name=signal_type)
                
                # If no valid signals found and we're looking for valid ones, 
                # show recent signals (within last 48 hours) even if invalid/executed
                if is_valid:
                    # Failsafe: treat signals with expires_at in the past as not active
                    valid_signals = queryset.filter(
                        is_valid=True
                    ).filter(
                        Q(expires_at__gte=timezone.now()) |
                        # Legacy/sample signals might have NULL expires_at; treat them as active
                        # only within the default expiry window (48h).
                        Q(expires_at__isnull=True, created_at__gte=timezone.now() - timedelta(hours=48))
                    )
                    valid_count = valid_signals.count()
                    
                    if valid_count == 0:
                        # No valid signals - return empty result instead of showing invalid/old signals
                        logger.info("No valid signals found, returning empty result")
                        queryset = TradingSignal.objects.none()  # Return empty queryset
                    else:
                        # Use valid signals queryset directly
                        queryset = valid_signals
                else:
                    queryset = queryset.filter(is_valid=is_valid)
                
                # Get signals ordered by created_at
                signals_queryset = queryset.order_by('-created_at', '-id')
                
                # IMPORTANT: Filter out duplicates - keep only the latest signal per symbol+type combination
                # This ensures we don't show duplicate signals even if they exist in the database
                seen_combinations = set()
                unique_signals = []
                for signal in signals_queryset:
                    combo_key = (signal.symbol.id, signal.signal_type.id)
                    if combo_key not in seen_combinations:
                        seen_combinations.add(combo_key)
                        unique_signals.append(signal)
                        if len(unique_signals) >= limit:
                            break
                
                signals = unique_signals
                
                # Log query results for debugging
                logger.info(f"Query executed: symbol={symbol}, signal_type={signal_type}, is_valid={is_valid}, limit={limit}")
                logger.info(f"Found {len(signals)} unique signals (after deduplication)")
                if len(signals) == 0:
                    # Check total signals in database for debugging
                    total_all = TradingSignal.objects.count()
                    total_valid = TradingSignal.objects.filter(is_valid=True).count()
                    total_invalid = TradingSignal.objects.filter(is_valid=False).count()
                    logger.warning(f"No signals found with filters. Total signals in DB: all={total_all}, valid={total_valid}, invalid={total_invalid}")
                
                # Get synchronized prices for all symbols
                from apps.signals.price_sync_service import price_sync_service
                
                # Serialize signals with optimized data access and synchronized prices
                signal_data = []
                for signal in signals:
                    symbol = signal.symbol.symbol
                    
                    # Get synchronized price data for this symbol
                    sync_prices = price_sync_service.get_synchronized_prices(symbol)
                    
                    current_price = sync_prices.get('current_price')
                    price_change_24h = sync_prices.get('price_change_24h')
                    price_discrepancy = sync_prices.get('price_discrepancy_percent', 0)
                    price_status = sync_prices.get('price_status', 'unknown')
                    price_alert = sync_prices.get('price_alert')
                    
                    signal_data.append({
                        'id': signal.id,
                        'symbol': symbol,
                        'signal_type': signal.signal_type.name,
                        'strength': signal.strength,
                        'confidence_score': signal.confidence_score,
                        'confidence_level': signal.confidence_level,
                        'entry_price': float(signal.entry_price) if signal.entry_price else None,
                        'target_price': float(signal.target_price) if signal.target_price else None,
                        'stop_loss': float(signal.stop_loss) if signal.stop_loss else None,
                        'current_price': current_price,  # Synchronized current price
                        'price_change_24h': price_change_24h,  # 24h price change
                        'price_discrepancy_percent': price_discrepancy,  # Price difference from entry
                        'price_status': price_status,  # Price reliability status
                        'price_alert': price_alert,  # Price discrepancy alerts
                        'risk_reward_ratio': signal.risk_reward_ratio,
                        'quality_score': signal.quality_score,
                        'is_valid': signal.is_valid,
                        'is_executed': signal.is_executed,
                        'is_profitable': signal.is_profitable,
                        'profit_loss': float(signal.profit_loss) if signal.profit_loss else None,
                        'created_at': signal.created_at.isoformat(),
                        'analyzed_at': signal.analyzed_at.isoformat() if signal.analyzed_at else signal.created_at.isoformat(),
                        'expires_at': signal.expires_at.isoformat() if signal.expires_at else None,
                        'technical_score': signal.technical_score,
                        'sentiment_score': signal.sentiment_score,
                        'news_score': signal.news_score,
                        'volume_score': signal.volume_score,
                        'pattern_score': signal.pattern_score,
                        # New timeframe and entry point fields
                        'timeframe': signal.timeframe,
                        'entry_point_type': signal.entry_point_type,
                        'entry_point_details': signal.entry_point_details,
                        'entry_zone_low': float(signal.entry_zone_low) if signal.entry_zone_low else None,
                        'entry_zone_high': float(signal.entry_zone_high) if signal.entry_zone_high else None,
                        'entry_confidence': signal.entry_confidence,
                        'is_best_of_day': signal.is_best_of_day,
                        'best_of_day_date': signal.best_of_day_date.isoformat() if signal.best_of_day_date else None,
                        'best_of_day_rank': signal.best_of_day_rank
                    })
                
                response_data = {
                    'success': True,
                    'signals': signal_data,
                    'count': len(signal_data),
                    'cached_at': timezone.now().isoformat()
                }
                
                # Cache the response for only 30 seconds to ensure fresh data
                # Reduced from 5 minutes to prevent showing stale signals
                cache_timeout = 30 if len(signal_data) > 0 else 10
                cache.set(cache_key, response_data, cache_timeout)
                logger.info(f"Cached response with {len(signal_data)} signals for {cache_timeout} seconds")
                
                return JsonResponse(response_data)
                
            except OperationalError as e:
                error_str = str(e).lower()
                is_lock_error = "database is locked" in error_str or "lock" in error_str
                is_connection_error = any(keyword in error_str for keyword in [
                    "connection", "timeout", "unavailable", "lost connection",
                    "can't connect", "connection refused", "too many connections"
                ])
                
                # Close the connection to force a reconnect on next query
                from django.db import connection
                try:
                    connection.close()
                    logger.info("Closed database connection to force reconnect")
                except:
                    pass
                
                if (is_lock_error or is_connection_error) and attempt < max_retries - 1:
                    logger.warning(
                        f"Database error ({'lock' if is_lock_error else 'connection'}), "
                        f"retrying in {retry_delay}s (attempt {attempt + 1}/{max_retries}): {e}"
                    )
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                    continue
                else:
                    # If all retries failed, return cached data or empty response
                    logger.error(f"Database error after {max_retries} attempts: {e}")
                    # Try to get any cached data, even if it's old
                    stale_cache = cache.get(cache_key)
                    if stale_cache:
                        logger.info("Returning stale cached data due to database error")
                        return JsonResponse(stale_cache)
                    # Return empty response with error message
                    return JsonResponse({
                        'success': False,
                        'error': 'Database temporarily unavailable. Please try again in a moment.',
                        'signals': [],
                        'count': 0
                    }, status=503)
            except Exception as e:
                error_str = str(e).lower()
                is_db_error = any(keyword in error_str for keyword in [
                    "database", "connection", "mysql", "operational", "timeout"
                ])
                
                # Close connection if it's a database error
                if is_db_error:
                    from django.db import connection
                    try:
                        connection.close()
                        logger.info("Closed database connection due to error")
                    except:
                        pass
                
                logger.error(f"Error getting signals: {e}", exc_info=True)
                # Try to return cached data even if there's an error
                stale_cache = cache.get(cache_key)
                if stale_cache:
                    logger.info("Returning stale cached data due to error")
                    return JsonResponse(stale_cache)
                
                # Return appropriate error message
                if is_db_error:
                    return JsonResponse({
                        'success': False,
                        'error': 'Database temporarily unavailable. Please try again in a moment.',
                        'signals': [],
                        'count': 0
                    }, status=503)
                else:
                    return JsonResponse({
                        'success': False,
                        'error': str(e)
                    }, status=500)

    def _get_top5_signals_last_hour(self, request):
        """Return the best signals for the current (date, hour) from HourlyBestSignal.
        Ensures no duplicate coins per hour/day. Fallback to TradingSignal slot/created_at for legacy data.
        """
        from apps.signals.price_sync_service import price_sync_service
        now = timezone.now()
        today = now.date()
        current_hour = now.hour  # 0-23 UTC

        # Primary: read from HourlyBestSignal (one row per symbol per hour per day, max 5 per hour)
        hourly_best = (
            HourlyBestSignal.objects.select_related('symbol', 'trading_signal', 'trading_signal__signal_type')
            .filter(signal_date=today, signal_hour=current_hour)
            .order_by('rank')
        )
        batch = []
        for hb in hourly_best:
            batch.append(hb.trading_signal)

        # Fallback: no HourlyBestSignal rows yet – use TradingSignal with signal_date/signal_hour or created_at
        if len(batch) < 5:
            with_slot = (
                TradingSignal.objects.select_related('symbol', 'signal_type')
                .filter(signal_date=today, signal_hour=current_hour)
                .order_by('-quality_score', '-confidence_score', '-created_at')
            )
            batch = list(with_slot[:5])
            if len(batch) < 5:
                hour_start = now.replace(minute=0, second=0, microsecond=0)
                hour_end = hour_start + timedelta(hours=1)
                fallback = (
                    TradingSignal.objects.select_related('symbol', 'signal_type')
                    .filter(
                        created_at__gte=hour_start,
                        created_at__lt=hour_end,
                    )
                    .order_by('-quality_score', '-confidence_score', '-created_at')
                )
                seen = {(s.symbol_id, s.signal_type_id) for s in batch}
                for signal in fallback:
                    if len(batch) >= 5:
                        break
                    key = (signal.symbol_id, signal.signal_type_id)
                    if key not in seen:
                        seen.add(key)
                        batch.append(signal)

        signal_data = []
        for signal in batch:
            sym = signal.symbol.symbol
            sync = price_sync_service.get_synchronized_prices(sym)
            signal_data.append({
                'id': signal.id,
                'symbol': sym,
                'signal_type': signal.signal_type.name,
                'strength': signal.strength,
                'confidence_score': signal.confidence_score,
                'confidence_level': signal.confidence_level,
                'entry_price': float(signal.entry_price) if signal.entry_price else None,
                'target_price': float(signal.target_price) if signal.target_price else None,
                'stop_loss': float(signal.stop_loss) if signal.stop_loss else None,
                'current_price': sync.get('current_price'),
                'price_change_24h': sync.get('price_change_24h'),
                'price_discrepancy_percent': sync.get('price_discrepancy_percent', 0),
                'price_status': sync.get('price_status', 'unknown'),
                'price_alert': sync.get('price_alert'),
                'risk_reward_ratio': signal.risk_reward_ratio,
                'quality_score': signal.quality_score,
                'is_valid': signal.is_valid,
                'is_executed': signal.is_executed,
                'is_profitable': signal.is_profitable,
                'profit_loss': float(signal.profit_loss) if signal.profit_loss else None,
                'created_at': signal.created_at.isoformat(),
                'analyzed_at': signal.analyzed_at.isoformat() if signal.analyzed_at else signal.created_at.isoformat(),
                'expires_at': signal.expires_at.isoformat() if signal.expires_at else None,
                'technical_score': signal.technical_score,
                'sentiment_score': signal.sentiment_score,
                'news_score': signal.news_score,
                'volume_score': signal.volume_score,
                'pattern_score': signal.pattern_score,
                'timeframe': signal.timeframe,
                'entry_point_type': signal.entry_point_type,
                'entry_point_details': signal.entry_point_details,
                'entry_zone_low': float(signal.entry_zone_low) if signal.entry_zone_low else None,
                'entry_zone_high': float(signal.entry_zone_high) if signal.entry_zone_high else None,
                'entry_confidence': signal.entry_confidence,
                'is_best_of_day': signal.is_best_of_day,
                'best_of_day_date': signal.best_of_day_date.isoformat() if signal.best_of_day_date else None,
                'best_of_day_rank': signal.best_of_day_rank,
            })
        return JsonResponse({
            'success': True,
            'signals': signal_data,
            'count': len(signal_data),
        })

    def _refresh_cache_async(self, cache_key, symbol, signal_type, is_valid, limit):
        """Refresh cache asynchronously without blocking"""
        try:
            queryset = TradingSignal.objects.select_related('symbol', 'signal_type')
            if symbol:
                queryset = queryset.filter(symbol__symbol__iexact=symbol)
            if signal_type:
                queryset = queryset.filter(signal_type__name=signal_type)
            # IMPORTANT: keep the background refresh consistent with the main GET logic.
            # Otherwise it can re-cache expired/old signals and make the UI "go back" to old rows.
            if is_valid:
                queryset = queryset.filter(is_valid=True).filter(
                    Q(expires_at__gte=timezone.now()) |
                    Q(expires_at__isnull=True, created_at__gte=timezone.now() - timedelta(hours=48))
                )
            else:
                queryset = queryset.filter(is_valid=is_valid)
            signals = list(queryset.order_by('-created_at')[:limit])
            
            # Serialize and cache (same logic as main get method)
            from apps.signals.price_sync_service import price_sync_service
            signal_data = []
            for signal in signals:
                symbol_name = signal.symbol.symbol
                sync_prices = price_sync_service.get_synchronized_prices(symbol_name)
                current_price = sync_prices.get('current_price')
                
                signal_data.append({
                    'id': signal.id,
                    'symbol': symbol_name,
                    'symbol_name': signal.symbol.name,
                    'signal_type': signal.signal_type.name,
                    'strength': signal.strength,
                    'confidence_score': float(signal.confidence_score) if signal.confidence_score else None,
                    'entry_price': float(signal.entry_price) if signal.entry_price else None,
                    'target_price': float(signal.target_price) if signal.target_price else None,
                    'stop_loss': float(signal.stop_loss) if signal.stop_loss else None,
                    'current_price': current_price,
                    'is_valid': signal.is_valid,
                    'is_executed': signal.is_executed,
                    'is_profitable': signal.is_profitable,
                    'created_at': signal.created_at.isoformat(),
                    'timeframe': signal.timeframe,
                    'entry_point_type': signal.entry_point_type,
                })
            
            response_data = {
                'success': True,
                'signals': signal_data,
                'count': len(signal_data),
                'cached_at': timezone.now().isoformat()
            }
            cache.set(cache_key, response_data, 30)  # Reduced from 300 to 30 seconds for fresh data
        except Exception as e:
            logger.debug(f"Background cache refresh failed: {e}")
    
    def post(self, request):
        """Generate signals for a symbol"""
        try:
            data = json.loads(request.body)
            symbol_name = data.get('symbol')
            
            if not symbol_name:
                return JsonResponse({
                    'success': False,
                    'error': 'Symbol is required'
                }, status=400)
            
            # Get symbol
            try:
                symbol = Symbol.objects.get(symbol__iexact=symbol_name)
            except Symbol.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': f'Symbol {symbol_name} not found'
                }, status=404)
            
            # Generate signals
            signal_service = SignalGenerationService()
            signals = signal_service.generate_signals_for_symbol(symbol)
            
            # Invalidate related caches to ensure data consistency
            cache_keys_to_delete = [
                "signal_statistics",
                f"signals_api_{symbol.symbol}_None_true_50",
                f"signals_api_None_None_true_50"
            ]
            
            for cache_key in cache_keys_to_delete:
                cache.delete(cache_key)
                logger.info(f"Invalidated cache key: {cache_key}")
            
            return JsonResponse({
                'success': True,
                'symbol': symbol.symbol,
                'signals_generated': len(signals),
                'signals': [signal.id for signal in signals]
            })
            
        except Exception as e:
            logger.error(f"Error generating signals: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


@method_decorator(csrf_exempt, name='dispatch')
@method_decorator(login_required, name='dispatch')
class SignalDetailView(View):
    """API view for individual signal operations"""
    
    def get(self, request, signal_id):
        """Get signal details"""
        try:
            signal = TradingSignal.objects.select_related(
                'symbol', 'signal_type'
            ).prefetch_related('factor_contributions__factor').get(id=signal_id)
            
            # Get factor contributions
            factor_contributions = []
            for contribution in signal.factor_contributions.all():
                factor_contributions.append({
                    'factor_name': contribution.factor.name,
                    'factor_type': contribution.factor.factor_type,
                    'score': contribution.score,
                    'weight': contribution.weight,
                    'contribution': contribution.contribution
                })
            
            signal_data = {
                'id': signal.id,
                'symbol': signal.symbol.symbol,
                'signal_type': signal.signal_type.name,
                'strength': signal.strength,
                'confidence_score': signal.confidence_score,
                'confidence_level': signal.confidence_level,
                'entry_price': float(signal.entry_price) if signal.entry_price else None,
                'target_price': float(signal.target_price) if signal.target_price else None,
                'stop_loss': float(signal.stop_loss) if signal.stop_loss else None,
                'risk_reward_ratio': signal.risk_reward_ratio,
                'quality_score': signal.quality_score,
                'is_valid': signal.is_valid,
                'is_executed': signal.is_executed,
                'is_profitable': signal.is_profitable,
                'profit_loss': float(signal.profit_loss) if signal.profit_loss else None,
                'created_at': signal.created_at.isoformat(),
                'expires_at': signal.expires_at.isoformat() if signal.expires_at else None,
                'technical_score': signal.technical_score,
                'sentiment_score': signal.sentiment_score,
                'news_score': signal.news_score,
                'volume_score': signal.volume_score,
                'pattern_score': signal.pattern_score,
                'factor_contributions': factor_contributions
            }
            
            return JsonResponse({
                'success': True,
                'signal': signal_data
            })
            
        except TradingSignal.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Signal not found'
            }, status=404)
        except Exception as e:
            logger.error(f"Error getting signal {signal_id}: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    def put(self, request, signal_id):
        """Update signal (e.g., mark as executed)"""
        try:
            data = json.loads(request.body)
            signal = TradingSignal.objects.get(id=signal_id)
            
            # Update fields
            if 'is_executed' in data:
                signal.is_executed = data['is_executed']
                if data['is_executed']:
                    signal.executed_at = timezone.now()
            
            if 'execution_price' in data:
                signal.execution_price = data['execution_price']
            
            if 'is_profitable' in data:
                signal.is_profitable = data['is_profitable']
            
            if 'profit_loss' in data:
                signal.profit_loss = data['profit_loss']
            
            signal.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Signal updated successfully'
            })
            
        except TradingSignal.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Signal not found'
            }, status=404)
        except Exception as e:
            logger.error(f"Error updating signal {signal_id}: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class SignalPerformanceView(View):
    """API view for signal performance metrics"""
    
    def get(self, request):
        """Get performance metrics"""
        try:
            # Get query parameters
            period_type = request.GET.get('period_type', '1D')
            
            # Calculate performance metrics
            performance_service = SignalPerformanceService()
            metrics = performance_service.calculate_performance_metrics(period_type)
            
            # Get recent performance records
            recent_performance = SignalPerformance.objects.filter(
                period_type=period_type
            ).order_by('-created_at')[:10]
            
            performance_history = []
            for record in recent_performance:
                performance_history.append({
                    'period_type': record.period_type,
                    'start_date': record.start_date.isoformat(),
                    'end_date': record.end_date.isoformat(),
                    'total_signals': record.total_signals,
                    'profitable_signals': record.profitable_signals,
                    'win_rate': record.win_rate,
                    'profit_factor': record.profit_factor,
                    'average_confidence': record.average_confidence,
                    'average_quality': record.average_quality_score
                })
            
            return JsonResponse({
                'success': True,
                'current_metrics': metrics,
                'performance_history': performance_history
            })
            
        except Exception as e:
            logger.error(f"Error getting performance metrics: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class MarketRegimeView(View):
    """API view for market regime detection"""
    
    def get(self, request):
        """Get market regimes"""
        try:
            symbol = request.GET.get('symbol')
            
            if symbol:
                # Get regime for specific symbol
                try:
                    symbol_obj = Symbol.objects.get(symbol__iexact=symbol)
                    regime_service = MarketRegimeService()
                    regime = regime_service.detect_market_regime(symbol_obj)
                    
                    if regime:
                        regime_data = {
                            'name': regime.name,
                            'description': regime.description,
                            'volatility_level': regime.volatility_level,
                            'trend_strength': regime.trend_strength,
                            'confidence': regime.confidence,
                            'created_at': regime.created_at.isoformat()
                        }
                    else:
                        regime_data = None
                    
                    return JsonResponse({
                        'success': True,
                        'symbol': symbol,
                        'regime': regime_data
                    })
                    
                except Symbol.DoesNotExist:
                    return JsonResponse({
                        'success': False,
                        'error': f'Symbol {symbol} not found'
                    }, status=404)
            else:
                # Get all recent regimes
                recent_regimes = MarketRegime.objects.order_by('-created_at')[:20]
                
                regime_data = []
                for regime in recent_regimes:
                    regime_data.append({
                        'name': regime.name,
                        'description': regime.description,
                        'volatility_level': regime.volatility_level,
                        'trend_strength': regime.trend_strength,
                        'confidence': regime.confidence,
                        'created_at': regime.created_at.isoformat()
                    })
                
                return JsonResponse({
                    'success': True,
                    'regimes': regime_data
                })
            
        except Exception as e:
            logger.error(f"Error getting market regimes: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    def post(self, request):
        """Detect market regimes for all symbols"""
        try:
            regime_service = MarketRegimeService()
            active_symbols = Symbol.objects.filter(is_active=True)
            
            regimes_detected = 0
            for symbol in active_symbols:
                try:
                    regime = regime_service.detect_market_regime(symbol)
                    if regime:
                        regimes_detected += 1
                except Exception as e:
                    logger.error(f"Error detecting regime for {symbol.symbol}: {e}")
            
            return JsonResponse({
                'success': True,
                'regimes_detected': regimes_detected,
                'symbols_processed': active_symbols.count()
            })
            
        except Exception as e:
            logger.error(f"Error detecting market regimes: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class SignalAlertView(View):
    """API view for signal alerts"""
    
    def get(self, request):
        """Get alerts"""
        try:
            # Get query parameters
            alert_type = request.GET.get('alert_type')
            priority = request.GET.get('priority')
            is_read = request.GET.get('is_read')
            limit = int(request.GET.get('limit', 50))
            
            # Build query
            queryset = SignalAlert.objects.select_related('signal__symbol')
            
            if alert_type:
                queryset = queryset.filter(alert_type=alert_type)
            
            if priority:
                queryset = queryset.filter(priority=priority)
            
            if is_read is not None:
                is_read_bool = is_read.lower() == 'true'
                queryset = queryset.filter(is_read=is_read_bool)
            
            alerts = queryset.order_by('-created_at')[:limit]
            
            # Serialize alerts
            alert_data = []
            for alert in alerts:
                alert_data.append({
                    'id': alert.id,
                    'alert_type': alert.alert_type,
                    'priority': alert.priority,
                    'title': alert.title,
                    'message': alert.message,
                    'signal_id': alert.signal.id if alert.signal else None,
                    'signal_symbol': alert.signal.symbol.symbol if alert.signal else None,
                    'is_read': alert.is_read,
                    'created_at': alert.created_at.isoformat()
                })
            
            return JsonResponse({
                'success': True,
                'alerts': alert_data,
                'count': len(alert_data)
            })
            
        except Exception as e:
            logger.error(f"Error getting alerts: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    def post(self, request):
        """Mark alerts as read"""
        try:
            data = json.loads(request.body)
            alert_ids = data.get('alert_ids', [])
            
            if not alert_ids:
                return JsonResponse({
                    'success': False,
                    'error': 'Alert IDs are required'
                }, status=400)
            
            # Mark alerts as read
            updated = SignalAlert.objects.filter(id__in=alert_ids).update(is_read=True)
            
            return JsonResponse({
                'success': True,
                'alerts_marked_read': updated
            })
            
        except Exception as e:
            logger.error(f"Error marking alerts as read: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


@method_decorator(csrf_exempt, name='dispatch')
@method_decorator(login_required, name='dispatch')
class DailyBestSignalsView(View):
    """API view for daily best signals by date"""
    
    def get(self, request):
        """Get best 10 signals for a specific date. Date is required."""
        try:
            from datetime import datetime
            from django.utils import timezone
            
            # Date is required: cannot view best signals without selecting a date
            date_str = request.GET.get('date')
            if not date_str:
                return JsonResponse({
                    'success': False,
                    'error': 'date_required',
                    'message': 'Please select a date to view best signals for that day.'
                }, status=400)
            try:
                target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid date format. Use YYYY-MM-DD'
                }, status=400)
            
            today = timezone.now().date()
            # READ-ONLY: Only return signals that were created on target_date (never mix dates).
            # Past date: use saved best_of_day marks, and enforce created_at date to avoid any cross-date leakage.
            # Today: top 10 by quality from signals already generated hourly today (no new generation).
            start_dt = timezone.make_aware(datetime.combine(target_date, datetime.min.time()))
            end_dt = timezone.make_aware(datetime.combine(target_date, datetime.max.time()))

            if target_date < today:
                # Past: only signals saved as best-of-day for this date AND created on this date
                best_signals_queryset = (
                    TradingSignal.objects.filter(
                        best_of_day_date=target_date,
                        is_best_of_day=True,
                        created_at__gte=start_dt,
                        created_at__lte=end_dt,
                    )
                    .select_related('symbol', 'signal_type')
                    .order_by('best_of_day_rank')
                )
                unique_signals = list(best_signals_queryset)
            else:
                # Today: top 10 by quality from hourly-generated signals for today only (read-only)
                day_signals = (
                    TradingSignal.objects.filter(
                        created_at__gte=start_dt,
                        created_at__lte=end_dt,
                    )
                    .select_related('symbol', 'signal_type')
                    .order_by('-quality_score', '-confidence_score', '-risk_reward_ratio', '-created_at')
                )
                seen_combinations = set()
                unique_signals = []
                for signal in day_signals:
                    combo_key = (signal.symbol.id, signal.signal_type.id)
                    if combo_key not in seen_combinations:
                        seen_combinations.add(combo_key)
                        unique_signals.append(signal)
                        if len(unique_signals) >= 10:
                            break
            
            # Serialize signals
            signal_data = []
            for signal in unique_signals:
                signal_data.append({
                    'id': signal.id,
                    'symbol': signal.symbol.symbol,
                    'signal_type': signal.signal_type.name,
                    'strength': signal.strength,
                    'confidence_score': signal.confidence_score,
                    'confidence_level': signal.confidence_level,
                    'entry_price': float(signal.entry_price) if signal.entry_price else None,
                    'target_price': float(signal.target_price) if signal.target_price else None,
                    'stop_loss': float(signal.stop_loss) if signal.stop_loss else None,
                    'risk_reward_ratio': signal.risk_reward_ratio,
                    'quality_score': signal.quality_score,
                    'timeframe': signal.timeframe,
                    'entry_point_type': signal.entry_point_type,
                    'best_of_day_rank': signal.best_of_day_rank,
                    'created_at': signal.created_at.isoformat(),
                })
            
            return JsonResponse({
                'success': True,
                'date': target_date.isoformat(),
                'signals': signal_data,
                'count': len(signal_data)
            })
            
        except Exception as e:
            logger.error(f"Error getting daily best signals: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


@method_decorator(csrf_exempt, name='dispatch')
@method_decorator(login_required, name='dispatch')
class AvailableDatesView(View):
    """API view to get available dates with best signals"""
    
    def get(self, request):
        """Get list of dates that have best signals"""
        try:
            from django.db.models import Count
            
            # Get distinct dates that have best signals
            dates = TradingSignal.objects.filter(
                is_best_of_day=True
            ).values('best_of_day_date').annotate(
                signal_count=Count('id')
            ).order_by('-best_of_day_date')
            
            date_list = [
                {
                    'date': item['best_of_day_date'].isoformat() if item['best_of_day_date'] else None,
                    'count': item['signal_count']
                }
                for item in dates
                if item['best_of_day_date']
            ]
            
            return JsonResponse({
                'success': True,
                'dates': date_list,
                'count': len(date_list)
            })
            
        except Exception as e:
            logger.error(f"Error getting available dates: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


def _signal_dashboard_safe_context(error=None):
    """Build a minimal safe context for the signal dashboard (used on error or as defaults)."""
    return {
        'recent_signals': [],
        'daily_metrics': {},
        'active_alerts': [],
        'recent_regimes': [],
        'total_signals': 0,
        'active_signals': 0,
        'executed_signals': 0,
        'profitable_signals': 0,
        'win_rate': 0.0,
        'error': error,
    }


@login_required
def signal_dashboard(request):
    """Signal dashboard view. On error, still renders page with safe context and shows error message."""
    try:
        # Get recent signals
        recent_signals = TradingSignal.objects.select_related(
            'symbol', 'signal_type'
        ).filter(is_valid=True).order_by('-created_at')[:10]
        
        # Get performance metrics
        performance_service = SignalPerformanceService()
        daily_metrics = performance_service.calculate_performance_metrics('1D')
        
        # Get active alerts
        active_alerts = SignalAlert.objects.filter(is_read=False).order_by('-created_at')[:5]
        
        # Get market regimes
        recent_regimes = MarketRegime.objects.order_by('-created_at')[:5]
        
        # Calculate statistics
        total_signals = TradingSignal.objects.count()
        active_signals = TradingSignal.objects.filter(is_valid=True).count()
        executed_signals = TradingSignal.objects.filter(is_executed=True).count()
        profitable_signals = TradingSignal.objects.filter(
            is_executed=True, is_profitable=True
        ).count()
        
        win_rate = profitable_signals / executed_signals if executed_signals > 0 else 0.0
        
        context = {
            'recent_signals': recent_signals,
            'daily_metrics': daily_metrics,
            'active_alerts': active_alerts,
            'recent_regimes': recent_regimes,
            'total_signals': total_signals,
            'active_signals': active_signals,
            'executed_signals': executed_signals,
            'profitable_signals': profitable_signals,
            'win_rate': win_rate,
            'error': None,
        }
        return render(request, 'signals/dashboard.html', context)
        
    except Exception as e:
        logger.exception("Error rendering signal dashboard: %s", e)
        context = _signal_dashboard_safe_context(error=str(e))
        return render(request, 'signals/dashboard.html', context)


@login_required
def signal_history(request):
    """Signal history view"""
    try:
        # Get query parameters
        symbol = request.GET.get('symbol', '')
        signal_type = request.GET.get('signal_type', '')
        archived_reason = request.GET.get('archived_reason', '')
        days = int(request.GET.get('days', 365))
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 50))
        
        # Calculate date range for filtering
        from datetime import datetime, timedelta
        from django.utils import timezone
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        # Build query - show archived signals (executed or expired)
        query = Q()
        
        # Filter by date range (only if days is specified and reasonable)
        # For now, let's show all signals regardless of date to fix the issue
        # if days <= 365:  # Only apply date filter for reasonable ranges
        #     query &= Q(created_at__gte=start_date, created_at__lte=end_date)
        
        # Filter by symbol
        if symbol:
            query &= Q(symbol__symbol__icontains=symbol)
        
        # Filter by signal type
        if signal_type:
            query &= Q(signal_type__name__icontains=signal_type)
        
        # Show ALL generated signals (history = full list, no filter by archived only)
        # No extra filter: query already has symbol/signal_type if provided
        
        # Get signals with pagination
        signals = TradingSignal.objects.select_related(
            'symbol', 'signal_type'
        ).filter(query).order_by('-created_at')
        
        # Calculate pagination
        total_signals = signals.count()
        start_index = (page - 1) * per_page
        end_index = start_index + per_page
        signals_page = signals[start_index:end_index]
        
        # Transform signals to match template expectations
        processed_signals = []
        for signal in signals_page:
            # Calculate performance metrics
            performance_percentage = None
            is_profitable = None
            
            if signal.is_executed and signal.executed_at:
                if signal.entry_price and signal.execution_price:
                    price_change = float(signal.execution_price) - float(signal.entry_price)
                    performance_percentage = (price_change / float(signal.entry_price)) * 100
                    is_profitable = price_change > 0
            
            # Create signal data matching template expectations
            signal_data = {
                'id': signal.id,
                'symbol_name': signal.symbol.symbol if signal.symbol else 'N/A',
                'signal_type_name': signal.signal_type.name if signal.signal_type else 'N/A',
                'strength': signal.strength,
                'confidence_score': signal.confidence_score,
                'confidence_level': signal.confidence_level,
                'entry_price': signal.entry_price,
                'target_price': signal.target_price,
                'stop_loss': signal.stop_loss,
                'risk_reward_ratio': signal.risk_reward_ratio,
                'timeframe': signal.timeframe or '1D',
                'entry_point_type': signal.entry_point_type or 'UNKNOWN',
                'entry_point_details': signal.entry_point_details,
                'entry_zone_low': signal.entry_zone_low,
                'entry_zone_high': signal.entry_zone_high,
                'entry_confidence': signal.entry_confidence,
                'quality_score': signal.quality_score,
                'is_valid': signal.is_valid,
                'expires_at': signal.expires_at,
                'technical_score': signal.technical_score,
                'sentiment_score': signal.sentiment_score,
                'news_score': signal.news_score,
                'volume_score': signal.volume_score,
                'pattern_score': signal.pattern_score,
                'economic_score': signal.economic_score,
                'sector_score': signal.sector_score,
                'is_executed': signal.is_executed,
                'executed_at': signal.executed_at,
                'execution_price': signal.execution_price,
                'is_profitable': is_profitable,
                'profit_loss': signal.profit_loss,
                'performance_percentage': performance_percentage,
                'analyzed_at': signal.analyzed_at,
                'archived_at': signal.executed_at or signal.created_at,  # Use executed_at as archived_at
                'archived_reason': 'EXECUTED' if signal.is_executed else ('EXPIRED' if not signal.is_valid else 'ACTIVE'),
                'notes': signal.notes,
                'created_at': signal.created_at,
                'updated_at': signal.updated_at,
            }
            processed_signals.append(signal_data)
        
        # Get unique values for filters
        unique_signal_types = list(TradingSignal.objects.filter(
            created_at__gte=start_date, created_at__lte=end_date
        ).values_list('signal_type__name', flat=True).distinct().exclude(signal_type__name__isnull=True))
        
        unique_reasons = ['EXECUTED', 'EXPIRED', 'MANUAL_ARCHIVE', 'SYSTEM_CLEANUP', 'ACTIVE']
        
        # Calculate statistics
        total_count = total_signals
        recent_archived = TradingSignal.objects.filter(
            created_at__gte=timezone.now() - timedelta(days=1),
            created_at__lte=timezone.now()
        ).filter(
            Q(is_executed=True) | Q(is_valid=False)  # Only count actually archived signals
        ).count()
        
        # Pagination info
        total_pages = (total_count + per_page - 1) // per_page
        has_prev = page > 1
        has_next = page < total_pages
        
        # Calculate page range for pagination
        start_page = max(1, page - 2)
        end_page = min(total_pages, page + 2)
        page_range = range(start_page, end_page + 1)
        
        context = {
            'signals': processed_signals,
            'total_count': total_count,
            'total_pages': total_pages,
            'page': page,
            'per_page': per_page,
            'has_prev': has_prev,
            'has_next': has_next,
            'page_range': page_range,
            'recent_archived': recent_archived,
            'unique_signal_types': unique_signal_types,
            'unique_reasons': unique_reasons,
            'current_filters': {
                'symbol': symbol,
                'signal_type': signal_type,
                'archived_reason': archived_reason,
                'days': days,
            }
        }
        
        return render(request, 'signals/history.html', context)
        
    except Exception as e:
        logger.error(f"Error rendering signal history: {e}")
        return render(request, 'signals/history.html', {'error': str(e)})


@login_required
def spot_signals_dashboard(request):
    """Spot trading signals dashboard view"""
    try:
        from apps.signals.models import SpotTradingSignal
        
        # Get query parameters
        symbol = request.GET.get('symbol', '')
        category = request.GET.get('category', '')
        horizon = request.GET.get('horizon', '')
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 20))
        
        # Build query
        query = Q()
        if symbol:
            query &= Q(symbol__symbol__icontains=symbol)
        if category:
            query &= Q(signal_category__icontains=category)
        if horizon:
            query &= Q(investment_horizon__icontains=horizon)
        
        # Get spot signals with pagination
        spot_signals = SpotTradingSignal.objects.select_related(
            'symbol'
        ).filter(query, is_active=True).order_by('-created_at')
        
        # Calculate pagination
        total_spot_signals = spot_signals.count()
        start_index = (page - 1) * per_page
        end_index = start_index + per_page
        spot_signals_page = spot_signals[start_index:end_index]
        
        # Get available symbols and categories for filters
        available_symbols = Symbol.objects.filter(is_active=True, is_crypto_symbol=True).order_by('symbol')
        
        # Calculate statistics
        total_accumulation = SpotTradingSignal.objects.filter(signal_category='ACCUMULATION', is_active=True).count()
        total_dca = SpotTradingSignal.objects.filter(signal_category='DCA', is_active=True).count()
        total_distribution = SpotTradingSignal.objects.filter(signal_category='DISTRIBUTION', is_active=True).count()
        total_hold = SpotTradingSignal.objects.filter(signal_category='HOLD', is_active=True).count()
        
        # Calculate average scores
        avg_fundamental = SpotTradingSignal.objects.filter(is_active=True).aggregate(
            avg=Avg('fundamental_score')
        )['avg'] or 0
        
        avg_technical = SpotTradingSignal.objects.filter(is_active=True).aggregate(
            avg=Avg('technical_score')
        )['avg'] or 0
        
        avg_sentiment = SpotTradingSignal.objects.filter(is_active=True).aggregate(
            avg=Avg('sentiment_score')
        )['avg'] or 0
        
        context = {
            'spot_signals': spot_signals_page,
            'total_spot_signals': total_spot_signals,
            'page': page,
            'per_page': per_page,
            'total_pages': (total_spot_signals + per_page - 1) // per_page,
            'available_symbols': available_symbols,
            'current_symbol': symbol,
            'current_category': category,
            'current_horizon': horizon,
            'statistics': {
                'total_accumulation': total_accumulation,
                'total_dca': total_dca,
                'total_distribution': total_distribution,
                'total_hold': total_hold,
                'avg_fundamental': round(avg_fundamental * 100, 1),
                'avg_technical': round(avg_technical * 100, 1),
                'avg_sentiment': round(avg_sentiment * 100, 1),
            }
        }
        
        return render(request, 'signals/spot_dashboard.html', context)
        
    except Exception as e:
        logger.error(f"Error rendering spot signals dashboard: {e}")
        return render(request, 'signals/spot_dashboard.html', {'error': str(e)})


@login_required
def backtesting_signals_history(request):
    """Backtesting signals history view - shows only backtesting signals"""
    try:
        # Get query parameters
        symbol = request.GET.get('symbol', '')
        signal_type = request.GET.get('signal_type', '')
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 50))
        
        # Build query - show only backtesting signals
        query = Q()
        
        # Filter by symbol
        if symbol:
            query &= Q(symbol__symbol__icontains=symbol)
        
        # Filter by signal type
        if signal_type:
            query &= Q(signal_type__name__icontains=signal_type)
        
        # Show only backtesting signals
        query &= Q(metadata__is_backtesting=True)
        
        # Get signals with pagination
        signals = TradingSignal.objects.select_related(
            'symbol', 'signal_type'
        ).filter(query).order_by('-created_at')
        
        # Calculate pagination
        total_signals = signals.count()
        start_index = (page - 1) * per_page
        end_index = start_index + per_page
        signals_page = signals[start_index:end_index]
        
        # Transform signals to match template expectations
        processed_signals = []
        for signal in signals_page:
            # Calculate performance if executed
            is_profitable = None
            performance_percentage = None
            
            if signal.is_executed and signal.execution_price and signal.target_price:
                if signal.signal_type.name == 'BUY':
                    performance = ((float(signal.target_price) - float(signal.execution_price)) / float(signal.execution_price)) * 100
                else:  # SELL
                    performance = ((float(signal.execution_price) - float(signal.target_price)) / float(signal.execution_price)) * 100
                
                is_profitable = performance > 0
                performance_percentage = round(performance, 2)
            
            signal_data = {
                'id': signal.id,
                'symbol': signal.symbol.symbol,
                'symbol_name': signal.symbol.name,
                'signal_type': signal.signal_type.name,
                'signal_type_color': signal.signal_type.color,
                'strength': signal.strength,
                'confidence_score': signal.confidence_score,
                'confidence_level': signal.confidence_level,
                'entry_price': signal.entry_price,
                'target_price': signal.target_price,
                'stop_loss': signal.stop_loss,
                'risk_reward_ratio': signal.risk_reward_ratio,
                'timeframe': signal.timeframe,
                'entry_point_type': signal.entry_point_type,
                'quality_score': signal.quality_score,
                'is_valid': signal.is_valid,
                'expires_at': signal.expires_at,
                'technical_score': signal.technical_score,
                'sentiment_score': signal.sentiment_score,
                'news_score': signal.news_score,
                'volume_score': signal.volume_score,
                'pattern_score': signal.pattern_score,
                'economic_score': signal.economic_score,
                'sector_score': signal.sector_score,
                'is_executed': signal.is_executed,
                'executed_at': signal.executed_at,
                'execution_price': signal.execution_price,
                'is_profitable': is_profitable,
                'profit_loss': signal.profit_loss,
                'performance_percentage': performance_percentage,
                'analyzed_at': signal.analyzed_at,
                'notes': signal.notes,
                'created_at': signal.created_at,
                'updated_at': signal.updated_at,
                'is_backtesting': True,  # Mark as backtesting signal
            }
            processed_signals.append(signal_data)
        
        # Get unique values for filters
        unique_signal_types = list(TradingSignal.objects.filter(
            metadata__is_backtesting=True
        ).values_list('signal_type__name', flat=True).distinct().exclude(signal_type__name__isnull=True))
        
        # Pagination info
        total_pages = (total_signals + per_page - 1) // per_page
        has_prev = page > 1
        has_next = page < total_pages
        
        # Calculate page range for pagination
        start_page = max(1, page - 2)
        end_page = min(total_pages, page + 2)
        page_range = range(start_page, end_page + 1)
        
        context = {
            'signals': processed_signals,
            'total_count': total_signals,
            'total_pages': total_pages,
            'page': page,
            'per_page': per_page,
            'has_prev': has_prev,
            'has_next': has_next,
            'page_range': page_range,
            'unique_signal_types': unique_signal_types,
            'current_filters': {
                'symbol': symbol,
                'signal_type': signal_type,
            },
            'is_backtesting_view': True,
        }
        
        return render(request, 'signals/backtesting_history.html', context)
        
    except Exception as e:
        logger.error(f"Error rendering backtesting signals history: {e}")
        return render(request, 'signals/backtesting_history.html', {'error': str(e)})


@login_required
def duplicate_signals_dashboard(request):
    """Duplicate signals removal dashboard"""
    try:
        return render(request, 'signals/duplicate_signals.html')
    except Exception as e:
        logger.error(f"Error in duplicate_signals_dashboard: {e}")
        return render(request, 'signals/duplicate_signals.html', {'error': str(e)})


@require_http_methods(["GET"])
def signal_statistics(request):
    """Get signal statistics"""
    try:
        # Check cache first
        cache_key = "signal_statistics"
        cached_stats = cache.get(cache_key)
        
        if cached_stats:
            logger.info("Returning cached signal statistics")
            return JsonResponse(cached_stats)
        
        # Calculate statistics with optimized queries
        total_signals = TradingSignal.objects.count()
        active_signals = TradingSignal.objects.filter(is_valid=True).count()
        executed_signals = TradingSignal.objects.filter(is_executed=True).count()
        profitable_signals = TradingSignal.objects.filter(
            is_executed=True, is_profitable=True
        ).count()
        
        win_rate = profitable_signals / executed_signals if executed_signals > 0 else 0.0
        
        # Get average metrics for recent signals with optimized query
        recent_signals = TradingSignal.objects.filter(
            created_at__gte=timezone.now() - timedelta(days=7)
        ).aggregate(
            avg_confidence=Avg('confidence_score'),
            avg_quality=Avg('quality_score')
        )
        
        avg_confidence = recent_signals['avg_confidence'] or 0.0
        avg_quality = recent_signals['avg_quality'] or 0.0
        
        # Get signal distribution by type with optimized query
        signal_distribution = TradingSignal.objects.values('signal_type__name').annotate(
            count=Count('id')
        )
        
        # Get signal distribution by strength with optimized query
        strength_distribution = TradingSignal.objects.values('strength').annotate(
            count=Count('id')
        )
        
        statistics = {
            'total_signals': total_signals,
            'active_signals': active_signals,
            'executed_signals': executed_signals,
            'profitable_signals': profitable_signals,
            'win_rate': win_rate,
            'avg_confidence': avg_confidence,
            'avg_quality': avg_quality,
            'signal_distribution': list(signal_distribution),
            'strength_distribution': list(strength_distribution),
            'cached_at': timezone.now().isoformat()
        }
        
        response_data = {
            'success': True,
            'statistics': statistics
        }
        
        # Cache the statistics for 60 seconds (reduced from 600 for fresh data)
        cache.set(cache_key, response_data, 60)
        
        return JsonResponse(response_data)
        
    except Exception as e:
        logger.error(f"Error getting signal statistics: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["POST"])
@login_required
def execute_signal(request, signal_id):
    """Execute a trading signal"""
    try:
        # Get the signal
        try:
            signal = TradingSignal.objects.get(id=signal_id)
        except TradingSignal.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': f'Signal {signal_id} not found'
            }, status=404)
        
        # Check if signal is valid and not already executed
        if not signal.is_valid:
            return JsonResponse({
                'success': False,
                'error': 'Signal is not valid'
            }, status=400)
        
        if signal.is_executed:
            return JsonResponse({
                'success': False,
                'error': 'Signal has already been executed'
            }, status=400)
        
        # Check if signal has expired
        if signal.expires_at and signal.expires_at < timezone.now():
            return JsonResponse({
                'success': False,
                'error': 'Signal has expired'
            }, status=400)
        
        # Execute the signal
        signal.is_executed = True
        signal.executed_at = timezone.now()
        signal.save()
        
        # Invalidate related caches to ensure data consistency
        cache_keys_to_delete = [
            "signal_statistics",
            f"signals_api_{signal.symbol.symbol}_None_true_50",
            f"signals_api_None_None_true_50"
        ]
        
        for cache_key in cache_keys_to_delete:
            cache.delete(cache_key)
            logger.info(f"Invalidated cache key: {cache_key}")
        
        # Log the execution
        logger.info(f"Signal {signal_id} executed successfully for {signal.symbol.symbol}")
        
        return JsonResponse({
            'success': True,
            'message': f'Signal {signal_id} executed successfully',
            'signal': {
                'id': signal.id,
                'symbol': signal.symbol.symbol,
                'signal_type': signal.signal_type.name,
                'executed_at': signal.executed_at.isoformat(),
                'entry_price': float(signal.entry_price) if signal.entry_price else None,
                'target_price': float(signal.target_price) if signal.target_price else None,
                'stop_loss': float(signal.stop_loss) if signal.stop_loss else None
            }
        })
        
    except Exception as e:
        logger.error(f"Error executing signal {signal_id}: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["POST"])
@login_required
def generate_signals_manual(request):
    """Manually trigger signal generation with improved error handling for deployment"""
    import time
    from django.db import connection, OperationalError, DatabaseError
    
    try:
        # Parse request data
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in request body: {e}")
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON in request body'
            }, status=400)
        
        symbol_name = data.get('symbol')
        
        if not symbol_name:
            return JsonResponse({
                'success': False,
                'error': 'Symbol is required'
            }, status=400)
        
        # Test database connection with retry logic
        max_db_retries = 3
        retry_delay = 0.5
        db_connected = False
        
        for attempt in range(max_db_retries):
            try:
                # Test connection with a simple query
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    cursor.fetchone()
                db_connected = True
                break
            except (OperationalError, DatabaseError) as db_error:
                error_msg = str(db_error).lower()
                logger.warning(f"Database connection test failed (attempt {attempt + 1}/{max_db_retries}): {db_error}")
                
                # Close all connections to force reconnect
                try:
                    from django.db import connections
                    connections.close_all()
                except:
                    pass
                
                if attempt < max_db_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    logger.error(f"Database connection failed after {max_db_retries} attempts: {db_error}")
                    return JsonResponse({
                        'success': False,
                        'error': 'Database connection failed. Please try again in a moment.',
                        'error_type': 'database_connection_error'
                    }, status=503)
        
        if not db_connected:
            return JsonResponse({
                'success': False,
                'error': 'Unable to connect to database',
                'error_type': 'database_connection_error'
            }, status=503)
        
        # Get symbol with retry logic
        symbol = None
        for attempt in range(max_db_retries):
            try:
                symbol = Symbol.objects.get(symbol__iexact=symbol_name)
                break
            except Symbol.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': f'Symbol {symbol_name} not found in database',
                    'error_type': 'symbol_not_found'
                }, status=404)
            except (OperationalError, DatabaseError) as db_error:
                logger.warning(f"Error fetching symbol (attempt {attempt + 1}/{max_db_retries}): {db_error}")
                if attempt < max_db_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    logger.error(f"Failed to fetch symbol after {max_db_retries} attempts: {db_error}")
                    return JsonResponse({
                        'success': False,
                        'error': 'Database error while fetching symbol. Please try again.',
                        'error_type': 'database_error'
                    }, status=503)
        
        if not symbol:
            return JsonResponse({
                'success': False,
                'error': 'Failed to retrieve symbol',
                'error_type': 'symbol_retrieval_error'
            }, status=500)
        
        # Check if symbol is active
        if not symbol.is_active:
            logger.warning(f"Attempted to generate signals for inactive symbol: {symbol_name}")
            return JsonResponse({
                'success': False,
                'error': f'Symbol {symbol_name} is not active',
                'error_type': 'symbol_inactive'
            }, status=400)
        
        # Generate signals with error handling
        try:
            logger.info(f"Starting signal generation for {symbol_name} (user: {request.user.username})")
            signal_service = SignalGenerationService()
            signals = signal_service.generate_signals_for_symbol(symbol)
            logger.info(f"Successfully generated {len(signals)} signals for {symbol_name}")
        except Exception as gen_error:
            error_msg = str(gen_error)
            error_type = type(gen_error).__name__
            logger.error(
                f"Error generating signals for {symbol_name}: {error_msg}",
                exc_info=True,
                extra={
                    'symbol': symbol_name,
                    'user': request.user.username,
                    'error_type': error_type,
                    'error_message': error_msg
                }
            )
            
            # Provide more specific error messages
            if 'database' in error_msg.lower() or 'connection' in error_msg.lower():
                return JsonResponse({
                    'success': False,
                    'error': 'Database error during signal generation. Please try again.',
                    'error_type': 'database_error',
                    'details': 'The signal generation process encountered a database issue.'
                }, status=503)
            elif 'timeout' in error_msg.lower():
                return JsonResponse({
                    'success': False,
                    'error': 'Signal generation timed out. The operation took too long.',
                    'error_type': 'timeout_error',
                    'details': 'Please try again or contact support if the issue persists.'
                }, status=504)
            elif 'market data' in error_msg.lower() or 'no data' in error_msg.lower():
                return JsonResponse({
                    'success': False,
                    'error': f'Insufficient market data for {symbol_name}. Please ensure data is available.',
                    'error_type': 'data_unavailable',
                    'details': 'Market data may need to be updated before generating signals.'
                }, status=400)
            else:
                # Generic error with sanitized message for security
                return JsonResponse({
                    'success': False,
                    'error': f'Error generating signals: {error_msg[:200]}',  # Limit error message length
                    'error_type': error_type,
                    'details': 'An unexpected error occurred during signal generation.'
                }, status=500)
        
        # Invalidate related caches to ensure data consistency
        try:
            cache_keys_to_delete = [
                "signal_statistics",
                f"signals_api_{symbol.symbol}_None_true_50",
                f"signals_api_None_None_true_50"
            ]
            
            for cache_key in cache_keys_to_delete:
                try:
                    cache.delete(cache_key)
                    logger.debug(f"Invalidated cache key: {cache_key}")
                except Exception as cache_error:
                    logger.warning(f"Failed to invalidate cache key {cache_key}: {cache_error}")
        except Exception as cache_error:
            logger.warning(f"Error invalidating caches: {cache_error}")
            # Don't fail the request if cache invalidation fails
        
        # Return success response
        return JsonResponse({
            'success': True,
            'symbol': symbol.symbol,
            'signals_generated': len(signals),
            'signals': [signal.id for signal in signals] if signals else [],
            'message': f'Successfully generated {len(signals)} signal(s) for {symbol.symbol}'
        })
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error in generate_signals_manual: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Invalid request format',
            'error_type': 'invalid_json'
        }, status=400)
    except Exception as e:
        error_msg = str(e)
        error_type = type(e).__name__
        logger.error(
            f"Unexpected error in generate_signals_manual: {error_msg}",
            exc_info=True,
            extra={
                'error_type': error_type,
                'error_message': error_msg,
                'user': request.user.username if hasattr(request, 'user') else 'unknown'
            }
        )
        return JsonResponse({
            'success': False,
            'error': 'An unexpected error occurred. Please try again or contact support.',
            'error_type': 'unexpected_error',
            'details': error_msg[:200] if settings.DEBUG else 'Internal server error'
        }, status=500)


@csrf_exempt
@login_required
def reset_signals_for_testing(request):
    """Reset all signals to 'Active' status for testing purposes"""
    try:
        # Only allow in development/testing environment
        if not settings.DEBUG:
            return JsonResponse({
                'success': False,
                'error': 'This endpoint is only available in development mode'
            }, status=403)
        
        # Reset all signals to not executed
        signals_updated = TradingSignal.objects.filter(is_executed=True).update(
            is_executed=False,
            executed_at=None
        )
        
        # Clear related caches
        cache_keys_to_delete = [
            "signal_statistics",
            "signals_api_None_None_true_50"
        ]
        
        for cache_key in cache_keys_to_delete:
            cache.delete(cache_key)
            logger.info(f"Invalidated cache key: {cache_key}")
        
        logger.info(f"Reset {signals_updated} signals for testing")
        
        return JsonResponse({
            'success': True,
            'message': f'Reset {signals_updated} signals for testing',
            'signals_reset': signals_updated
        })
        
    except Exception as e:
        logger.error(f"Error resetting signals for testing: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["POST"])
@login_required
def sync_signal_prices(request):
    """Synchronize prices for all active signals"""
    try:
        from apps.signals.price_sync_service import price_sync_service
        
        # Get all active signals
        active_signals = TradingSignal.objects.filter(
            is_valid=True,
            is_executed=False
        )
        
        synced_count = 0
        errors = []
        
        for signal in active_signals:
            try:
                # Update signal prices using the sync service
                if price_sync_service.update_signal_prices(signal.id):
                    synced_count += 1
            except Exception as e:
                errors.append(f"Error syncing {signal.symbol.symbol}: {str(e)}")
                logger.warning(f"Error syncing signal {signal.id}: {e}")
        
        # Clear signal caches to force refresh
        cache_keys_to_delete = [
            "signal_statistics",
            "signals_api_None_None_true_50"
        ]
        
        for cache_key in cache_keys_to_delete:
            cache.delete(cache_key)
        
        logger.info(f"Successfully synchronized prices for {synced_count} signals")
        
        response_data = {
            'success': True,
            'synced_count': synced_count,
            'total_signals': len(active_signals),
            'message': f'Successfully synchronized prices for {synced_count}/{len(active_signals)} signals'
        }
        
        if errors:
            response_data['warnings'] = errors
        
        return JsonResponse(response_data)
        
    except Exception as e:
        logger.error(f"Error synchronizing signal prices: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["POST"])
@login_required
def clear_signals_cache(request):
    """Clear signals cache - useful when signals are not loading"""
    try:
        
        # Clear all signal-related cache keys
        cache_keys_to_clear = [
            "signal_statistics",
            "signals_api_None_None_true_50",
            "signals_api_None_None_True_50",
        ]
        
        # Try to find and clear all signals_api_* keys (if possible)
        # Note: Django cache doesn't support key pattern matching easily,
        # so we clear known patterns
        cleared_count = 0
        for key in cache_keys_to_clear:
            if cache.get(key):
                cache.delete(key)
                cleared_count += 1
                logger.info(f"Cleared cache key: {key}")
        
        # Also try to clear with None values for symbol/signal_type
        for symbol_val in [None, 'None']:
            for signal_type_val in [None, 'None']:
                for is_valid_val in [True, 'True', 'true']:
                    for limit_val in [50, '50']:
                        cache_key = f"signals_api_{symbol_val}_{signal_type_val}_{is_valid_val}_{limit_val}"
                        if cache.get(cache_key):
                            cache.delete(cache_key)
                            cleared_count += 1
                            logger.info(f"Cleared cache key: {cache_key}")
        
        logger.info(f"Cleared {cleared_count} cache keys")
        
        return JsonResponse({
            'success': True,
            'message': f'Cleared {cleared_count} cache key(s)',
            'cleared_count': cleared_count
        })
        
    except Exception as e:
        logger.error(f"Error clearing signals cache: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["GET"])
@login_required
def signals_diagnostic(request):
    """Diagnostic endpoint to check signals database status"""
    try:
        from django.db import connection
        from datetime import timedelta
        
        # Test database connection first
        db_status = 'connected'
        db_error_detail = None
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            # Test actual query execution
            test_query = TradingSignal.objects.count()
        except Exception as db_error:
            db_status = 'error'
            db_error_detail = str(db_error)
            logger.error(f"Database connection error: {db_error}", exc_info=True)
        
        # Get database statistics
        total_signals = TradingSignal.objects.count()
        valid_signals = TradingSignal.objects.filter(is_valid=True).count()
        invalid_signals = TradingSignal.objects.filter(is_valid=False).count()
        executed_signals = TradingSignal.objects.filter(is_executed=True).count()
        
        # Get recent signals (last 48 hours) - same query as API fallback
        recent_48h_signals = TradingSignal.objects.filter(
            created_at__gte=timezone.now() - timedelta(hours=48)
        ).order_by('-created_at')[:10]
        
        recent_signal_data = []
        for signal in recent_48h_signals:
            recent_signal_data.append({
                'id': signal.id,
                'symbol': signal.symbol.symbol if signal.symbol else None,
                'signal_type': signal.signal_type.name if signal.signal_type else None,
                'is_valid': signal.is_valid,
                'is_executed': signal.is_executed,
                'created_at': signal.created_at.isoformat() if signal.created_at else None
            })
        
        # Test the EXACT query that API uses when no valid signals found
        queryset = TradingSignal.objects.select_related('symbol', 'signal_type')
        valid_count = queryset.filter(is_valid=True).count()
        
        api_query_result = []
        if valid_count == 0:
            # This is the fallback query used in API
            api_queryset = queryset.filter(
                created_at__gte=timezone.now() - timedelta(hours=48)
            ).order_by('-created_at')[:50]
            api_query_result = list(api_queryset.values(
                'id', 'is_valid', 'is_executed', 'created_at',
                'symbol__symbol', 'signal_type__name'
            )[:10])  # Show first 10
            api_query_count = api_queryset.count()
        else:
            api_query_count = valid_count
        
        # Check cache status
        cache_key = "signals_api_None_None_true_50"
        cached_data = cache.get(cache_key)
        cache_status = {
            'exists': cached_data is not None,
            'count': cached_data.get('count', 0) if cached_data else 0,
            'cached_at': cached_data.get('cached_at') if cached_data else None
        }
        
        diagnostic_data = {
            'success': True,
            'database': {
                'status': db_status,
                'error_detail': db_error_detail,
                'total_signals': total_signals,
                'valid_signals': valid_signals,
                'invalid_signals': invalid_signals,
                'executed_signals': executed_signals,
                'recent_48h_count': recent_48h_signals.count(),
            },
            'api_query_test': {
                'valid_count': valid_count,
                'api_would_use_fallback': valid_count == 0,
                'api_query_result_count': api_query_count,
                'api_query_sample': api_query_result[:5],  # First 5 results
            },
            'cache': cache_status,
            'recent_signals_sample': recent_signal_data,
            'timestamp': timezone.now().isoformat()
        }
        
        return JsonResponse(diagnostic_data)
        
    except Exception as e:
        logger.error(f"Error in signals diagnostic: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e),
            'error_type': type(e).__name__
        }, status=500)
