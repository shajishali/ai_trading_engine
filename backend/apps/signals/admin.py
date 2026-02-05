from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Avg, Count, Q
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils import timezone

from apps.signals.models import (
    SignalType, SignalFactor, TradingSignal, SignalFactorContribution,
    MarketRegime, SignalPerformance, SignalAlert, HourlyBestSignal
)
from apps.signals.admin_filters import (
    SignalDateRangeFilter, SignalPerformanceFilter, SignalStrengthFilter,
    SignalTimeframeFilter, SignalQualityFilter
)
from apps.signals.admin_performance import SignalPerformanceService
from apps.core.admin_exports import export_queryset
from apps.core.admin_search import EnhancedSearchMixin


@admin.register(SignalType)
class SignalTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'description', 'color_display', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'description']
    ordering = ['name']
    
    def color_display(self, obj):
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            obj.color,
            obj.color
        )
    color_display.short_description = 'Color'


@admin.register(SignalFactor)
class SignalFactorAdmin(admin.ModelAdmin):
    list_display = ['name', 'factor_type', 'weight', 'is_active']
    list_filter = ['factor_type', 'is_active']
    search_fields = ['name', 'description']
    ordering = ['factor_type', 'name']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'factor_type', 'description')
        }),
        ('Configuration', {
            'fields': ('weight', 'is_active')
        }),
    )


class SignalFactorContributionInline(admin.TabularInline):
    model = SignalFactorContribution
    extra = 0
    readonly_fields = ['contribution']
    fields = ['factor', 'score', 'weight', 'contribution']


