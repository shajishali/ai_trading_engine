from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # Market data WebSocket
    re_path(r'ws/market-data/$', consumers.MarketDataConsumer.as_asgi()),
    
    # Trading signals WebSocket
    re_path(r'ws/trading-signals/$', consumers.TradingSignalsConsumer.as_asgi()),
    
    # Notifications WebSocket
    re_path(r'ws/notifications/$', consumers.NotificationsConsumer.as_asgi()),
]











