"""
Hybrid signal generation service
Combines database-driven signals with live API fallback
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from django.utils import timezone
from django.core.cache import cache

from apps.trading.models import Symbol
from apps.signals.database_signal_service import database_signal_service
from apps.signals.database_data_utils import get_database_health_status, validate_data_quality
from apps.signals.services import SignalGenerationService
from apps.signals.models import TradingSignal

logger = logging.getLogger(__name__)


class HybridSignalService:
    """Hybrid service that uses database data with live API fallback"""
    
    def __init__(self):
        self.database_service = database_signal_service
        self.live_api_service = SignalGenerationService()
        self.fallback_threshold_hours = 2  # Fallback if data older than 2 hours
        self.min_data_quality = 0.8  # Minimum data quality percentage
        
    def generate_signals_for_all_coins(self) -> Dict[str, any]:
        """Generate signals using hybrid approach (database + live API fallback)"""
        logger.info("Starting hybrid signal generation for all coins...")
        
        # Check database health and data quality
        database_health = self._assess_database_health()
        
        if database_health['use_database']:
            logger.info("Using database signals (primary method)")
            return self._generate_database_signals()
        else:
            logger.warning(f"Falling back to live API signals: {database_health['reason']}")
            return self._generate_live_api_signals()
    
    def generate_signals_for_symbol(self, symbol: Symbol) -> List[TradingSignal]:
        """Generate signals for a specific symbol using hybrid approach"""
        try:
            # Check symbol-specific data quality
            symbol_quality = self._assess_symbol_data_quality(symbol)
            
            if symbol_quality['use_database']:
                logger.info(f"Using database signals for {symbol.symbol}")
                return self._generate_database_signals_for_symbol(symbol)
            else:
                logger.warning(f"Falling back to live API for {symbol.symbol}: {symbol_quality['reason']}")
                return self._generate_live_api_signals_for_symbol(symbol)
                
        except Exception as e:
            logger.error(f"Error in hybrid signal generation for {symbol.symbol}: {e}")
            # Final fallback to live API
            return self._generate_live_api_signals_for_symbol(symbol)
    
    def _assess_database_health(self) -> Dict[str, any]:
        """Assess overall database health for signal generation"""
        try:
            # Check database health status
            health_status = get_database_health_status()
            
            # Check data freshness
            data_age_hours = health_status.get('latest_data_age_hours', 999)
            is_fresh = data_age_hours <= self.fallback_threshold_hours
            
            # Check system status
            is_healthy = health_status['status'] in ['HEALTHY', 'WARNING']
            
            # Check data availability
            active_symbols = health_status.get('active_symbols', 0)
            has_sufficient_data = active_symbols >= 50  # Minimum symbols with data
            
            use_database = is_fresh and is_healthy and has_sufficient_data
            
            reason = None
            if not is_fresh:
                reason = f"Data too old: {data_age_hours:.1f} hours"
            elif not is_healthy:
                reason = f"Database health: {health_status['status']}"
            elif not has_sufficient_data:
                reason = f"Insufficient data: {active_symbols} symbols"
            
            return {
                'use_database': use_database,
                'reason': reason,
                'health_status': health_status,
                'data_age_hours': data_age_hours,
                'is_fresh': is_fresh,
                'is_healthy': is_healthy,
                'has_sufficient_data': has_sufficient_data
            }
            
        except Exception as e:
            logger.error(f"Error assessing database health: {e}")
            return {
                'use_database': False,
                'reason': f'Health check error: {e}',
                'health_status': {'status': 'ERROR'},
                'data_age_hours': 999,
                'is_fresh': False,
                'is_healthy': False,
                'has_sufficient_data': False
            }
    
    def _assess_symbol_data_quality(self, symbol: Symbol) -> Dict[str, any]:
        """Assess data quality for a specific symbol"""
        try:
            # Validate symbol data quality
            quality = validate_data_quality(symbol, hours_back=24)
            
            # Check if data is valid and fresh
            is_valid = quality['is_valid']
            is_fresh = quality.get('data_age_hours', 999) <= self.fallback_threshold_hours
            is_complete = quality.get('completeness', 0) >= self.min_data_quality
            
            use_database = is_valid and is_fresh and is_complete
            
            reason = None
            if not is_valid:
                reason = f"Invalid data: {quality['reason']}"
            elif not is_fresh:
                reason = f"Data too old: {quality.get('data_age_hours', 0):.1f} hours"
            elif not is_complete:
                reason = f"Low completeness: {quality.get('completeness', 0):.1%}"
            
            return {
                'use_database': use_database,
                'reason': reason,
                'quality': quality,
                'is_valid': is_valid,
                'is_fresh': is_fresh,
                'is_complete': is_complete
            }
            
        except Exception as e:
            logger.error(f"Error assessing symbol data quality for {symbol.symbol}: {e}")
            return {
                'use_database': False,
                'reason': f'Quality check error: {e}',
                'quality': {'is_valid': False},
                'is_valid': False,
                'is_fresh': False,
                'is_complete': False
            }
    
    def _generate_database_signals(self) -> Dict[str, any]:
        """Generate signals using database data"""
        try:
            result = self.database_service.generate_best_signals_for_all_coins()
            result['signal_source'] = 'database'
            result['method'] = 'database_primary'
            
            logger.info(
                f"Database signal generation completed: "
                f"{result['total_signals_generated']} signals generated"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Database signal generation failed: {e}")
            # Fallback to live API
            return self._generate_live_api_signals_with_fallback(e)
    
    def _generate_live_api_signals(self) -> Dict[str, any]:
        """Generate signals using live API data"""
        try:
            result = self.live_api_service.generate_best_signals_for_all_coins()
            result['signal_source'] = 'live_api'
            result['method'] = 'live_api_fallback'
            
            logger.info(
                f"Live API signal generation completed: "
                f"{result.get('total_signals_generated', 0)} signals generated"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Live API signal generation failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'signal_source': 'live_api',
                'method': 'live_api_failed'
            }
    
    def _generate_live_api_signals_with_fallback(self, database_error: Exception) -> Dict[str, any]:
        """Generate live API signals with database error context"""
        logger.warning(f"Database signals failed ({database_error}), falling back to live API")
        
        result = self._generate_live_api_signals()
        result['fallback_reason'] = f'Database error: {database_error}'
        result['database_error'] = str(database_error)
        
        return result
    
    def _generate_database_signals_for_symbol(self, symbol: Symbol) -> List[TradingSignal]:
        """Generate database signals for a specific symbol"""
        try:
            from apps.signals.database_data_utils import get_recent_market_data
            market_data = get_recent_market_data(symbol, hours_back=24)
            
            signals = self.database_service.generate_logical_signals_for_symbol(symbol, market_data)
            
            # Mark signals with database source
            for signal in signals:
                signal.data_source = 'database'
                signal.save()
            
            logger.info(f"Generated {len(signals)} database signals for {symbol.symbol}")
            return signals
            
        except Exception as e:
            logger.error(f"Database signal generation failed for {symbol.symbol}: {e}")
            # Fallback to live API
            return self._generate_live_api_signals_for_symbol(symbol)
    
    def _generate_live_api_signals_for_symbol(self, symbol: Symbol) -> List[TradingSignal]:
        """Generate live API signals for a specific symbol"""
        try:
            signals = self.live_api_service.generate_signals_for_symbol(symbol)
            
            # Mark signals with live API source
            for signal in signals:
                signal.data_source = 'live_api'
                signal.save()
            
            logger.info(f"Generated {len(signals)} live API signals for {symbol.symbol}")
            return signals
            
        except Exception as e:
            logger.error(f"Live API signal generation failed for {symbol.symbol}: {e}")
            return []
    
    def get_signal_generation_stats(self) -> Dict[str, any]:
        """Get statistics about signal generation methods used"""
        try:
            # Get recent signals by source
            recent_signals = TradingSignal.objects.filter(
                created_at__gte=timezone.now() - timedelta(hours=24)
            )
            
            database_signals = recent_signals.filter(data_source='database').count()
            live_api_signals = recent_signals.filter(data_source='live_api').count()
            total_signals = recent_signals.count()
            
            # Calculate percentages
            database_percentage = (database_signals / total_signals * 100) if total_signals > 0 else 0
            live_api_percentage = (live_api_signals / total_signals * 100) if total_signals > 0 else 0
            
            # Get database health
            health_status = get_database_health_status()
            
            stats = {
                'total_signals_24h': total_signals,
                'database_signals': database_signals,
                'live_api_signals': live_api_signals,
                'database_percentage': database_percentage,
                'live_api_percentage': live_api_percentage,
                'database_health': health_status,
                'timestamp': timezone.now()
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting signal generation stats: {e}")
            return {
                'error': str(e),
                'timestamp': timezone.now()
            }
    
    def force_database_mode(self) -> bool:
        """Force the service to use database mode (for testing)"""
        try:
            # Clear any cache that might affect decision
            cache.delete('database_health_status')
            cache.delete('hybrid_mode_decision')
            
            logger.info("Forced database mode enabled")
            return True
            
        except Exception as e:
            logger.error(f"Error forcing database mode: {e}")
            return False
    
    def force_live_api_mode(self) -> bool:
        """Force the service to use live API mode (for testing)"""
        try:
            # Set cache to force live API mode
            cache.set('force_live_api_mode', True, 3600)  # 1 hour
            
            logger.info("Forced live API mode enabled")
            return True
            
        except Exception as e:
            logger.error(f"Error forcing live API mode: {e}")
            return False
    
    def reset_to_auto_mode(self) -> bool:
        """Reset to automatic mode selection"""
        try:
            # Clear forced mode cache
            cache.delete('force_live_api_mode')
            cache.delete('database_health_status')
            cache.delete('hybrid_mode_decision')
            
            logger.info("Reset to automatic mode selection")
            return True
            
        except Exception as e:
            logger.error(f"Error resetting to auto mode: {e}")
            return False


# Global instance
hybrid_signal_service = HybridSignalService()