@admin.register(TradingSignal)
class TradingSignalAdmin(EnhancedSearchMixin, admin.ModelAdmin):
    """Enhanced Trading Signal Admin with time filters and performance tracking"""
    
    list_display = [
        'symbol', 'signal_type', 'strength_display', 'confidence_display',
        'quality_display', 'risk_reward_display', 'performance_indicator',
        'timeframe', 'is_valid', 'created_at'
    ]
    list_filter = [
        SignalDateRangeFilter, SignalPerformanceFilter, SignalStrengthFilter,
        SignalTimeframeFilter, SignalQualityFilter,
        'signal_type', 'confidence_level', 'is_valid', 'is_executed', 'created_at'
    ]
    search_fields = ['symbol__symbol', 'symbol__name', 'signal_type__name']
    readonly_fields = [
        'created_at', 'updated_at', 'is_expired', 'time_to_expiry',
        'performance_summary', 'related_signals_link'
    ]
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    list_per_page = 50
    
    fieldsets = (
        ('Signal Information', {
            'fields': ('symbol', 'signal_type', 'strength', 'confidence_score', 'confidence_level', 'timeframe')
        }),
        ('Price Targets', {
            'fields': ('entry_price', 'target_price', 'stop_loss', 'risk_reward_ratio')
        }),
        ('Quality Metrics', {
            'fields': ('quality_score', 'is_valid', 'expires_at')
        }),
        ('Contributing Factors', {
            'fields': ('technical_score', 'sentiment_score', 'news_score', 'volume_score', 'pattern_score', 'economic_score', 'sector_score')
        }),
        ('Performance Tracking', {
            'fields': ('is_executed', 'executed_at', 'execution_price', 'is_profitable', 'profit_loss', 'performance_summary')
        }),
        ('Related Signals', {
            'fields': ('related_signals_link',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'notes')
        }),
    )
    
    inlines = [SignalFactorContributionInline]
    
    def strength_display(self, obj):
        """Display signal strength with color coding"""
        colors = {
            'VERY_STRONG': 'green',
            'STRONG': 'lightgreen',
            'MODERATE': 'orange',
            'WEAK': 'red'
        }
        color = colors.get(obj.strength, 'gray')
        # Get display value from choices
        strength_choices = dict(TradingSignal.SIGNAL_STRENGTHS)
        strength_label = strength_choices.get(obj.strength, obj.strength)
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            strength_label
        )
    strength_display.short_description = 'Strength'
    strength_display.admin_order_field = 'strength'
    
    def confidence_display(self, obj):
        """Display confidence score with color coding"""
        color = 'green' if obj.confidence_score >= 0.8 else 'orange' if obj.confidence_score >= 0.7 else 'red'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1%}</span>',
            color,
            obj.confidence_score
        )
    confidence_display.short_description = 'Confidence'
    confidence_display.admin_order_field = 'confidence_score'
    
    def quality_display(self, obj):
        color = 'green' if obj.quality_score >= 0.8 else 'orange' if obj.quality_score >= 0.6 else 'red'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1%}</span>',
            color,
            obj.quality_score
        )
    quality_display.short_description = 'Quality'
    
    def risk_reward_display(self, obj):
        """Display risk-reward ratio with color coding"""
        if not obj.risk_reward_ratio:
            return '-'
        color = 'green' if obj.risk_reward_ratio >= 3.0 else 'orange' if obj.risk_reward_ratio >= 2.0 else 'red'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.2f}</span>',
            color,
            obj.risk_reward_ratio
        )
    risk_reward_display.short_description = 'R:R Ratio'
    risk_reward_display.admin_order_field = 'risk_reward_ratio'
    
    def performance_indicator(self, obj):
        """Display performance indicator for executed signals"""
        if not obj.is_executed:
            return format_html('<span style="color: gray;">Not Executed</span>')
        
        if obj.is_profitable is None:
            return format_html('<span style="color: orange;">Pending</span>')
        
        if obj.is_profitable:
            profit = float(obj.profit_loss) if obj.profit_loss else 0
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ ${:.2f}</span>',
                profit
            )
        else:
            loss = abs(float(obj.profit_loss)) if obj.profit_loss else 0
            return format_html(
                '<span style="color: red; font-weight: bold;">✗ ${:.2f}</span>',
                loss
            )
    performance_indicator.short_description = 'Performance'
    
    def performance_summary(self, obj):
        """Display performance summary in detail view"""
        if not obj.is_executed:
            return 'Signal not yet executed'
        
        summary = []
        if obj.executed_at:
            summary.append(f"Executed: {obj.executed_at.strftime('%Y-%m-%d %H:%M')}")
        if obj.execution_price:
            summary.append(f"Execution Price: ${obj.execution_price}")
        if obj.is_profitable is not None:
            status = "Profitable" if obj.is_profitable else "Unprofitable"
            color = "green" if obj.is_profitable else "red"
            summary.append(f'Status: <span style="color: {color}; font-weight: bold;">{status}</span>')
        if obj.profit_loss:
            summary.append(f"P/L: ${obj.profit_loss}")
        
        return format_html('<br>'.join(summary)) if summary else 'No performance data'
    performance_summary.short_description = 'Performance Summary'
    
    def related_signals_link(self, obj):
        """Link to related signals for the same symbol"""
        if not obj.symbol:
            return '-'
        
        related_count = TradingSignal.objects.filter(
            symbol=obj.symbol
        ).exclude(id=obj.id).count()
        
        if related_count > 0:
            url = reverse('admin:signals_tradingsignal_changelist')
            url += f'?symbol__id__exact={obj.symbol.id}'
            return format_html(
                '<a href="{}">View {} related signal(s) for {}</a>',
                url,
                related_count,
                obj.symbol.symbol
            )
        return 'No related signals'
    related_signals_link.short_description = 'Related Signals'
    
    def is_expired(self, obj):
        return obj.is_expired
    is_expired.boolean = True
    is_expired.short_description = 'Expired'
    
    def time_to_expiry(self, obj):
        if not obj.expires_at:
            return 'No expiry'
        time_left = obj.time_to_expiry
        if time_left:
            hours = time_left.total_seconds() / 3600
            return f"{hours:.1f} hours"
        return 'Expired'
    time_to_expiry.short_description = 'Time to Expiry'
    
    actions = [
        'mark_as_executed', 'mark_as_invalid', 'regenerate_signals',
        'export_selected_csv', 'export_selected_excel', 'export_selected_json',
        'calculate_performance'
    ]
    
    def mark_as_executed(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(
            is_executed=True,
            executed_at=timezone.now()
        )
        self.message_user(request, f"{updated} signals marked as executed.")
    mark_as_executed.short_description = "Mark selected signals as executed"
    
    def mark_as_invalid(self, request, queryset):
        updated = queryset.update(is_valid=False)
        self.message_user(request, f"{updated} signals marked as invalid.")
    mark_as_invalid.short_description = "Mark selected signals as invalid"
    
    def regenerate_signals(self, request, queryset):
        from apps.signals.services import SignalGenerationService
        signal_service = SignalGenerationService()
        regenerated = 0
        
        for signal in queryset:
            try:
                new_signals = signal_service.generate_signals_for_symbol(signal.symbol)
                regenerated += len(new_signals)
            except Exception as e:
                self.message_user(request, f"Error regenerating signals for {signal.symbol}: {e}")
        
        self.message_user(request, f"Generated {regenerated} new signals.")
    regenerate_signals.short_description = "Regenerate signals for selected symbols"
    
    def export_selected_csv(self, request, queryset):
        """Export selected signals to CSV"""
        fields = [
            'symbol__symbol', 'signal_type__name', 'strength', 'confidence_score',
            'quality_score', 'entry_price', 'target_price', 'stop_loss',
            'risk_reward_ratio', 'timeframe', 'is_valid', 'is_executed',
            'is_profitable', 'profit_loss', 'created_at'
        ]
        headers = [
            'Symbol', 'Signal Type', 'Strength', 'Confidence', 'Quality',
            'Entry Price', 'Target Price', 'Stop Loss', 'R:R Ratio',
            'Timeframe', 'Is Valid', 'Is Executed', 'Is Profitable',
            'Profit/Loss', 'Created At'
        ]
        filename = f"signals_export_{timezone.now().strftime('%Y%m%d_%H%M%S')}"
        return export_queryset(queryset.select_related('symbol', 'signal_type'), 'csv', fields, headers, filename)
    export_selected_csv.short_description = "Export selected signals to CSV"
    
    def export_selected_excel(self, request, queryset):
        """Export selected signals to Excel"""
        fields = [
            'symbol__symbol', 'signal_type__name', 'strength', 'confidence_score',
            'quality_score', 'entry_price', 'target_price', 'stop_loss',
            'risk_reward_ratio', 'timeframe', 'is_valid', 'is_executed',
            'is_profitable', 'profit_loss', 'created_at'
        ]
        headers = [
            'Symbol', 'Signal Type', 'Strength', 'Confidence', 'Quality',
            'Entry Price', 'Target Price', 'Stop Loss', 'R:R Ratio',
            'Timeframe', 'Is Valid', 'Is Executed', 'Is Profitable',
            'Profit/Loss', 'Created At'
        ]
        filename = f"signals_export_{timezone.now().strftime('%Y%m%d_%H%M%S')}"
        return export_queryset(queryset.select_related('symbol', 'signal_type'), 'excel', fields, headers, filename)
    export_selected_excel.short_description = "Export selected signals to Excel"
    
    def export_selected_json(self, request, queryset):
        """Export selected signals to JSON"""
        fields = [
            'symbol__symbol', 'signal_type__name', 'strength', 'confidence_score',
            'quality_score', 'entry_price', 'target_price', 'stop_loss',
            'risk_reward_ratio', 'timeframe', 'is_valid', 'is_executed',
            'is_profitable', 'profit_loss', 'created_at'
        ]
        filename = f"signals_export_{timezone.now().strftime('%Y%m%d_%H%M%S')}"
        return export_queryset(queryset.select_related('symbol', 'signal_type'), 'json', fields, None, filename)
    export_selected_json.short_description = "Export selected signals to JSON"
    
    def calculate_performance(self, request, queryset):
        """Calculate and display performance metrics for selected signals"""
        service = SignalPerformanceService()
        
        win_rate = service.calculate_win_rate(queryset)
        profit_factor = service.calculate_profit_factor(queryset)
        avg_pl = service.calculate_avg_profit_loss(queryset)
        
        message = (
            f"Performance Metrics for {queryset.count()} signals:\n"
            f"Win Rate: {win_rate:.1%}\n"
            f"Profit Factor: {profit_factor:.2f}\n"
            f"Average Profit: ${avg_pl['avg_profit']:.2f}\n"
            f"Average Loss: ${avg_pl['avg_loss']:.2f}\n"
            f"Average P/L: ${avg_pl['avg_total']:.2f}"
        )
        
        self.message_user(request, message)
    calculate_performance.short_description = "Calculate performance metrics"
    
    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        qs = super().get_queryset(request)
        return qs.select_related('symbol', 'signal_type')


@admin.register(SignalFactorContribution)
class SignalFactorContributionAdmin(admin.ModelAdmin):
    list_display = ['signal', 'factor', 'score_display', 'weight', 'contribution_display']
    list_filter = ['factor__factor_type', 'factor']
    search_fields = ['signal__symbol__symbol', 'factor__name']
    ordering = ['-signal__created_at']
    
    def score_display(self, obj):
        color = 'green' if obj.score > 0 else 'red' if obj.score < 0 else 'gray'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.3f}</span>',
            color,
            obj.score
        )
    score_display.short_description = 'Score'
    
    def contribution_display(self, obj):
        color = 'green' if obj.contribution > 0 else 'red' if obj.contribution < 0 else 'gray'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.3f}</span>',
            color,
            obj.contribution
        )
    contribution_display.short_description = 'Contribution'


