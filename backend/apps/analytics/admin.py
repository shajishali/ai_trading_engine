from django.contrib import admin
from .models import (
    SentimentData, AnalyticsPortfolio, AnalyticsPosition, AnalyticsTrade,
    PerformanceMetrics, BacktestResult, MarketData, Alert,
    MarketSentimentIndicator, FearGreedIndex, VIXData, PutCallRatio
)

@admin.register(AnalyticsPortfolio)
class AnalyticsPortfolioAdmin(admin.ModelAdmin):
    list_display = ['user', 'name', 'initial_balance', 'current_balance', 'total_return', 'is_active']
    list_filter = ['is_active', 'created_at']
    search_fields = ['user__username', 'name']
    readonly_fields = ['total_return', 'total_return_amount']

@admin.register(AnalyticsPosition)
class AnalyticsPositionAdmin(admin.ModelAdmin):
    list_display = ['portfolio', 'symbol', 'quantity', 'entry_price', 'current_price', 'unrealized_pnl', 'is_open']
    list_filter = ['is_open', 'entry_date']
    search_fields = ['symbol', 'portfolio__name']
    readonly_fields = ['market_value', 'unrealized_pnl', 'unrealized_pnl_percent']

@admin.register(AnalyticsTrade)
class AnalyticsTradeAdmin(admin.ModelAdmin):
    list_display = ['portfolio', 'symbol', 'trade_type', 'quantity', 'price', 'total_value', 'timestamp']
    list_filter = ['trade_type', 'timestamp']
    search_fields = ['symbol', 'portfolio__name']
    readonly_fields = ['total_value', 'net_value']

@admin.register(PerformanceMetrics)
class PerformanceMetricsAdmin(admin.ModelAdmin):
    list_display = ['portfolio', 'date', 'total_value', 'daily_return', 'sharpe_ratio', 'max_drawdown']
    list_filter = ['date']
    search_fields = ['portfolio__name']

@admin.register(BacktestResult)
class BacktestResultAdmin(admin.ModelAdmin):
    list_display = ['user', 'strategy_name', 'start_date', 'end_date', 'total_return', 'sharpe_ratio', 'win_rate']
    list_filter = ['start_date', 'end_date']
    search_fields = ['strategy_name', 'user__username']
    readonly_fields = ['total_trades_count']

@admin.register(MarketData)
class MarketDataAdmin(admin.ModelAdmin):
    list_display = ['symbol', 'date', 'close_price', 'volume', 'rsi', 'sma_20']
    list_filter = ['symbol', 'date']
    search_fields = ['symbol']
    readonly_fields = ['created_at']

@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ['user', 'alert_type', 'title', 'status', 'created_at', 'is_read']
    list_filter = ['alert_type', 'status', 'created_at', 'is_read']
    search_fields = ['title', 'message', 'user__username']
    readonly_fields = ['created_at']

@admin.register(MarketSentimentIndicator)
class MarketSentimentIndicatorAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'timeframe', 'fear_greed_index', 'vix_value', 'put_call_ratio', 'market_mood', 'volatility_regime']
    list_filter = ['timeframe', 'market_mood', 'volatility_regime', 'trend_strength']
    search_fields = ['fear_greed_label', 'market_mood']
    date_hierarchy = 'timestamp'
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('timestamp', 'timeframe', 'market_mood', 'confidence_score')
        }),
        ('Fear & Greed Index', {
            'fields': ('fear_greed_index', 'fear_greed_label')
        }),
        ('VIX Volatility', {
            'fields': ('vix_value', 'vix_change', 'vix_change_percent')
        }),
        ('Put/Call Ratio', {
            'fields': ('put_call_ratio', 'put_call_ratio_change')
        }),
        ('Market Regime', {
            'fields': ('volatility_regime', 'trend_strength')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(FearGreedIndex)
class FearGreedIndexAdmin(admin.ModelAdmin):
    list_display = ['date', 'value', 'label', 'classification']
    list_filter = ['classification', 'label']
    search_fields = ['label', 'classification']
    date_hierarchy = 'date'
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('date', 'value', 'label', 'classification')
        }),
        ('Component Scores', {
            'fields': ('volatility_score', 'market_momentum_score', 'social_media_score', 
                      'survey_score', 'junk_bond_demand_score', 'safe_haven_demand_score'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )


@admin.register(VIXData)
class VIXDataAdmin(admin.ModelAdmin):
    list_display = ['date', 'close_value', 'change', 'change_percent', 'volume']
    list_filter = ['date']
    search_fields = ['date']
    date_hierarchy = 'date'
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Price Data', {
            'fields': ('date', 'open_value', 'high_value', 'low_value', 'close_value')
        }),
        ('Change Metrics', {
            'fields': ('change', 'change_percent', 'volume')
        }),
        ('Moving Averages', {
            'fields': ('sma_20', 'sma_50'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )


@admin.register(PutCallRatio)
class PutCallRatioAdmin(admin.ModelAdmin):
    list_display = ['date', 'total_put_call_ratio', 'sentiment_indicator', 'change', 'change_percent']
    list_filter = ['date']
    search_fields = ['date']
    date_hierarchy = 'date'
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('date', 'total_put_call_ratio')
        }),
        ('Individual Ratios', {
            'fields': ('equity_put_call_ratio', 'index_put_call_ratio', 'etf_put_call_ratio'),
            'classes': ('collapse',)
        }),
        ('Volume Data', {
            'fields': ('total_put_volume', 'total_call_volume'),
            'classes': ('collapse',)
        }),
        ('Change Metrics', {
            'fields': ('change', 'change_percent')
        }),
        ('Moving Averages', {
            'fields': ('sma_10', 'sma_20'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
