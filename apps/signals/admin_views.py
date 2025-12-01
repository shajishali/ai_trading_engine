"""
Custom Admin Views for Signal Analytics and Statistics
"""

from django.contrib import admin
from django.template.response import TemplateResponse
from django.urls import path
from django.utils import timezone
from django.db.models import Count, Avg, Sum, Q
from datetime import timedelta

from .models import TradingSignal, SignalType
from .admin_performance import SignalPerformanceService


class SignalAnalyticsMixin:
    """Mixin for signal analytics views"""
    
    def get_signal_statistics(self, queryset=None):
        """Get comprehensive signal statistics"""
        if queryset is None:
            queryset = TradingSignal.objects.all()
        
        service = SignalPerformanceService()
        now = timezone.now()
        
        # Basic counts
        total_signals = queryset.count()
        active_signals = queryset.filter(is_valid=True).count()
        executed_signals = queryset.filter(is_executed=True).count()
        profitable_signals = queryset.filter(
            is_executed=True, is_profitable=True
        ).count()
        
        # Performance metrics
        win_rate = service.calculate_win_rate(queryset)
        profit_factor = service.calculate_profit_factor(queryset)
        avg_pl = service.calculate_avg_profit_loss(queryset)
        
        # Distribution
        signal_distribution = service.get_signal_distribution(queryset)
        
        # Time-based stats
        signals_today = queryset.filter(created_at__date=now.date()).count()
        signals_this_week = queryset.filter(
            created_at__gte=now - timedelta(days=7)
        ).count()
        signals_this_month = queryset.filter(
            created_at__gte=now - timedelta(days=30)
        ).count()
        
        # Quality metrics
        avg_confidence = queryset.aggregate(
            avg=Avg('confidence_score')
        )['avg'] or 0.0
        
        avg_quality = queryset.aggregate(
            avg=Avg('quality_score')
        )['avg'] or 0.0
        
        # Top performers
        top_symbols = service.get_top_performing_symbols(queryset, limit=10)
        
        # Performance by timeframe
        performance_by_timeframe = service.get_performance_by_timeframe(queryset)
        
        # Confidence vs performance
        confidence_performance = service.get_confidence_vs_performance(queryset)
        
        return {
            'total_signals': total_signals,
            'active_signals': active_signals,
            'executed_signals': executed_signals,
            'profitable_signals': profitable_signals,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'avg_profit': avg_pl['avg_profit'],
            'avg_loss': avg_pl['avg_loss'],
            'avg_total_pl': avg_pl['avg_total'],
            'signal_distribution': signal_distribution,
            'signals_today': signals_today,
            'signals_this_week': signals_this_week,
            'signals_this_month': signals_this_month,
            'avg_confidence': float(avg_confidence),
            'avg_quality': float(avg_quality),
            'top_symbols': top_symbols,
            'performance_by_timeframe': performance_by_timeframe,
            'confidence_performance': confidence_performance,
        }


class SignalAnalyticsAdmin(SignalAnalyticsMixin, admin.ModelAdmin):
    """Admin view for signal analytics dashboard"""
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('analytics/', self.admin_site.admin_view(self.analytics_view), name='signal_analytics'),
            path('performance/', self.admin_site.admin_view(self.performance_view), name='signal_performance'),
        ]
        return custom_urls + urls
    
    def analytics_view(self, request):
        """Display signal analytics dashboard"""
        # Get filter parameters
        date_range = request.GET.get('date_range', 'last_30_days')
        signal_type = request.GET.get('signal_type', None)
        
        # Build queryset based on filters
        queryset = TradingSignal.objects.all()
        
        if date_range == 'today':
            queryset = queryset.filter(created_at__date=timezone.now().date())
        elif date_range == 'last_7_days':
            queryset = queryset.filter(created_at__gte=timezone.now() - timedelta(days=7))
        elif date_range == 'last_30_days':
            queryset = queryset.filter(created_at__gte=timezone.now() - timedelta(days=30))
        elif date_range == 'last_90_days':
            queryset = queryset.filter(created_at__gte=timezone.now() - timedelta(days=90))
        elif date_range == 'this_month':
            now = timezone.now()
            queryset = queryset.filter(
                created_at__year=now.year,
                created_at__month=now.month
            )
        elif date_range == 'this_year':
            queryset = queryset.filter(created_at__year=timezone.now().year)
        
        if signal_type:
            queryset = queryset.filter(signal_type_id=signal_type)
        
        stats = self.get_signal_statistics(queryset)
        
        # Get signal types for filter
        signal_types = SignalType.objects.all()
        
        context = {
            **self.admin_site.each_context(request),
            'title': 'Signal Analytics Dashboard',
            'stats': stats,
            'date_range': date_range,
            'signal_type': signal_type,
            'signal_types': signal_types,
        }
        
        return TemplateResponse(request, 'admin/signals/analytics.html', context)
    
    def performance_view(self, request):
        """Display signal performance tracking"""
        service = SignalPerformanceService()
        
        # Get filter parameters
        days = int(request.GET.get('days', 30))
        
        # Get all signals
        queryset = TradingSignal.objects.all()
        
        # Get performance trends
        trends = service.get_performance_trends(queryset, days=days)
        
        # Get overall stats
        stats = self.get_signal_statistics(queryset)
        
        context = {
            **self.admin_site.each_context(request),
            'title': 'Signal Performance Tracking',
            'stats': stats,
            'trends': trends,
            'days': days,
        }
        
        return TemplateResponse(request, 'admin/signals/performance.html', context)