@admin.register(MarketRegime)
class MarketRegimeAdmin(admin.ModelAdmin):
    list_display = ['name', 'volatility_display', 'trend_display', 'confidence_display', 'created_at']
    list_filter = ['name', 'created_at']
    search_fields = ['name', 'description']
    ordering = ['-created_at']
    
    def volatility_display(self, obj):
        color = 'red' if obj.volatility_level > 0.6 else 'orange' if obj.volatility_level > 0.3 else 'green'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1%}</span>',
            color,
            obj.volatility_level
        )
    volatility_display.short_description = 'Volatility'
    
    def trend_display(self, obj):
        color = 'green' if obj.trend_strength > 0.3 else 'red' if obj.trend_strength < -0.3 else 'orange'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.3f}</span>',
            color,
            obj.trend_strength
        )
    trend_display.short_description = 'Trend Strength'
    
    def confidence_display(self, obj):
        color = 'green' if obj.confidence > 0.8 else 'orange' if obj.confidence > 0.6 else 'red'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1%}</span>',
            color,
            obj.confidence
        )
    confidence_display.short_description = 'Confidence'


@admin.register(SignalPerformance)
class SignalPerformanceAdmin(admin.ModelAdmin):
    list_display = [
        'period_type', 'start_date', 'end_date', 'total_signals',
        'win_rate_display', 'profit_factor_display', 'avg_confidence_display'
    ]
    list_filter = ['period_type', 'start_date']
    ordering = ['-start_date']
    
    def win_rate_display(self, obj):
        color = 'green' if obj.win_rate >= 0.7 else 'orange' if obj.win_rate >= 0.5 else 'red'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1%}</span>',
            color,
            obj.win_rate
        )
    win_rate_display.short_description = 'Win Rate'
    
    def profit_factor_display(self, obj):
        color = 'green' if obj.profit_factor >= 1.5 else 'orange' if obj.profit_factor >= 1.0 else 'red'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.2f}</span>',
            color,
            obj.profit_factor
        )
    profit_factor_display.short_description = 'Profit Factor'
    
    def avg_confidence_display(self, obj):
        color = 'green' if obj.average_confidence >= 0.8 else 'orange' if obj.average_confidence >= 0.7 else 'red'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1%}</span>',
            color,
            obj.average_confidence
        )
    avg_confidence_display.short_description = 'Avg Confidence'


