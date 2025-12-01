"""
Advanced Admin Filters
Provides multi-field filtering, date range pickers, and numeric range filters
"""

from django.contrib import admin
from django.utils import timezone
from datetime import timedelta, datetime
from django import forms


class DateRangeFilter(admin.SimpleListFilter):
    """Advanced date range filter with custom date picker"""
    title = 'Date Range'
    parameter_name = 'date_range'
    template = 'admin/filters/date_range_filter.html'
    
    def lookups(self, request, model_admin):
        return (
            ('today', 'Today'),
            ('yesterday', 'Yesterday'),
            ('last_7_days', 'Last 7 Days'),
            ('last_30_days', 'Last 30 Days'),
            ('last_90_days', 'Last 90 Days'),
            ('this_month', 'This Month'),
            ('last_month', 'Last Month'),
            ('this_year', 'This Year'),
            ('custom', 'Custom Range'),
        )
    
    def queryset(self, request, queryset):
        now = timezone.now()
        value = self.value()
        
        if value == 'today':
            return queryset.filter(created_at__date=now.date())
        elif value == 'yesterday':
            yesterday = now - timedelta(days=1)
            return queryset.filter(created_at__date=yesterday.date())
        elif value == 'last_7_days':
            return queryset.filter(created_at__gte=now - timedelta(days=7))
        elif value == 'last_30_days':
            return queryset.filter(created_at__gte=now - timedelta(days=30))
        elif value == 'last_90_days':
            return queryset.filter(created_at__gte=now - timedelta(days=90))
        elif value == 'this_month':
            return queryset.filter(
                created_at__year=now.year,
                created_at__month=now.month
            )
        elif value == 'last_month':
            last_month = now - timedelta(days=30)
            return queryset.filter(
                created_at__year=last_month.year,
                created_at__month=last_month.month
            )
        elif value == 'this_year':
            return queryset.filter(created_at__year=now.year)
        elif value == 'custom':
            # Handle custom date range from request parameters
            start_date = request.GET.get('date_range_start')
            end_date = request.GET.get('date_range_end')
            if start_date and end_date:
                try:
                    start = datetime.strptime(start_date, '%Y-%m-%d')
                    end = datetime.strptime(end_date, '%Y-%m-%d')
                    return queryset.filter(
                        created_at__date__gte=start.date(),
                        created_at__date__lte=end.date()
                    )
                except ValueError:
                    pass
        
        return queryset


class NumericRangeFilter(admin.SimpleListFilter):
    """Filter by numeric range"""
    title = 'Numeric Range'
    parameter_name = 'numeric_range'
    field_name = None  # Should be set in subclass
    
    def lookups(self, request, model_admin):
        return (
            ('0-10', '0 - 10'),
            ('10-50', '10 - 50'),
            ('50-100', '50 - 100'),
            ('100-500', '100 - 500'),
            ('500+', '500+'),
        )
    
    def queryset(self, request, queryset):
        if not self.field_name:
            return queryset
        
        value = self.value()
        if value == '0-10':
            return queryset.filter(**{f'{self.field_name}__gte': 0, f'{self.field_name}__lte': 10})
        elif value == '10-50':
            return queryset.filter(**{f'{self.field_name}__gte': 10, f'{self.field_name}__lte': 50})
        elif value == '10-50':
            return queryset.filter(**{f'{self.field_name}__gte': 50, f'{self.field_name}__lte': 100})
        elif value == '100-500':
            return queryset.filter(**{f'{self.field_name}__gte': 100, f'{self.field_name}__lte': 500})
        elif value == '500+':
            return queryset.filter(**{f'{self.field_name}__gte': 500})
        
        return queryset


class MultiFieldFilter(admin.SimpleListFilter):
    """Base class for multi-field filtering"""
    title = 'Multi-Field Filter'
    parameter_name = 'multi_field'
    
    def lookups(self, request, model_admin):
        return (
            ('all', 'All Fields'),
            ('name', 'Name Only'),
            ('email', 'Email Only'),
            ('username', 'Username Only'),
        )
    
    def queryset(self, request, queryset):
        value = self.value()
        search_term = request.GET.get('q', '')
        
        if not search_term:
            return queryset
        
        if value == 'name' or value is None:
            # Default search behavior
            return queryset
        elif value == 'email':
            return queryset.filter(email__icontains=search_term)
        elif value == 'username':
            return queryset.filter(username__icontains=search_term)
        
        return queryset


class SavedFilterPreset(admin.ModelAdmin):
    """Mixin to add saved filter presets functionality"""
    
    def get_list_filter(self, request):
        filters = super().get_list_filter(request)
        # Add saved presets if any
        return filters
    
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        # Add saved filter presets to context
        extra_context['saved_presets'] = self.get_saved_presets(request)
        return super().changelist_view(request, extra_context)
    
    def get_saved_presets(self, request):
        """Get saved filter presets for the current user"""
        # This can be extended to store presets in database
        return []













