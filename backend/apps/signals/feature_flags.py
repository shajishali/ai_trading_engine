"""
Feature Flags and Migration Strategy for Database-Driven Signal Generation
Phase 4: Implement migration and rollback strategy with feature flags
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum

from django.utils import timezone
from django.core.cache import cache
from django.conf import settings

from apps.trading.models import Symbol
from apps.signals.models import TradingSignal, SignalAlert
from apps.signals.database_signal_service import database_signal_service
from apps.signals.database_signal_monitoring import database_signal_monitor

logger = logging.getLogger(__name__)


class SignalGenerationMode(Enum):
    """Signal generation modes"""
    LIVE_API = "live_api"
    DATABASE = "database"
    HYBRID = "hybrid"
    AUTO = "auto"


class MigrationStatus(Enum):
    """Migration status"""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


class FeatureFlags:
    """Feature flags for database-driven signal generation"""
    
    def __init__(self):
        self.cache_timeout = 300  # 5 minutes
        self.default_mode = getattr(settings, 'DEFAULT_SIGNAL_MODE', SignalGenerationMode.LIVE_API)
        self.migration_enabled = getattr(settings, 'MIGRATION_ENABLED', True)
        
        # Migration configuration
        self.migration_config = {
            'rollback_threshold': 0.7,  # Rollback if success rate < 70%
            'monitoring_period_hours': 24,  # Monitor for 24 hours
            'gradual_rollout_percentage': 10,  # Start with 10% of symbols
            'health_check_interval': 300  # 5 minutes
        }
    
    def get_current_mode(self) -> SignalGenerationMode:
        """Get current signal generation mode"""
        try:
            cached_mode = cache.get('signal_generation_mode')
            if cached_mode:
                return SignalGenerationMode(cached_mode)
            
            # Default mode
            return self.default_mode
            
        except Exception as e:
            logger.error(f"Error getting current mode: {e}")
            return self.default_mode
    
    def set_mode(self, mode: SignalGenerationMode, force: bool = False) -> bool:
        """Set signal generation mode"""
        try:
            if not force and not self._can_change_mode(mode):
                logger.warning(f"Cannot change mode to {mode.value} - conditions not met")
                return False
            
            # Set mode in cache
            cache.set('signal_generation_mode', mode.value, self.cache_timeout)
            
            # Log mode change
            logger.info(f"Signal generation mode changed to: {mode.value}")
            
            # Create alert
            self._create_mode_change_alert(mode)
            
            return True
            
        except Exception as e:
            logger.error(f"Error setting mode: {e}")
            return False
    
    def _can_change_mode(self, new_mode: SignalGenerationMode) -> bool:
        """Check if mode can be changed"""
        try:
            current_mode = self.get_current_mode()
            
            # Can always change to live API (rollback)
            if new_mode == SignalGenerationMode.LIVE_API:
                return True
            
            # Check system health for database/hybrid modes
            if new_mode in [SignalGenerationMode.DATABASE, SignalGenerationMode.HYBRID]:
                health_status = self._check_system_health()
                if health_status != "HEALTHY":
                    logger.warning(f"Cannot change to {new_mode.value} - system health: {health_status}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking if mode can be changed: {e}")
            return False
    
    def _check_system_health(self) -> str:
        """Check system health for mode change"""
        try:
            # Get database health
            from apps.signals.database_data_utils import get_database_health_status
            db_health = get_database_health_status()
            
            if db_health.get('status') == 'CRITICAL':
                return "CRITICAL"
            elif db_health.get('status') == 'WARNING':
                return "DEGRADED"
            else:
                return "HEALTHY"
                
        except Exception as e:
            logger.error(f"Error checking system health: {e}")
            return "UNKNOWN"
    
    def _create_mode_change_alert(self, mode: SignalGenerationMode):
        """Create alert for mode change"""
        try:
            SignalAlert.objects.create(
                title=f"Signal Generation Mode Changed",
                message=f"Signal generation mode changed to {mode.value}",
                priority="MEDIUM",
                alert_type="SYSTEM_CHANGE",
                is_read=False
            )
            
        except Exception as e:
            logger.error(f"Error creating mode change alert: {e}")
    
    def start_migration(self, target_mode: SignalGenerationMode) -> Dict[str, Any]:
        """Start migration to database-driven signals"""
        try:
            if not self.migration_enabled:
                return {'error': 'Migration is disabled'}
            
            logger.info(f"Starting migration to {target_mode.value}")
            
            # Check prerequisites
            prerequisites = self._check_migration_prerequisites(target_mode)
            if not prerequisites['can_migrate']:
                return {'error': f"Cannot migrate: {prerequisites['reason']}"}
            
            # Set migration status
            cache.set('migration_status', MigrationStatus.IN_PROGRESS.value, 3600)
            cache.set('migration_start_time', timezone.now().isoformat(), 3600)
            cache.set('target_mode', target_mode.value, 3600)
            
            # Start gradual rollout
            rollout_result = self._start_gradual_rollout(target_mode)
            
            migration_info = {
                'status': MigrationStatus.IN_PROGRESS.value,
                'target_mode': target_mode.value,
                'start_time': timezone.now().isoformat(),
                'rollout_percentage': self.migration_config['gradual_rollout_percentage'],
                'monitoring_period_hours': self.migration_config['monitoring_period_hours'],
                'rollout_result': rollout_result
            }
            
            logger.info(f"Migration started successfully")
            return migration_info
            
        except Exception as e:
            logger.error(f"Error starting migration: {e}")
            return {'error': str(e)}
    
    def _check_migration_prerequisites(self, target_mode: SignalGenerationMode) -> Dict[str, Any]:
        """Check migration prerequisites"""
        try:
            # Check database health
            db_health = self._check_system_health()
            if db_health != "HEALTHY":
                return {
                    'can_migrate': False,
                    'reason': f"Database health is {db_health}"
                }
            
            # Check data freshness
            from apps.signals.database_data_utils import get_database_health_status
            health_status = get_database_health_status()
            data_age = health_status.get('latest_data_age_hours', 0)
            
            if data_age > 2:
                return {
                    'can_migrate': False,
                    'reason': f"Data is {data_age:.1f} hours old"
                }
            
            # Check active symbols
            active_symbols = health_status.get('active_symbols', 0)
            if active_symbols < 50:
                return {
                    'can_migrate': False,
                    'reason': f"Only {active_symbols} active symbols"
                }
            
            return {'can_migrate': True, 'reason': 'All prerequisites met'}
            
        except Exception as e:
            logger.error(f"Error checking migration prerequisites: {e}")
            return {'can_migrate': False, 'reason': str(e)}
    
    def _start_gradual_rollout(self, target_mode: SignalGenerationMode) -> Dict[str, Any]:
        """Start gradual rollout of new mode"""
        try:
            # Get symbols for rollout
            symbols = Symbol.objects.filter(is_active=True, is_crypto_symbol=True)
            rollout_count = int(len(symbols) * self.migration_config['gradual_rollout_percentage'] / 100)
            rollout_symbols = symbols[:rollout_count]
            
            # Set rollout symbols
            cache.set('rollout_symbols', [s.symbol for s in rollout_symbols], 3600)
            
            # Start monitoring
            self._start_migration_monitoring()
            
            return {
                'rollout_symbols': [s.symbol for s in rollout_symbols],
                'rollout_count': rollout_count,
                'total_symbols': len(symbols),
                'rollout_percentage': self.migration_config['gradual_rollout_percentage']
            }
            
        except Exception as e:
            logger.error(f"Error starting gradual rollout: {e}")
            return {'error': str(e)}
    
    def _start_migration_monitoring(self):
        """Start monitoring migration progress"""
        try:
            # Set up monitoring
            cache.set('migration_monitoring_start', timezone.now().isoformat(), 3600)
            cache.set('migration_health_checks', 0, 3600)
            
            logger.info("Migration monitoring started")
            
        except Exception as e:
            logger.error(f"Error starting migration monitoring: {e}")
    
    def check_migration_status(self) -> Dict[str, Any]:
        """Check current migration status"""
        try:
            status = cache.get('migration_status', MigrationStatus.NOT_STARTED.value)
            start_time = cache.get('migration_start_time')
            target_mode = cache.get('target_mode')
            
            if status == MigrationStatus.NOT_STARTED.value:
                return {
                    'status': status,
                    'message': 'No migration in progress'
                }
            
            # Get monitoring data
            monitoring_data = self._get_migration_monitoring_data()
            
            # Check if migration should be completed or rolled back
            if status == MigrationStatus.IN_PROGRESS.value:
                decision = self._evaluate_migration_decision(monitoring_data)
                if decision['action'] == 'complete':
                    self._complete_migration()
                    status = MigrationStatus.COMPLETED.value
                elif decision['action'] == 'rollback':
                    self._rollback_migration()
                    status = MigrationStatus.ROLLED_BACK.value
            
            return {
                'status': status,
                'start_time': start_time,
                'target_mode': target_mode,
                'monitoring_data': monitoring_data,
                'next_check': timezone.now() + timedelta(minutes=5)
            }
            
        except Exception as e:
            logger.error(f"Error checking migration status: {e}")
            return {'error': str(e)}
    
    def _get_migration_monitoring_data(self) -> Dict[str, Any]:
        """Get migration monitoring data"""
        try:
            # Get signal quality data
            quality_report = database_signal_monitor.monitor_signal_quality()
            
            # Get performance data
            performance_report = database_signal_monitor.monitor_signal_generation_performance()
            
            # Get database health
            from apps.signals.database_data_utils import get_database_health_status
            db_health = get_database_health_status()
            
            return {
                'quality_score': quality_report.get('quality_score', 0),
                'performance_score': performance_report.get('performance_score', 0),
                'database_health': db_health.get('status', 'UNKNOWN'),
                'signal_count': performance_report.get('total_signals', 0),
                'success_rate': performance_report.get('success_rate', 0)
            }
            
        except Exception as e:
            logger.error(f"Error getting migration monitoring data: {e}")
            return {}
    
    def _evaluate_migration_decision(self, monitoring_data: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate whether to complete or rollback migration"""
        try:
            quality_score = monitoring_data.get('quality_score', 0)
            performance_score = monitoring_data.get('performance_score', 0)
            success_rate = monitoring_data.get('success_rate', 0)
            
            # Check rollback conditions
            if (quality_score < self.migration_config['rollback_threshold'] * 100 or
                performance_score < self.migration_config['rollback_threshold'] * 100 or
                success_rate < self.migration_config['rollback_threshold']):
                
                return {
                    'action': 'rollback',
                    'reason': f'Performance below threshold: Quality={quality_score:.1f}, Performance={performance_score:.1f}, Success={success_rate:.1f}'
                }
            
            # Check completion conditions
            if (quality_score >= 80 and performance_score >= 80 and success_rate >= 0.8):
                return {
                    'action': 'complete',
                    'reason': f'Performance above threshold: Quality={quality_score:.1f}, Performance={performance_score:.1f}, Success={success_rate:.1f}'
                }
            
            # Continue monitoring
            return {
                'action': 'continue',
                'reason': 'Performance within acceptable range, continuing monitoring'
            }
            
        except Exception as e:
            logger.error(f"Error evaluating migration decision: {e}")
            return {'action': 'continue', 'reason': 'Error in evaluation'}
    
    def _complete_migration(self):
        """Complete migration to new mode"""
        try:
            target_mode = cache.get('target_mode')
            if target_mode:
                self.set_mode(SignalGenerationMode(target_mode), force=True)
            
            cache.set('migration_status', MigrationStatus.COMPLETED.value, 3600)
            cache.set('migration_completion_time', timezone.now().isoformat(), 3600)
            
            # Create completion alert
            SignalAlert.objects.create(
                title="Migration Completed",
                message=f"Migration to {target_mode} completed successfully",
                priority="LOW",
                alert_type="MIGRATION_COMPLETE",
                is_read=False
            )
            
            logger.info(f"Migration completed successfully to {target_mode}")
            
        except Exception as e:
            logger.error(f"Error completing migration: {e}")
    
    def _rollback_migration(self):
        """Rollback migration to previous mode"""
        try:
            # Rollback to live API mode
            self.set_mode(SignalGenerationMode.LIVE_API, force=True)
            
            cache.set('migration_status', MigrationStatus.ROLLED_BACK.value, 3600)
            cache.set('migration_rollback_time', timezone.now().isoformat(), 3600)
            
            # Create rollback alert
            SignalAlert.objects.create(
                title="Migration Rolled Back",
                message="Migration rolled back to live API mode due to performance issues",
                priority="HIGH",
                alert_type="MIGRATION_ROLLBACK",
                is_read=False
            )
            
            logger.warning("Migration rolled back due to performance issues")
            
        except Exception as e:
            logger.error(f"Error rolling back migration: {e}")
    
    def force_rollback(self) -> bool:
        """Force rollback to live API mode"""
        try:
            logger.info("Forcing rollback to live API mode")
            
            # Set mode to live API
            self.set_mode(SignalGenerationMode.LIVE_API, force=True)
            
            # Update migration status
            cache.set('migration_status', MigrationStatus.ROLLED_BACK.value, 3600)
            cache.set('migration_rollback_time', timezone.now().isoformat(), 3600)
            
            # Create force rollback alert
            SignalAlert.objects.create(
                title="Forced Rollback",
                message="Migration forcefully rolled back to live API mode",
                priority="CRITICAL",
                alert_type="FORCED_ROLLBACK",
                is_read=False
            )
            
            logger.info("Forced rollback completed")
            return True
            
        except Exception as e:
            logger.error(f"Error forcing rollback: {e}")
            return False
    
    def get_migration_history(self) -> List[Dict[str, Any]]:
        """Get migration history"""
        try:
            # This would typically be stored in a database table
            # For now, return cached data
            history = []
            
            start_time = cache.get('migration_start_time')
            completion_time = cache.get('migration_completion_time')
            rollback_time = cache.get('migration_rollback_time')
            target_mode = cache.get('target_mode')
            
            if start_time:
                history.append({
                    'event': 'migration_started',
                    'timestamp': start_time,
                    'target_mode': target_mode
                })
            
            if completion_time:
                history.append({
                    'event': 'migration_completed',
                    'timestamp': completion_time,
                    'target_mode': target_mode
                })
            
            if rollback_time:
                history.append({
                    'event': 'migration_rolled_back',
                    'timestamp': rollback_time,
                    'target_mode': target_mode
                })
            
            return history
            
        except Exception as e:
            logger.error(f"Error getting migration history: {e}")
            return []
    
    def get_feature_flags_status(self) -> Dict[str, Any]:
        """Get current feature flags status"""
        try:
            return {
                'current_mode': self.get_current_mode().value,
                'migration_enabled': self.migration_enabled,
                'migration_status': cache.get('migration_status', MigrationStatus.NOT_STARTED.value),
                'migration_config': self.migration_config,
                'system_health': self._check_system_health(),
                'can_change_mode': self._can_change_mode(SignalGenerationMode.DATABASE)
            }
            
        except Exception as e:
            logger.error(f"Error getting feature flags status: {e}")
            return {'error': str(e)}


# Global instance
feature_flags = FeatureFlags()