@admin.register(SignalAlert)
class SignalAlertAdmin(admin.ModelAdmin):
    list_display = [
        'alert_type', 'priority_display', 'title', 'signal_link',
        'is_read', 'created_at'
    ]
    list_filter = ['alert_type', 'priority', 'is_read', 'created_at']
    search_fields = ['title', 'message']
    ordering = ['-created_at']
    readonly_fields = ['created_at']
    
    def priority_display(self, obj):
        colors = {
            'CRITICAL': 'red',
            'HIGH': 'orange',
            'MEDIUM': 'yellow',
            'LOW': 'green'
        }
        color = colors.get(obj.priority, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.priority
        )
    priority_display.short_description = 'Priority'
    
    def signal_link(self, obj):
        if obj.signal:
            url = reverse('admin:signals_tradingsignal_change', args=[obj.signal.id])
            return format_html('<a href="{}">{}</a>', url, obj.signal)
        return '-'
    signal_link.short_description = 'Signal'
    
    actions = ['mark_as_read', 'mark_as_unread']
    
    def mark_as_read(self, request, queryset):
        updated = queryset.update(is_read=True)
        self.message_user(request, f"{updated} alerts marked as read.")
    mark_as_read.short_description = "Mark selected alerts as read"
    
    def mark_as_unread(self, request, queryset):
        updated = queryset.update(is_read=False)
        self.message_user(request, f"{updated} alerts marked as unread.")
    mark_as_unread.short_description = "Mark selected alerts as unread"


