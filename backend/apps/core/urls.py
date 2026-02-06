from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    # Favicon route (served directly to avoid 404)
    path('favicon.ico', views.favicon_view, name='favicon'),
    path('static/images/favicon.svg', views.favicon_view, name='favicon_svg'),
    
    # Performance monitoring (Phase 5)
    path('api/performance/', views.performance_metrics, name='performance_metrics'),
    
    # Real-time features (Phase 6)
    path('api/realtime/connect/', views.RealTimeConnectionView.as_view(), name='realtime_connect'),
    path('api/realtime/streaming/', views.MarketDataStreamingView.as_view(), name='market_data_streaming'),
    path('api/realtime/notifications/', views.RealTimeNotificationsView.as_view(), name='realtime_notifications'),
    path('api/realtime/status/', views.WebSocketStatusView.as_view(), name='websocket_status'),
    
    # Real-time dashboard (Phase 6)
    path('realtime-dashboard/', views.realtime_dashboard, name='realtime_dashboard'),
    
    # WebSocket test page (Phase 6)
    path('websocket-test/', views.websocket_test, name='websocket_test'),
    path('api/run-websocket-test/', views.run_websocket_test, name='run_websocket_test'),
    
    # Monitoring & Alerting (Phase 7B.3)
    path('health/', views.health_check_endpoint, name='health_check'),
    path('monitoring-dashboard/', views.monitoring_dashboard, name='monitoring_dashboard'),
    path('api/monitoring/dashboard/', views.monitoring_dashboard, name='monitoring_dashboard'),
    path('api/monitoring/start/', views.start_monitoring, name='start_monitoring'),
    path('api/monitoring/stop/', views.stop_monitoring, name='stop_monitoring'),
    path('api/monitoring/performance/', views.performance_metrics, name='performance_metrics'),
    path('api/monitoring/alerts/', views.alert_history, name='alert_history'),
    path('api/monitoring/services/', views.service_status, name='service_status'),
    path('api/monitoring/test-alert/', views.trigger_test_alert, name='trigger_test_alert'),
    path('api/monitoring/config/', views.monitoring_config, name='monitoring_config'),
]
