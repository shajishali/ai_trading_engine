from django.urls import path
from . import views

app_name = 'data'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('realtime/', views.realtime_dashboard, name='realtime_dashboard'),
    
    # API endpoints
    path('api/market-data/', views.api_market_data, name='api_market_data'),
    path('api/symbols/', views.api_symbols, name='api_symbols'),
    path('api/live-prices/', views.api_live_prices, name='api_live_prices'),
]