@admin.register(HourlyBestSignal)
class HourlyBestSignalAdmin(admin.ModelAdmin):
    list_display = ['signal_date', 'signal_hour', 'symbol', 'rank', 'quality_score', 'trading_signal', 'created_at']
    list_filter = ['signal_date', 'signal_hour']
    search_fields = ['symbol__symbol', 'symbol__name']
    ordering = ['-signal_date', '-signal_hour', 'rank']
    raw_id_fields = ['symbol', 'trading_signal']
    readonly_fields = ['created_at']
    date_hierarchy = 'signal_date'


# Custom admin site configuration
admin.site.site_header = "AI Trading Signal Engine"
admin.site.site_title = "CryptAI Admin"
admin.site.index_title = "Dashboard"

# Add custom admin views for statistics
class SignalStatisticsAdmin(admin.ModelAdmin):
    change_list_template = 'admin/signal_statistics.html'
    
    def changelist_view(self, request, extra_context=None):
        # Calculate statistics
        total_signals = TradingSignal.objects.count()
        active_signals = TradingSignal.objects.filter(is_valid=True).count()
        executed_signals = TradingSignal.objects.filter(is_executed=True).count()
        profitable_signals = TradingSignal.objects.filter(
            is_executed=True, is_profitable=True
        ).count()
        
        win_rate = profitable_signals / executed_signals if executed_signals > 0 else 0.0
        
        avg_confidence = TradingSignal.objects.filter(
            created_at__gte=timezone.now() - timezone.timedelta(days=7)
        ).aggregate(avg_confidence=Avg('confidence_score'))['avg_confidence'] or 0.0
        
        avg_quality = TradingSignal.objects.filter(
            created_at__gte=timezone.now() - timezone.timedelta(days=7)
        ).aggregate(avg_quality=Avg('quality_score'))['avg_quality'] or 0.0
        
        unread_alerts = SignalAlert.objects.filter(is_read=False).count()
        
        extra_context = extra_context or {}
        extra_context.update({
            'total_signals': total_signals,
            'active_signals': active_signals,
            'executed_signals': executed_signals,
            'profitable_signals': profitable_signals,
            'win_rate': win_rate,
            'avg_confidence': avg_confidence,
            'avg_quality': avg_quality,
            'unread_alerts': unread_alerts,
        })
        
        return super().changelist_view(request, extra_context)

# Note: TradingSignal is already registered above with TradingSignalAdmin
