"""
Duplicate Signal Removal Service

This service identifies and removes duplicate trading signals from the database.
Duplicates are identified based on core signal characteristics rather than just timestamps.
"""

import logging
from typing import Dict, List, Tuple, Set
from decimal import Decimal
from datetime import datetime, timedelta
from django.db import transaction
from django.utils import timezone
from collections import defaultdict

from apps.signals.models import TradingSignal
from apps.trading.models import Symbol

logger = logging.getLogger(__name__)


class DuplicateSignalRemovalService:
    """Service for identifying and removing duplicate trading signals"""
    
    def __init__(self):
        self.duplicate_groups = []
        self.removed_count = 0
        self.kept_count = 0
        
    def identify_duplicates(self, 
                          symbol: str = None, 
                          start_date: datetime = None, 
                          end_date: datetime = None,
                          tolerance_percentage: float = 0.01) -> Dict:
        """
        Identify duplicate signals based on core characteristics
        
        Args:
            symbol: Optional symbol to filter by
            start_date: Optional start date for filtering
            end_date: Optional end date for filtering
            tolerance_percentage: Price tolerance for considering signals as duplicates (default 1%)
            
        Returns:
            Dict containing duplicate groups and statistics
        """
        try:
            logger.info("Starting duplicate signal identification")
            
            # Build base query
            queryset = TradingSignal.objects.select_related('symbol', 'signal_type')
            
            if symbol:
                queryset = queryset.filter(symbol__symbol__iexact=symbol)
            
            if start_date:
                queryset = queryset.filter(created_at__gte=start_date)
            
            if end_date:
                queryset = queryset.filter(created_at__lte=end_date)
            
            # Order by creation date to process chronologically
            signals = queryset.order_by('created_at')
            
            logger.info(f"Analyzing {signals.count()} signals for duplicates")
            
            # Group signals by core characteristics
            signal_groups = self._group_signals_by_characteristics(signals, tolerance_percentage)
            
            # Identify duplicate groups
            duplicate_groups = []
            for group_key, group_signals in signal_groups.items():
                if len(group_signals) > 1:
                    # Sort by creation date to keep the earliest
                    group_signals.sort(key=lambda x: x.created_at)
                    duplicate_groups.append({
                        'group_key': group_key,
                        'signals': group_signals,
                        'count': len(group_signals),
                        'earliest_signal': group_signals[0],
                        'duplicate_signals': group_signals[1:]
                    })
            
            self.duplicate_groups = duplicate_groups
            
            # Calculate statistics
            total_duplicates = sum(len(group['duplicate_signals']) for group in duplicate_groups)
            total_groups = len(duplicate_groups)
            
            result = {
                'success': True,
                'total_signals_analyzed': signals.count(),
                'duplicate_groups_found': total_groups,
                'total_duplicate_signals': total_duplicates,
                'duplicate_groups': duplicate_groups,
                'statistics': {
                    'signals_to_remove': total_duplicates,
                    'signals_to_keep': signals.count() - total_duplicates,
                    'duplicate_percentage': (total_duplicates / signals.count() * 100) if signals.count() > 0 else 0
                }
            }
            
            logger.info(f"Found {total_groups} duplicate groups with {total_duplicates} duplicate signals")
            return result
            
        except Exception as e:
            logger.error(f"Error identifying duplicates: {e}")
            return {
                'success': False,
                'error': str(e),
                'duplicate_groups': [],
                'statistics': {}
            }
    
    def _group_signals_by_characteristics(self, signals, tolerance_percentage: float) -> Dict[str, List[TradingSignal]]:
        """
        Group signals by their core characteristics
        
        Args:
            signals: QuerySet of TradingSignal objects
            tolerance_percentage: Price tolerance for grouping
            
        Returns:
            Dict mapping group keys to lists of signals
        """
        groups = defaultdict(list)
        
        for signal in signals:
            # Create a group key based on core characteristics
            group_key = self._create_signal_group_key(signal, tolerance_percentage)
            groups[group_key].append(signal)
        
        return dict(groups)
    
    def _create_signal_group_key(self, signal: TradingSignal, tolerance_percentage: float) -> str:
        """
        Create a group key for signal based on core characteristics
        
        Args:
            signal: TradingSignal object
            tolerance_percentage: Price tolerance for grouping
            
        Returns:
            String key representing the signal group
        """
        # Core characteristics that define a signal
        symbol = signal.symbol.symbol
        signal_type = signal.signal_type.name if signal.signal_type else 'UNKNOWN'
        strength = signal.strength
        confidence_level = signal.confidence_level
        
        # Price characteristics (rounded to tolerance)
        entry_price = self._round_to_tolerance(float(signal.entry_price), tolerance_percentage)
        target_price = self._round_to_tolerance(float(signal.target_price), tolerance_percentage)
        stop_loss = self._round_to_tolerance(float(signal.stop_loss), tolerance_percentage)
        
        # Risk-reward ratio (rounded)
        risk_reward = round(float(signal.risk_reward_ratio), 2) if signal.risk_reward_ratio else 0
        
        # Quality score (rounded)
        quality_score = round(float(signal.quality_score), 2) if signal.quality_score else 0
        
        # Timeframe
        timeframe = signal.timeframe or '1D'
        
        # Entry point type
        entry_point_type = signal.entry_point_type or 'UNKNOWN'
        
        # Create composite key
        group_key = f"{symbol}|{signal_type}|{strength}|{confidence_level}|{entry_price}|{target_price}|{stop_loss}|{risk_reward}|{quality_score}|{timeframe}|{entry_point_type}"
        
        return group_key
    
    def _round_to_tolerance(self, price: float, tolerance_percentage: float) -> float:
        """
        Round price to tolerance level to group similar prices
        
        Args:
            price: Price to round
            tolerance_percentage: Tolerance percentage (e.g., 0.01 for 1%)
            
        Returns:
            Rounded price
        """
        if price == 0:
            return 0
        
        # Calculate tolerance amount
        tolerance_amount = price * tolerance_percentage
        
        # Round to nearest tolerance
        return round(price / tolerance_amount) * tolerance_amount
    
    def remove_duplicates(self, 
                         symbol: str = None,
                         start_date: datetime = None,
                         end_date: datetime = None,
                         dry_run: bool = True,
                         tolerance_percentage: float = 0.01) -> Dict:
        """
        Remove duplicate signals from the database
        
        Args:
            symbol: Optional symbol to filter by
            start_date: Optional start date for filtering
            end_date: Optional end date for filtering
            dry_run: If True, only identify duplicates without removing them
            tolerance_percentage: Price tolerance for considering signals as duplicates
            
        Returns:
            Dict containing removal results and statistics
        """
        try:
            logger.info(f"Starting duplicate removal (dry_run={dry_run})")
            
            # First identify duplicates
            identification_result = self.identify_duplicates(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                tolerance_percentage=tolerance_percentage
            )
            
            if not identification_result['success']:
                return identification_result
            
            duplicate_groups = identification_result['duplicate_groups']
            
            if not duplicate_groups:
                return {
                    'success': True,
                    'message': 'No duplicates found',
                    'removed_count': 0,
                    'kept_count': identification_result['total_signals_analyzed'],
                    'duplicate_groups': []
                }
            
            # Collect signals to remove
            signals_to_remove = []
            signals_to_keep = []
            
            for group in duplicate_groups:
                # Keep the earliest signal
                earliest_signal = group['earliest_signal']
                signals_to_keep.append(earliest_signal)
                
                # Mark duplicates for removal
                for duplicate_signal in group['duplicate_signals']:
                    signals_to_remove.append(duplicate_signal)
            
            if dry_run:
                logger.info(f"DRY RUN: Would remove {len(signals_to_remove)} duplicate signals")
                return {
                    'success': True,
                    'dry_run': True,
                    'message': f'DRY RUN: Would remove {len(signals_to_remove)} duplicate signals',
                    'removed_count': 0,
                    'kept_count': len(signals_to_keep),
                    'signals_to_remove': [s.id for s in signals_to_remove],
                    'signals_to_keep': [s.id for s in signals_to_keep],
                    'duplicate_groups': duplicate_groups
                }
            
            # Actually remove duplicates
            with transaction.atomic():
                removed_ids = []
                for signal in signals_to_remove:
                    signal_id = signal.id
                    signal.delete()
                    removed_ids.append(signal_id)
                
                self.removed_count = len(removed_ids)
                self.kept_count = len(signals_to_keep)
            
            logger.info(f"Successfully removed {self.removed_count} duplicate signals")
            
            return {
                'success': True,
                'dry_run': False,
                'message': f'Successfully removed {self.removed_count} duplicate signals',
                'removed_count': self.removed_count,
                'kept_count': self.kept_count,
                'removed_signal_ids': removed_ids,
                'kept_signal_ids': [s.id for s in signals_to_keep],
                'duplicate_groups': duplicate_groups
            }
            
        except Exception as e:
            logger.error(f"Error removing duplicates: {e}")
            return {
                'success': False,
                'error': str(e),
                'removed_count': 0,
                'kept_count': 0
            }
    
    def get_duplicate_statistics(self, symbol: str = None) -> Dict:
        """
        Get statistics about duplicates in the database
        
        Args:
            symbol: Optional symbol to filter by
            
        Returns:
            Dict containing duplicate statistics
        """
        try:
            # Get all signals
            queryset = TradingSignal.objects.select_related('symbol', 'signal_type')
            
            if symbol:
                queryset = queryset.filter(symbol__symbol__iexact=symbol)
            
            total_signals = queryset.count()
            
            # Identify duplicates
            identification_result = self.identify_duplicates(symbol=symbol)
            
            if not identification_result['success']:
                return identification_result
            
            duplicate_groups = identification_result['duplicate_groups']
            total_duplicates = identification_result['total_duplicate_signals']
            
            # Calculate additional statistics
            symbols_with_duplicates = set()
            signal_types_with_duplicates = set()
            
            for group in duplicate_groups:
                for signal in group['signals']:
                    symbols_with_duplicates.add(signal.symbol.symbol)
                    if signal.signal_type:
                        signal_types_with_duplicates.add(signal.signal_type.name)
            
            # Time-based analysis
            duplicate_time_ranges = []
            for group in duplicate_groups:
                if len(group['signals']) > 1:
                    earliest = min(s.created_at for s in group['signals'])
                    latest = max(s.created_at for s in group['signals'])
                    time_diff = (latest - earliest).total_seconds() / 3600  # hours
                    duplicate_time_ranges.append(time_diff)
            
            avg_duplicate_time_span = sum(duplicate_time_ranges) / len(duplicate_time_ranges) if duplicate_time_ranges else 0
            
            return {
                'success': True,
                'total_signals': total_signals,
                'total_duplicates': total_duplicates,
                'duplicate_percentage': (total_duplicates / total_signals * 100) if total_signals > 0 else 0,
                'duplicate_groups_count': len(duplicate_groups),
                'symbols_with_duplicates': list(symbols_with_duplicates),
                'signal_types_with_duplicates': list(signal_types_with_duplicates),
                'avg_duplicate_time_span_hours': round(avg_duplicate_time_span, 2),
                'max_duplicate_time_span_hours': max(duplicate_time_ranges) if duplicate_time_ranges else 0,
                'min_duplicate_time_span_hours': min(duplicate_time_ranges) if duplicate_time_ranges else 0
            }
            
        except Exception as e:
            logger.error(f"Error getting duplicate statistics: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def cleanup_old_duplicates(self, days_old: int = 30, dry_run: bool = True) -> Dict:
        """
        Clean up duplicates older than specified days
        
        Args:
            days_old: Remove duplicates older than this many days
            dry_run: If True, only identify duplicates without removing them
            
        Returns:
            Dict containing cleanup results
        """
        try:
            cutoff_date = timezone.now() - timedelta(days=days_old)
            
            logger.info(f"Cleaning up duplicates older than {days_old} days (before {cutoff_date})")
            
            return self.remove_duplicates(
                start_date=None,  # No start date limit
                end_date=cutoff_date,
                dry_run=dry_run
            )
            
        except Exception as e:
            logger.error(f"Error cleaning up old duplicates: {e}")
            return {
                'success': False,
                'error': str(e)
            }


# Global service instance
duplicate_removal_service = DuplicateSignalRemovalService()
