"""
Admin Report Generation Service
Provides comprehensive reporting functionality
"""

from django.db.models import Count, Sum, Avg, Q
from django.utils import timezone
from datetime import timedelta, datetime
from typing import Dict, List, Any, Optional
import logging

from apps.subscription.models import UserProfile, Payment, SubscriptionPlan
from apps.signals.models import TradingSignal
from apps.trading.models import Symbol

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Base class for report generation"""
    
    def generate_report(self, start_date=None, end_date=None, **kwargs):
        """Generate report - to be implemented by subclasses"""
        raise NotImplementedError


class UserActivityReport(ReportGenerator):
    """Generate user activity report"""
    
    def generate_report(self, start_date=None, end_date=None, **kwargs):
        """Generate user activity report"""
        if start_date is None:
            start_date = timezone.now() - timedelta(days=30)
        if end_date is None:
            end_date = timezone.now()
        
        queryset = UserProfile.objects.filter(
            created_at__gte=start_date,
            created_at__lte=end_date
        )
        
        # User registrations
        total_registrations = queryset.count()
        registrations_by_day = (
            queryset.extra(select={'day': 'date(created_at)'})
            .values('day')
            .annotate(count=Count('id'))
            .order_by('day')
        )
        
        # Email verification stats
        verified_count = queryset.filter(email_verified=True).count()
        unverified_count = queryset.filter(email_verified=False).count()
        
        # Social auth stats
        social_auth_count = queryset.exclude(social_provider__isnull=True).count()
        
        # Subscription stats
        subscription_stats = queryset.values('subscription_status').annotate(
            count=Count('id')
        )
        
        return {
            'report_type': 'user_activity',
            'period': {
                'start_date': start_date,
                'end_date': end_date,
            },
            'summary': {
                'total_registrations': total_registrations,
                'verified_users': verified_count,
                'unverified_users': unverified_count,
                'social_auth_users': social_auth_count,
            },
            'registrations_by_day': list(registrations_by_day),
            'subscription_distribution': list(subscription_stats),
        }


class SubscriptionRevenueReport(ReportGenerator):
    """Generate subscription revenue report"""
    
    def generate_report(self, start_date=None, end_date=None, **kwargs):
        """Generate subscription revenue report"""
        if start_date is None:
            start_date = timezone.now() - timedelta(days=30)
        if end_date is None:
            end_date = timezone.now()
        
        payments = Payment.objects.filter(
            created_at__gte=start_date,
            created_at__lte=end_date
        )
        
        # Revenue by status
        revenue_by_status = payments.values('status').annotate(
            total=Sum('amount'),
            count=Count('id')
        )
        
        # Revenue by plan
        revenue_by_plan = payments.values('subscription_plan__name').annotate(
            total=Sum('amount'),
            count=Count('id')
        )
        
        # Revenue by provider
        revenue_by_provider = payments.values('provider').annotate(
            total=Sum('amount'),
            count=Count('id')
        )
        
        # Total revenue
        total_revenue = payments.filter(status='completed').aggregate(
            total=Sum('amount')
        )['total'] or 0
        
        # Revenue by day
        revenue_by_day = (
            payments.filter(status='completed')
            .extra(select={'day': 'date(created_at)'})
            .values('day')
            .annotate(total=Sum('amount'), count=Count('id'))
            .order_by('day')
        )
        
        return {
            'report_type': 'subscription_revenue',
            'period': {
                'start_date': start_date,
                'end_date': end_date,
            },
            'summary': {
                'total_revenue': float(total_revenue),
                'total_payments': payments.count(),
                'completed_payments': payments.filter(status='completed').count(),
                'pending_payments': payments.filter(status='pending').count(),
                'failed_payments': payments.filter(status='failed').count(),
            },
            'revenue_by_status': list(revenue_by_status),
            'revenue_by_plan': list(revenue_by_plan),
            'revenue_by_provider': list(revenue_by_provider),
            'revenue_by_day': list(revenue_by_day),
        }


class SignalPerformanceReport(ReportGenerator):
    """Generate signal performance report"""
    
    def generate_report(self, start_date=None, end_date=None, **kwargs):
        """Generate signal performance report"""
        if start_date is None:
            start_date = timezone.now() - timedelta(days=30)
        if end_date is None:
            end_date = timezone.now()
        
        signals = TradingSignal.objects.filter(
            created_at__gte=start_date,
            created_at__lte=end_date
        )
        
        # Basic stats
        total_signals = signals.count()
        executed_signals = signals.filter(is_executed=True).count()
        profitable_signals = signals.filter(
            is_executed=True, is_profitable=True
        ).count()
        
        # Performance metrics
        win_rate = (profitable_signals / executed_signals * 100) if executed_signals > 0 else 0
        
        total_profit = signals.filter(
            is_executed=True, is_profitable=True, profit_loss__isnull=False
        ).aggregate(total=Sum('profit_loss'))['total'] or 0
        
        total_loss = abs(signals.filter(
            is_executed=True, is_profitable=False, profit_loss__isnull=False
        ).aggregate(total=Sum('profit_loss'))['total'] or 0)
        
        profit_factor = (total_profit / total_loss) if total_loss > 0 else 0
        
        # Performance by signal type
        performance_by_type = signals.filter(is_executed=True).values(
            'signal_type__name'
        ).annotate(
            total=Count('id'),
            profitable=Count('id', filter=Q(is_profitable=True)),
            total_profit=Sum('profit_loss', filter=Q(is_profitable=True)),
        )
        
        # Performance by symbol
        performance_by_symbol = signals.filter(is_executed=True).values(
            'symbol__symbol'
        ).annotate(
            total=Count('id'),
            profitable=Count('id', filter=Q(is_profitable=True)),
            total_profit=Sum('profit_loss', filter=Q(is_profitable=True)),
        ).order_by('-total')[:10]
        
        # Signals by day
        signals_by_day = (
            signals.extra(select={'day': 'date(created_at)'})
            .values('day')
            .annotate(count=Count('id'))
            .order_by('day')
        )
        
        return {
            'report_type': 'signal_performance',
            'period': {
                'start_date': start_date,
                'end_date': end_date,
            },
            'summary': {
                'total_signals': total_signals,
                'executed_signals': executed_signals,
                'profitable_signals': profitable_signals,
                'win_rate': win_rate,
                'total_profit': float(total_profit),
                'total_loss': float(total_loss),
                'profit_factor': float(profit_factor),
            },
            'performance_by_type': list(performance_by_type),
            'performance_by_symbol': list(performance_by_symbol),
            'signals_by_day': list(signals_by_day),
        }


class SystemUsageReport(ReportGenerator):
    """Generate system usage report"""
    
    def generate_report(self, start_date=None, end_date=None, **kwargs):
        """Generate system usage report"""
        if start_date is None:
            start_date = timezone.now() - timedelta(days=30)
        if end_date is None:
            end_date = timezone.now()
        
        # User activity
        active_users = UserProfile.objects.filter(
            updated_at__gte=start_date
        ).count()
        
        # Signal generation
        signals_generated = TradingSignal.objects.filter(
            created_at__gte=start_date,
            created_at__lte=end_date
        ).count()
        
        # Subscription activity
        subscription_changes = UserProfile.objects.filter(
            updated_at__gte=start_date
        ).exclude(subscription_status='inactive').count()
        
        # Payment activity
        payments_processed = Payment.objects.filter(
            created_at__gte=start_date,
            created_at__lte=end_date
        ).count()
        
        return {
            'report_type': 'system_usage',
            'period': {
                'start_date': start_date,
                'end_date': end_date,
            },
            'summary': {
                'active_users': active_users,
                'signals_generated': signals_generated,
                'subscription_changes': subscription_changes,
                'payments_processed': payments_processed,
            },
        }


class ReportService:
    """Service for generating and managing reports"""
    
    REPORT_TYPES = {
        'user_activity': UserActivityReport,
        'subscription_revenue': SubscriptionRevenueReport,
        'signal_performance': SignalPerformanceReport,
        'system_usage': SystemUsageReport,
    }
    
    @classmethod
    def generate_report(cls, report_type, start_date=None, end_date=None, **kwargs):
        """Generate a report of the specified type"""
        if report_type not in cls.REPORT_TYPES:
            raise ValueError(f"Unknown report type: {report_type}")
        
        generator_class = cls.REPORT_TYPES[report_type]
        generator = generator_class()
        
        return generator.generate_report(start_date, end_date, **kwargs)
    
    @classmethod
    def get_available_reports(cls):
        """Get list of available report types"""
        return list(cls.REPORT_TYPES.keys())













