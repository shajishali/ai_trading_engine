from django.contrib import admin
from .models import DataSource, MarketData, DataFeed, TechnicalIndicator, DataSyncLog


@admin.register(DataSource)
class DataSourceAdmin(admin.ModelAdmin):
    list_display = ['name', 'source_type', 'base_url', 'is_active', 'created_at']
    list_filter = ['source_type', 'is_active', 'created_at']
    search_fields = ['name', 'base_url']
    readonly_fields = ['created_at']


@admin.register(MarketData)
class MarketDataAdmin(admin.ModelAdmin):
    list_display = ['symbol', 'timestamp', 'open_price', 'high_price', 'low_price', 'close_price', 'volume']
    list_filter = ['symbol', 'timestamp']
    search_fields = ['symbol__symbol']
    readonly_fields = ['created_at']
    date_hierarchy = 'timestamp'


@admin.register(DataFeed)
class DataFeedAdmin(admin.ModelAdmin):
    list_display = ['name', 'symbol', 'data_source', 'feed_type', 'is_active', 'last_update']
    list_filter = ['feed_type', 'is_active', 'data_source']
    search_fields = ['name', 'symbol__symbol']
    readonly_fields = ['created_at', 'last_update']


@admin.register(TechnicalIndicator)
class TechnicalIndicatorAdmin(admin.ModelAdmin):
    list_display = ['symbol', 'indicator_type', 'period', 'value', 'timestamp']
    list_filter = ['indicator_type', 'period', 'timestamp']
    search_fields = ['symbol__symbol']
    readonly_fields = ['created_at']
    date_hierarchy = 'timestamp'


@admin.register(DataSyncLog)
class DataSyncLogAdmin(admin.ModelAdmin):
    list_display = ['sync_type', 'symbol', 'status', 'records_processed', 'records_added', 'records_updated', 'started_at']
    list_filter = ['sync_type', 'status', 'started_at']
    search_fields = ['sync_type', 'symbol__symbol']
    readonly_fields = ['started_at', 'completed_at']
