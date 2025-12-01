"""
Signal Performance Tracking Service
Calculates and tracks signal performance metrics
"""

from django.db.models import Avg, Count, Sum, Q, F
from django.utils import timezone
from datetime import timedelta
from typing import Dict, List, Optional
from decimal import Decimal

from .models import TradingSignal


class SignalPerformanceService:
    """Service for calculating signal performance metrics"""
    
    @staticmethod
    def calculate_win_rate(queryset) -> float:
        """Calculate win rate for a queryset of signals"""
        executed = queryset.filter(is_executed=True)
        if not executed.exists():
            return 0.0
        
        profitable = executed.filter(is_profitable=True).count()
        total = executed.count()
        
        return profitable / total if total > 0 else 0.0
    
    @staticmethod
    def calculate_profit_factor(queryset) -> float:
        """Calculate profit factor for a queryset of signals"""
        executed = queryset.filter(is_executed=True)
        if not executed.exists():
            return 0.0
        
        total_profit = executed.filter(
            is_profitable=True,
            profit_loss__isnull=False
        ).aggregate(
            total=Sum('profit_loss')
        )['total'] or Decimal('0')
        
        total_loss = abs(executed.filter(
            is_profitable=False,
            profit_loss__isnull=False
        ).aggregate(
            total=Sum('profit_loss')
        )['total'] or Decimal('0'))
        
        if total_loss == 0:
            return float(total_profit) if total_profit > 0 else 0.0
        
        return float(total_profit / total_loss)
    
    @staticmethod
    def calculate_avg_profit_loss(queryset) -> Dict[str, float]:
        """Calculate average profit and loss"""
        executed = queryset.filter(is_executed=True, profit_loss__isnull=False)
        
        if not executed.exists():
            return {'avg_profit': 0.0, 'avg_loss': 0.0, 'avg_total': 0.0}
        
        profitable = executed.filter(is_profitable=True)
        unprofitable = executed.filter(is_profitable=False)
        
        avg_profit = float(
            profitable.aggregate(avg=Avg('profit_loss'))['avg'] or 0.0
        )
        avg_loss = float(
            abs(unprofitable.aggregate(avg=Avg('profit_loss'))['avg'] or 0.0)
        )
        avg_total = float(
            executed.aggregate(avg=Avg('profit_loss'))['avg'] or 0.0
        )
        
        return {
            'avg_profit': avg_profit,
            'avg_loss': avg_loss,
            'avg_total': avg_total
        }
    
    @staticmethod
    def get_signal_distribution(queryset) -> Dict[str, int]:
        """Get signal distribution by type"""
        return dict(
            queryset.values('signal_type__name')
            .annotate(count=Count('id'))
            .values_list('signal_type__name', 'count')
        )
    
    @staticmethod
    def get_top_performing_symbols(queryset, limit: int = 10) -> List[Dict]:
        """Get top performing symbols by win rate"""
        executed = queryset.filter(is_executed=True)
        
        symbols = (
            executed.values('symbol__symbol', 'symbol__name')
            .annotate(
                total_signals=Count('id'),
                profitable_signals=Count('id', filter=Q(is_profitable=True)),
                total_profit=Sum('profit_loss', filter=Q(is_profitable=True)),
                avg_confidence=Avg('confidence_score')
            )
            .order_by('-profitable_signals')[:limit]
        )
        
        result = []
        for symbol in symbols:
            win_rate = (
                symbol['profitable_signals'] / symbol['total_signals']
                if symbol['total_signals'] > 0 else 0.0
            )
            result.append({
                'symbol': symbol['symbol__symbol'],
                'name': symbol['symbol__name'],
                'total_signals': symbol['total_signals'],
                'profitable_signals': symbol['profitable_signals'],
                'win_rate': win_rate,
                'total_profit': float(symbol['total_profit'] or 0),
                'avg_confidence': float(symbol['avg_confidence'] or 0)
            })
        
        return result
    
    @staticmethod
    def get_performance_by_timeframe(queryset) -> Dict[str, Dict]:
        """Get performance metrics by timeframe"""
        timeframes = queryset.values('timeframe').distinct()
        result = {}
        
        for tf in timeframes:
            timeframe = tf['timeframe']
            if not timeframe:
                continue
            
            tf_queryset = queryset.filter(timeframe=timeframe)
            executed = tf_queryset.filter(is_executed=True)
            
            if executed.exists():
                win_rate = SignalPerformanceService.calculate_win_rate(tf_queryset)
                profit_factor = SignalPerformanceService.calculate_profit_factor(tf_queryset)
                total_signals = tf_queryset.count()
                executed_count = executed.count()
                
                result[timeframe] = {
                    'total_signals': total_signals,
                    'executed_count': executed_count,
                    'win_rate': win_rate,
                    'profit_factor': profit_factor
                }
        
        return result
    
    @staticmethod
    def get_performance_trends(queryset, days: int = 30) -> List[Dict]:
        """Get performance trends over time"""
        now = timezone.now()
        start_date = now - timedelta(days=days)
        
        daily_performance = []
        current_date = start_date.date()
        
        while current_date <= now.date():
            day_queryset = queryset.filter(created_at__date=current_date)
            executed = day_queryset.filter(is_executed=True)
            
            if executed.exists():
                win_rate = SignalPerformanceService.calculate_win_rate(day_queryset)
                total_signals = day_queryset.count()
                executed_count = executed.count()
                
                daily_performance.append({
                    'date': current_date.isoformat(),
                    'total_signals': total_signals,
                    'executed_count': executed_count,
                    'win_rate': win_rate
                })
            
            current_date += timedelta(days=1)
        
        return daily_performance
    
    @staticmethod
    def get_confidence_vs_performance(queryset) -> Dict[str, float]:
        """Analyze correlation between confidence score and actual performance"""
        executed = queryset.filter(is_executed=True)
        
        if not executed.exists():
            return {}
        
        # Group by confidence ranges
        high_confidence = executed.filter(confidence_score__gte=0.8)
        medium_confidence = executed.filter(
            confidence_score__gte=0.5,
            confidence_score__lt=0.8
        )
        low_confidence = executed.filter(confidence_score__lt=0.5)
        
        result = {}
        
        for name, qs in [
            ('high', high_confidence),
            ('medium', medium_confidence),
            ('low', low_confidence)
        ]:
            if qs.exists():
                win_rate = SignalPerformanceService.calculate_win_rate(qs)
                result[name] = {
                    'win_rate': win_rate,
                    'count': qs.count(),
                    'avg_confidence': float(qs.aggregate(avg=Avg('confidence_score'))['avg'] or 0)
                }
        
        return result













