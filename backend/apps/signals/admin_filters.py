from django.contrib import admin
from django.utils import timezone
from datetime import timedelta


class SignalDateRangeFilter(admin.SimpleListFilter):
    """Filter signals by date range"""
    title = 'Date Range'
    parameter_name = 'date_range'
    
    def lookups(self, request, model_admin):
        return (
            ('today', 'Today'),
            ('last_7_days', 'Last 7 Days'),
            ('last_30_days', 'Last 30 Days'),
            ('last_90_days', 'Last 90 Days'),
            ('this_month', 'This Month'),
            ('this_year', 'This Year'),
        )
    
    def queryset(self, request, queryset):
        now = timezone.now()
        if self.value() == 'today':
            return queryset.filter(created_at__date=now.date())
        elif self.value() == 'last_7_days':
            return queryset.filter(created_at__gte=now - timedelta(days=7))
        elif self.value() == 'last_30_days':
            return queryset.filter(created_at__gte=now - timedelta(days=30))
        elif self.value() == 'last_90_days':
            return queryset.filter(created_at__gte=now - timedelta(days=90))
        elif self.value() == 'this_month':
            return queryset.filter(
                created_at__year=now.year,
                created_at__month=now.month
            )
        elif self.value() == 'this_year':
            return queryset.filter(created_at__year=now.year)
        return queryset


class SignalPerformanceFilter(admin.SimpleListFilter):
    """Filter signals by performance"""
    title = 'Performance'
    parameter_name = 'performance'
    
    def lookups(self, request, model_admin):
        return (
            ('profitable', 'Profitable'),
            ('unprofitable', 'Unprofitable'),
            ('executed', 'Executed'),
            ('not_executed', 'Not Executed'),
            ('high_confidence', 'High Confidence (>80%)'),
            ('medium_confidence', 'Medium Confidence (50-80%)'),
            ('low_confidence', 'Low Confidence (<50%)'),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'profitable':
            return queryset.filter(is_executed=True, is_profitable=True)
        elif self.value() == 'unprofitable':
            return queryset.filter(is_executed=True, is_profitable=False)
        elif self.value() == 'executed':
            return queryset.filter(is_executed=True)
        elif self.value() == 'not_executed':
            return queryset.filter(is_executed=False)
        elif self.value() == 'high_confidence':
            return queryset.filter(confidence_score__gte=0.8)
        elif self.value() == 'medium_confidence':
            return queryset.filter(confidence_score__gte=0.5, confidence_score__lt=0.8)
        elif self.value() == 'low_confidence':
            return queryset.filter(confidence_score__lt=0.5)
        return queryset


class SignalStrengthFilter(admin.SimpleListFilter):
    """Filter signals by strength"""
    title = 'Signal Strength'
    parameter_name = 'strength'
    
    def lookups(self, request, model_admin):
        return (
            ('very_strong', 'Very Strong'),
            ('strong', 'Strong'),
            ('moderate', 'Moderate'),
            ('weak', 'Weak'),
        )
    
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(strength=self.value().upper())
        return queryset


class SignalTimeframeFilter(admin.SimpleListFilter):
    """Filter signals by timeframe"""
    title = 'Timeframe'
    parameter_name = 'timeframe'
    
    def lookups(self, request, model_admin):
        return (
            ('1M', '1 Minute'),
            ('5M', '5 Minutes'),
            ('15M', '15 Minutes'),
            ('30M', '30 Minutes'),
            ('1H', '1 Hour'),
            ('4H', '4 Hours'),
            ('1D', '1 Day'),
            ('1W', '1 Week'),
        )
    
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(timeframe=self.value())
        return queryset


class SignalQualityFilter(admin.SimpleListFilter):
    """Filter signals by quality score"""
    title = 'Quality Score'
    parameter_name = 'quality'
    
    def lookups(self, request, model_admin):
        return (
            ('excellent', 'Excellent (≥80%)'),
            ('good', 'Good (60-80%)'),
            ('fair', 'Fair (40-60%)'),
            ('poor', 'Poor (<40%)'),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'excellent':
            return queryset.filter(quality_score__gte=0.8)
        elif self.value() == 'good':
            return queryset.filter(quality_score__gte=0.6, quality_score__lt=0.8)
        elif self.value() == 'fair':
            return queryset.filter(quality_score__gte=0.4, quality_score__lt=0.6)
        elif self.value() == 'poor':
            return queryset.filter(quality_score__lt=0.4)
        return queryset













