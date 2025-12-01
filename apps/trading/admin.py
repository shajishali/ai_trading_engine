from django.contrib import admin
from .models import Portfolio, Symbol, Position, Trade, RiskSettings


@admin.register(Portfolio)
class PortfolioAdmin(admin.ModelAdmin):
    list_display = ['user', 'name', 'balance', 'currency', 'created_at']
    list_filter = ['currency', 'created_at']
    search_fields = ['user__username', 'name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Symbol)
class SymbolAdmin(admin.ModelAdmin):
    list_display = ['symbol', 'name', 'symbol_type', 'exchange', 'is_active']
    list_filter = ['symbol_type', 'exchange', 'is_active']
    search_fields = ['symbol', 'name']
    readonly_fields = ['created_at']


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ['portfolio', 'symbol', 'position_type', 'quantity', 'entry_price', 'current_price', 'is_open']
    list_filter = ['position_type', 'is_open', 'opened_at']
    search_fields = ['portfolio__user__username', 'symbol__symbol']
    readonly_fields = ['opened_at', 'closed_at', 'unrealized_pnl']


@admin.register(Trade)
class TradeAdmin(admin.ModelAdmin):
    list_display = ['portfolio', 'symbol', 'trade_type', 'quantity', 'price', 'total_value', 'executed_at']
    list_filter = ['trade_type', 'executed_at']
    search_fields = ['portfolio__user__username', 'symbol__symbol']
    readonly_fields = ['executed_at', 'total_value']


@admin.register(RiskSettings)
class RiskSettingsAdmin(admin.ModelAdmin):
    list_display = ['portfolio', 'max_position_size', 'max_risk_per_trade', 'stop_loss_percentage', 'take_profit_percentage']
    list_filter = ['max_position_size', 'max_risk_per_trade']
    search_fields = ['portfolio__user__username']
