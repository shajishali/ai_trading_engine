"""
ML Migration Service
Handles gradual migration from rule-based to ML-based signal generation
Supports parallel running, A/B testing, and full migration
"""

import logging
import hashlib
from typing import Dict, List, Optional, Tuple
from enum import Enum
from datetime import timedelta
from django.utils import timezone
from django.db.models import Q, Count, Avg
from django.core.cache import cache

from apps.trading.models import Symbol
from apps.signals.models import TradingSignal
from apps.signals.ml_signal_generation_service import MLSignalGenerationService
from apps.signals.database_signal_service import database_signal_service

logger = logging.getLogger(__name__)


class MigrationPhase(Enum):
    """Migration phases"""
    PARALLEL_RUNNING = 'parallel_running'  # Both systems run, compare results
    AB_TESTING = 'ab_testing'  # Split symbols between ML and rule-based
    FULL_MIGRATION = 'full_migration'  # All symbols use ML, rule-based as fallback
    ROLLBACK = 'rollback'  # Revert to rule-based


class MLMigrationService:
    """Service to manage ML migration strategy"""
    
    def __init__(self):
        self.ml_service = None
        self.phase = self._get_current_phase()
        self.config = self._load_config()
        
        # Initialize ML service if needed
        if self.phase != MigrationPhase.ROLLBACK:
            try:
                self.ml_service = MLSignalGenerationService(
                    model_name=self.config.get('ml_model_name', 'signal_xgboost')
                )
            except Exception as e:
                logger.warning(f"ML service initialization failed: {e}. Using rule-based fallback.")
                self.phase = MigrationPhase.ROLLBACK
    
    def _get_current_phase(self) -> MigrationPhase:
        """Get current migration phase from cache or default"""
        # Default to full_migration to use ML model by default
        phase_str = cache.get('ml_migration_phase', 'full_migration')
        try:
            return MigrationPhase(phase_str)
        except ValueError:
            return MigrationPhase.FULL_MIGRATION
    
    def _load_config(self) -> Dict:
        """Load migration configuration"""
        return {
            'ml_model_name': cache.get('ml_model_name', 'signal_xgboost'),
            'ml_weight': float(cache.get('ml_weight', 0.3)),  # Weight for parallel running
            'ml_min_confidence': float(cache.get('ml_min_confidence', 0.5)),
            'ab_test_split': float(cache.get('ab_test_split', 0.5)),  # 50% ML, 50% rule-based
            'ab_test_seed': cache.get('ab_test_seed', 'default_seed'),
        }
    
    def set_phase(self, phase: MigrationPhase):
        """Set migration phase"""
        self.phase = phase
        cache.set('ml_migration_phase', phase.value, timeout=None)
        logger.info(f"Migration phase set to: {phase.value}")
    
    def set_config(self, **kwargs):
        """Update migration configuration"""
        for key, value in kwargs.items():
            if key in self.config:
                self.config[key] = value
                cache.set(f'ml_{key}', value, timeout=None)
        logger.info(f"Migration config updated: {kwargs}")
    
    def get_symbol_group(self, symbol: Symbol) -> str:
        """
        Determine which group a symbol belongs to (for A/B testing)
        
        Returns:
            'ml' or 'rule_based'
        """
        if self.phase != MigrationPhase.AB_TESTING:
            return 'ml' if self.phase == MigrationPhase.FULL_MIGRATION else 'both'
        
        # Deterministic assignment based on symbol ID and seed
        seed = self.config['ab_test_seed']
        hash_input = f"{symbol.id}_{seed}".encode()
        hash_value = int(hashlib.md5(hash_input).hexdigest(), 16)
        
        # Assign based on hash
        split_ratio = self.config['ab_test_split']
        if (hash_value % 100) < (split_ratio * 100):
            return 'ml'
        else:
            return 'rule_based'
    
    def generate_signals_for_symbol(
        self,
        symbol: Symbol,
        prediction_horizon_hours: int = 24
    ) -> List[TradingSignal]:
        """
        Generate signals for a symbol based on current migration phase
        
        Returns:
            List of TradingSignal objects
        """
        if self.phase == MigrationPhase.ROLLBACK:
            return self._generate_rule_based_signals(symbol)
        
        if self.phase == MigrationPhase.PARALLEL_RUNNING:
            return self._generate_parallel_signals(symbol, prediction_horizon_hours)
        
        elif self.phase == MigrationPhase.AB_TESTING:
            group = self.get_symbol_group(symbol)
            if group == 'ml':
                return self._generate_ml_signals(symbol, prediction_horizon_hours)
            else:
                return self._generate_rule_based_signals(symbol)
        
        elif self.phase == MigrationPhase.FULL_MIGRATION:
            try:
                return self._generate_ml_signals(symbol, prediction_horizon_hours)
            except Exception as e:
                logger.error(f"ML signal generation failed for {symbol.symbol}: {e}. Falling back to rule-based.")
                return self._generate_rule_based_signals(symbol)
        
        return []
    
    def _generate_ml_signals(
        self,
        symbol: Symbol,
        prediction_horizon_hours: int
    ) -> List[TradingSignal]:
        """Generate ML signals"""
        if not self.ml_service:
            raise Exception("ML service not initialized")
        
        signals = self.ml_service.generate_signals_for_symbol(
            symbol=symbol,
            prediction_horizon_hours=prediction_horizon_hours,
            min_confidence=self.config['ml_min_confidence']
        )
        
        # Tag signals with migration metadata
        for signal in signals:
            if not signal.metadata:
                signal.metadata = {}
            signal.metadata['migration_phase'] = self.phase.value
            signal.metadata['signal_source'] = 'ml'
            signal.save()
        
        return signals
    
    def _generate_rule_based_signals(self, symbol: Symbol) -> List[TradingSignal]:
        """Generate rule-based signals"""
        from apps.signals.database_data_utils import get_recent_market_data
        
        market_data = get_recent_market_data(symbol, hours_back=24)
        signals = database_signal_service.generate_logical_signals_for_symbol(
            symbol, market_data
        )
        
        # Tag signals with migration metadata
        for signal in signals:
            if not signal.metadata:
                signal.metadata = {}
            signal.metadata['migration_phase'] = self.phase.value
            signal.metadata['signal_source'] = 'rule_based'
            signal.save()
        
        return signals
    
    def _generate_parallel_signals(
        self,
        symbol: Symbol,
        prediction_horizon_hours: int
    ) -> List[TradingSignal]:
        """Generate signals from both systems and combine"""
        ml_signals = []
        rule_signals = []
        
        # Generate ML signals
        try:
            ml_signals = self._generate_ml_signals(symbol, prediction_horizon_hours)
        except Exception as e:
            logger.warning(f"ML signal generation failed for {symbol.symbol}: {e}")
        
        # Generate rule-based signals
        try:
            rule_signals = self._generate_rule_based_signals(symbol)
        except Exception as e:
            logger.warning(f"Rule-based signal generation failed for {symbol.symbol}: {e}")
        
        # Combine signals with weights
        combined_signals = self._combine_signals(
            ml_signals,
            rule_signals,
            ml_weight=self.config['ml_weight']
        )
        
        return combined_signals
    
    def _combine_signals(
        self,
        ml_signals: List[TradingSignal],
        rule_signals: List[TradingSignal],
        ml_weight: float
    ) -> List[TradingSignal]:
        """
        Combine ML and rule-based signals with weights
        
        Args:
            ml_signals: ML-generated signals
            rule_signals: Rule-based signals
            ml_weight: Weight for ML signals (0-1)
        
        Returns:
            Combined list of signals
        """
        combined = []
        rule_weight = 1.0 - ml_weight
        
        # Add ML signals with adjusted confidence
        for signal in ml_signals:
            # Adjust confidence based on weight
            original_confidence = signal.confidence_score
            adjusted_confidence = original_confidence * ml_weight
            signal.confidence_score = adjusted_confidence
            signal.metadata['original_confidence'] = float(original_confidence)
            signal.metadata['ml_weight'] = ml_weight
            combined.append(signal)
        
        # Add rule-based signals with adjusted confidence
        for signal in rule_signals:
            # Adjust confidence based on weight
            original_confidence = signal.confidence_score
            adjusted_confidence = original_confidence * rule_weight
            signal.confidence_score = adjusted_confidence
            signal.metadata['original_confidence'] = float(original_confidence)
            signal.metadata['rule_weight'] = rule_weight
            combined.append(signal)
        
        # Sort by adjusted confidence
        combined.sort(key=lambda s: s.confidence_score, reverse=True)
        
        return combined
    
    def get_migration_stats(self, days: int = 7) -> Dict:
        """Get migration statistics"""
        start_date = timezone.now() - timedelta(days=days)
        
        # Get signals by source
        ml_signals = TradingSignal.objects.filter(
            created_at__gte=start_date,
            metadata__signal_source='ml'
        )
        
        rule_signals = TradingSignal.objects.filter(
            created_at__gte=start_date,
            metadata__signal_source='rule_based'
        )
        
        # Calculate metrics
        ml_count = ml_signals.count()
        rule_count = rule_signals.count()
        total_count = ml_count + rule_count
        
        ml_avg_confidence = ml_signals.aggregate(avg=Avg('confidence_score'))['avg'] or 0.0
        rule_avg_confidence = rule_signals.aggregate(avg=Avg('confidence_score'))['avg'] or 0.0
        
        # Execution metrics (if available)
        ml_executed = ml_signals.filter(is_executed=True).count()
        rule_executed = rule_signals.filter(is_executed=True).count()
        
        ml_profitable = ml_signals.filter(is_executed=True, is_profitable=True).count()
        rule_profitable = rule_signals.filter(is_executed=True, is_profitable=True).count()
        
        ml_win_rate = ml_profitable / ml_executed if ml_executed > 0 else 0.0
        rule_win_rate = rule_profitable / rule_executed if rule_executed > 0 else 0.0
        
        return {
            'phase': self.phase.value,
            'period_days': days,
            'ml_signals': {
                'count': ml_count,
                'avg_confidence': float(ml_avg_confidence),
                'executed': ml_executed,
                'profitable': ml_profitable,
                'win_rate': float(ml_win_rate)
            },
            'rule_based_signals': {
                'count': rule_count,
                'avg_confidence': float(rule_avg_confidence),
                'executed': rule_executed,
                'profitable': rule_profitable,
                'win_rate': float(rule_win_rate)
            },
            'total_signals': total_count,
            'ml_percentage': (ml_count / total_count * 100) if total_count > 0 else 0.0
        }


# Global instance
ml_migration_service = MLMigrationService()

