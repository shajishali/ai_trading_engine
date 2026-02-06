from django.shortcuts import render
from django.http import HttpResponse, JsonResponse, FileResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from django.core.cache import cache
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.conf import settings
from pathlib import Path
import logging
import json
import os

from .services import market_broadcaster, signals_broadcaster, notification_broadcaster

# Monitoring and Alerting Views for Phase 7B.3
from .services import (
    ApplicationMonitoringService, 
    ErrorAlertingService, 
    UptimeMonitoringService
)

# Global monitoring service instances
app_monitoring_service = ApplicationMonitoringService()
error_alerting_service = ErrorAlertingService()
uptime_monitoring_service = UptimeMonitoringService()


logger = logging.getLogger(__name__)

# Create your views here.

# Custom error handlers for Phase 5
def handler404(request, exception):
    """Custom 404 error handler"""
    logger.warning(f"404 error for URL: {request.path}")
    return render(request, 'core/404.html', status=404)

def handler500(request):
    """Custom 500 error handler"""
    logger.error(f"500 error for URL: {request.path}")
    try:
        return render(request, 'core/500.html', status=500)
    except Exception as e:
        logger.error(f"Error in handler500: {e}", exc_info=True)
        # Fallback to simple HttpResponse if template rendering fails
        from django.http import HttpResponse
        return HttpResponse("Server Error - Something went wrong", status=500)

def handler403(request, exception):
    """Custom 403 error handler"""
    logger.warning(f"403 error for URL: {request.path}")
    return render(request, 'core/403.html', status=403)


@method_decorator(login_required, name='dispatch')
class PerformanceMetricsView(View):
    """View for performance metrics"""
    
    def get(self, request):
        """Get performance metrics"""
        try:
            # Get cached performance metrics
            cache_key = "performance_metrics"
            metrics = cache.get(cache_key)
            
            if not metrics:
                # Generate default metrics if cache is empty
                metrics = {
                    'total_requests': 0,
                    'avg_response_time': 0.0,
                    'error_rate': 0.0,
                    'active_connections': 0,
                    'cache_hit_rate': 0.0
                }
            
            return JsonResponse({
                'success': True,
                'metrics': metrics
            })
            
        except Exception as e:
            logger.error(f"Error getting performance metrics: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


# Real-Time API Endpoints for Phase 6
@method_decorator(login_required, name='dispatch')
class RealTimeConnectionView(View):
    """View for real-time connection management"""
    
    def post(self, request):
        """Establish real-time connection"""
        try:
            connection_type = request.POST.get('type', 'market_data')
            
            # Return connection details
            return JsonResponse({
                'success': True,
                'connection_type': connection_type,
                'websocket_url': f'/ws/{connection_type}/',
                'message': f'Real-time {connection_type} connection established'
            })
            
        except Exception as e:
            logger.error(f"Error establishing real-time connection: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


@method_decorator(login_required, name='dispatch')
class MarketDataStreamingView(View):
    """View for market data streaming control"""
    
    def post(self, request):
        """Start/stop market data streaming"""
        try:
            action = request.POST.get('action')  # 'start' or 'stop'
            symbol = request.POST.get('symbol')
            
            if not symbol:
                return JsonResponse({
                    'success': False,
                    'error': 'Symbol is required'
                }, status=400)
            
            if action == 'start':
                message = f'Started streaming market data for {symbol}'
            elif action == 'stop':
                message = f'Stopped streaming market data for {symbol}'
            else:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid action. Use "start" or "stop"'
                }, status=400)
            
            return JsonResponse({
                'success': True,
                'action': action,
                'symbol': symbol,
                'message': message
            })
            
        except Exception as e:
            logger.error(f"Error controlling market data streaming: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


@method_decorator(login_required, name='dispatch')
class RealTimeNotificationsView(View):
    """View for real-time notification management"""
    
    def post(self, request):
        """Send real-time notification"""
        try:
            notification_type = request.POST.get('type')
            title = request.POST.get('title')
            message = request.POST.get('message')
            priority = request.POST.get('priority', 'medium')
            
            if not all([notification_type, title, message]):
                return JsonResponse({
                    'success': False,
                    'error': 'Type, title, and message are required'
                }, status=400)
            
            notification_broadcaster.broadcast_notification(
                user_id=request.user.id,
                notification_id=f"manual_{int(timezone.now().timestamp())}",
                title=title,
                message=message,
                notification_type=notification_type,
                priority=priority
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Notification sent successfully'
            })
            
        except Exception as e:
            logger.error(f"Error sending real-time notification: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


@method_decorator(login_required, name='dispatch')
class WebSocketStatusView(View):
    """View for WebSocket connection status"""
    
    def get(self, request):
        """Get WebSocket connection status"""
        try:
            # Check if user has active WebSocket connections
            user_id = request.user.id
            
            # Get connection status from cache
            market_data_status = cache.get(f"ws_market_data_{user_id}", False)
            trading_signals_status = cache.get(f"ws_trading_signals_{user_id}", False)
            notifications_status = cache.get(f"ws_notifications_{user_id}", False)
            
            return JsonResponse({
                'success': True,
                'connections': {
                    'market_data': market_data_status,
                    'trading_signals': trading_signals_status,
                    'notifications': notifications_status
                },
                'websocket_urls': {
                    'market_data': '/ws/market-data/',
                    'trading_signals': '/ws/trading-signals/',
                    'notifications': '/ws/notifications/'
                }
            })
            
        except Exception as e:
            logger.error(f"Error getting WebSocket status: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


@login_required
def realtime_dashboard(request):
    """Real-time dashboard view for Phase 6"""
    return render(request, 'core/realtime_dashboard.html')


@login_required
def websocket_test(request):
    """WebSocket test page view for Phase 6"""
    return render(request, 'core/websocket_test.html')


@method_decorator(login_required, name='dispatch')
class WebSocketTestView(View):
    """View for running WebSocket tests"""
    
    def post(self, request):
        """Run WebSocket test"""
        try:
            import json
            data = json.loads(request.body)
            test_type = data.get('type', 'all')
            count = data.get('count', 5)
            delay = data.get('delay', 2.0)
            
            # Import the test command
            from django.core.management import call_command
            from io import StringIO
            
            # Capture command output
            out = StringIO()
            
            # Run the test command
            call_command(
                'test_websockets',
                type=test_type,
                count=count,
                delay=delay,
                stdout=out
            )
            
            output = out.getvalue()
            out.close()
            
            return JsonResponse({
                'success': True,
                'message': f'WebSocket test completed: {test_type}',
                'output': output
            })
            
        except Exception as e:
            logger.error(f"Error running WebSocket test: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


def run_websocket_test(request):
    """Function-based view for running WebSocket tests"""
    if request.method == 'POST':
        try:
            import json
            data = json.loads(request.body)
            test_type = data.get('type', 'all')
            count = data.get('count', 5)
            delay = data.get('delay', 2.0)
            
            # Import the test command
            from django.core.management import call_command
            from io import StringIO
            
            # Capture command output
            out = StringIO()
            
            # Run the test command
            call_command(
                'test_websockets',
                type=test_type,
                count=count,
                delay=delay,
                stdout=out
            )
            
            output = out.getvalue()
            out.close()
            
            return JsonResponse({
                'success': True,
                'message': f'WebSocket test completed: {test_type}',
                'output': output
            })
            
        except Exception as e:
            logger.error(f"Error running WebSocket test: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    return JsonResponse({
        'success': False,
        'error': 'Only POST method allowed'
    }, status=405)


def health_check_endpoint(request):
    """
    Health check endpoint for load balancers and monitoring systems
    Returns comprehensive health status of all services
    """
    try:
        from django.core.cache import cache
        from django.db import connection
        import psutil
        
        # Basic health checks
        health_status = {
            'status': 'healthy',
            'timestamp': timezone.now().isoformat(),
            'services': {}
        }
        
        # Check Django
        try:
            cache.set('health_check', 'ok', 10)
            django_ok = cache.get('health_check') == 'ok'
            cache.delete('health_check')
            health_status['services']['django'] = 'healthy' if django_ok else 'unhealthy'
        except Exception as e:
            health_status['services']['django'] = 'unhealthy'
            health_status['status'] = 'unhealthy'
            
        # Check Database
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            health_status['services']['database'] = 'healthy'
        except Exception as e:
            health_status['services']['database'] = 'unhealthy'
            health_status['status'] = 'unhealthy'
            
        # Check Redis
        try:
            cache.set('redis_health', 'ok', 10)
            redis_ok = cache.get('redis_health') == 'ok'
            cache.delete('redis_health')
            health_status['services']['redis'] = 'healthy' if redis_ok else 'unhealthy'
        except Exception as e:
            health_status['services']['redis'] = 'unhealthy'
            health_status['status'] = 'unhealthy'
            
        # Check System Resources
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory_percent = psutil.virtual_memory().percent
            disk_percent = psutil.disk_usage('/').percent
            
            health_status['services']['system'] = {
                'cpu': 'healthy' if cpu_percent < 90 else 'warning',
                'memory': 'healthy' if memory_percent < 95 else 'warning',
                'disk': 'healthy' if disk_percent < 95 else 'warning',
                'metrics': {
                    'cpu_percent': cpu_percent,
                    'memory_percent': memory_percent,
                    'disk_percent': disk_percent
                }
            }
            
            # Update overall status if any system component is unhealthy
            if any(status == 'unhealthy' for status in health_status['services'].values() if isinstance(status, str)):
                health_status['status'] = 'unhealthy'
            elif any(status == 'warning' for status in health_status['services'].values() if isinstance(status, dict)):
                health_status['status'] = 'degraded'
                
        except Exception as e:
            health_status['services']['system'] = 'unhealthy'
            health_status['status'] = 'unhealthy'
            
        # Add monitoring status
        health_status['monitoring'] = {
            'application_monitoring': app_monitoring_service.monitoring_active,
            'error_alerting': True,  # Always active
            'uptime_monitoring': uptime_monitoring_service.monitoring_active
        }
        
        # Return appropriate HTTP status
        if health_status['status'] == 'healthy':
            return JsonResponse(health_status, status=200)
        elif health_status['status'] == 'degraded':
            return JsonResponse(health_status, status=200)  # Still 200 but with degraded status
        else:
            return JsonResponse(health_status, status=503)  # Service Unavailable
            
    except Exception as e:
        error_response = {
            'status': 'error',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }
        return JsonResponse(error_response, status=500)


def monitoring_dashboard(request):
    """
    Monitoring dashboard view showing comprehensive system status
    """
    try:
        # Get monitoring status from all services
        monitoring_data = {
            'application_monitoring': app_monitoring_service.get_monitoring_status(),
            'error_alerting': error_alerting_service.get_error_status(),
            'uptime_monitoring': uptime_monitoring_service.get_uptime_status(),
            'timestamp': timezone.now().isoformat()
        }
        
        return JsonResponse(monitoring_data)
        
    except Exception as e:
        error_response = {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }
        return JsonResponse(error_response, status=500)


def favicon_view(request):
    """Serve favicon directly to avoid 404 errors"""
    favicon_path = None
    
    # Try multiple possible locations
    possible_paths = [
        Path(settings.BASE_DIR.parent) / 'frontend' / 'static' / 'images' / 'favicon.svg',
        Path(settings.BASE_DIR) / 'static' / 'images' / 'favicon.svg',
        Path(settings.BASE_DIR.parent) / 'frontend' / 'staticfiles' / 'images' / 'favicon.svg',
    ]
    
    for path in possible_paths:
        if path.exists():
            favicon_path = path
            break
    
    if favicon_path and favicon_path.exists():
        return FileResponse(open(favicon_path, 'rb'), content_type='image/svg+xml')
    else:
        # Return inline SVG favicon as fallback
        svg_content = '''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#022b57"/>
      <stop offset="1" stop-color="#0d6efd"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="56" height="56" rx="14" fill="url(#g)"/>
  <path d="M20 40c6-10 12-16 24-20" fill="none" stroke="#ffffff" stroke-width="5" stroke-linecap="round"/>
  <path d="M22 24h6v18h-6z" fill="#ffffff" opacity="0.9"/>
  <path d="M30 20h6v22h-6z" fill="#ffffff" opacity="0.9"/>
  <path d="M38 28h6v14h-6z" fill="#ffffff" opacity="0.9"/>
</svg>'''
        return HttpResponse(svg_content, content_type='image/svg+xml')


def start_monitoring(request):
    """
    Start all monitoring services
    """
    try:
        if request.method == 'POST':
            # Start application monitoring
            app_monitoring_service.start_monitoring()
            
            # Start uptime monitoring
            uptime_monitoring_service.start_monitoring()
            
            response_data = {
                'message': 'All monitoring services started successfully',
                'status': 'started',
                'timestamp': timezone.now().isoformat()
            }
            
            return JsonResponse(response_data, status=200)
        else:
            return JsonResponse({'error': 'Method not allowed'}, status=405)
            
    except Exception as e:
        error_response = {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }
        return JsonResponse(error_response, status=500)


def favicon_view(request):
    """Serve favicon directly to avoid 404 errors"""
    favicon_path = None
    
    # Try multiple possible locations
    possible_paths = [
        Path(settings.BASE_DIR.parent) / 'frontend' / 'static' / 'images' / 'favicon.svg',
        Path(settings.BASE_DIR) / 'static' / 'images' / 'favicon.svg',
        Path(settings.BASE_DIR.parent) / 'frontend' / 'staticfiles' / 'images' / 'favicon.svg',
    ]
    
    for path in possible_paths:
        if path.exists():
            favicon_path = path
            break
    
    if favicon_path and favicon_path.exists():
        return FileResponse(open(favicon_path, 'rb'), content_type='image/svg+xml')
    else:
        # Return inline SVG favicon as fallback
        svg_content = '''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#022b57"/>
      <stop offset="1" stop-color="#0d6efd"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="56" height="56" rx="14" fill="url(#g)"/>
  <path d="M20 40c6-10 12-16 24-20" fill="none" stroke="#ffffff" stroke-width="5" stroke-linecap="round"/>
  <path d="M22 24h6v18h-6z" fill="#ffffff" opacity="0.9"/>
  <path d="M30 20h6v22h-6z" fill="#ffffff" opacity="0.9"/>
  <path d="M38 28h6v14h-6z" fill="#ffffff" opacity="0.9"/>
</svg>'''
        return HttpResponse(svg_content, content_type='image/svg+xml')


def stop_monitoring(request):
    """
    Stop all monitoring services
    """
    try:
        if request.method == 'POST':
            # Stop application monitoring
            app_monitoring_service.stop_monitoring()
            
            # Stop uptime monitoring
            uptime_monitoring_service.stop_monitoring()
            
            response_data = {
                'message': 'All monitoring services stopped successfully',
                'status': 'stopped',
                'timestamp': timezone.now().isoformat()
            }
            
            return JsonResponse(response_data, status=200)
        else:
            return JsonResponse({'error': 'Method not allowed'}, status=405)
            
    except Exception as e:
        error_response = {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }
        return JsonResponse(error_response, status=500)


def favicon_view(request):
    """Serve favicon directly to avoid 404 errors"""
    favicon_path = None
    
    # Try multiple possible locations
    possible_paths = [
        Path(settings.BASE_DIR.parent) / 'frontend' / 'static' / 'images' / 'favicon.svg',
        Path(settings.BASE_DIR) / 'static' / 'images' / 'favicon.svg',
        Path(settings.BASE_DIR.parent) / 'frontend' / 'staticfiles' / 'images' / 'favicon.svg',
    ]
    
    for path in possible_paths:
        if path.exists():
            favicon_path = path
            break
    
    if favicon_path and favicon_path.exists():
        return FileResponse(open(favicon_path, 'rb'), content_type='image/svg+xml')
    else:
        # Return inline SVG favicon as fallback
        svg_content = '''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#022b57"/>
      <stop offset="1" stop-color="#0d6efd"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="56" height="56" rx="14" fill="url(#g)"/>
  <path d="M20 40c6-10 12-16 24-20" fill="none" stroke="#ffffff" stroke-width="5" stroke-linecap="round"/>
  <path d="M22 24h6v18h-6z" fill="#ffffff" opacity="0.9"/>
  <path d="M30 20h6v22h-6z" fill="#ffffff" opacity="0.9"/>
  <path d="M38 28h6v14h-6z" fill="#ffffff" opacity="0.9"/>
</svg>'''
        return HttpResponse(svg_content, content_type='image/svg+xml')


def performance_metrics(request):
    """
    Get detailed performance metrics
    """
    try:
        # Get performance metrics from application monitoring
        performance_data = app_monitoring_service.performance_metrics
        
        # Add current system metrics
        import psutil
        current_metrics = {
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_percent': psutil.disk_usage('/').percent,
            'timestamp': timezone.now().isoformat()
        }
        
        response_data = {
            'performance_metrics': performance_data,
            'current_metrics': current_metrics,
            'summary': app_monitoring_service._get_performance_summary()
        }
        
        return JsonResponse(response_data)
        
    except Exception as e:
        error_response = {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }
        return JsonResponse(error_response, status=500)


def favicon_view(request):
    """Serve favicon directly to avoid 404 errors"""
    favicon_path = None
    
    # Try multiple possible locations
    possible_paths = [
        Path(settings.BASE_DIR.parent) / 'frontend' / 'static' / 'images' / 'favicon.svg',
        Path(settings.BASE_DIR) / 'static' / 'images' / 'favicon.svg',
        Path(settings.BASE_DIR.parent) / 'frontend' / 'staticfiles' / 'images' / 'favicon.svg',
    ]
    
    for path in possible_paths:
        if path.exists():
            favicon_path = path
            break
    
    if favicon_path and favicon_path.exists():
        return FileResponse(open(favicon_path, 'rb'), content_type='image/svg+xml')
    else:
        # Return inline SVG favicon as fallback
        svg_content = '''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#022b57"/>
      <stop offset="1" stop-color="#0d6efd"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="56" height="56" rx="14" fill="url(#g)"/>
  <path d="M20 40c6-10 12-16 24-20" fill="none" stroke="#ffffff" stroke-width="5" stroke-linecap="round"/>
  <path d="M22 24h6v18h-6z" fill="#ffffff" opacity="0.9"/>
  <path d="M30 20h6v22h-6z" fill="#ffffff" opacity="0.9"/>
  <path d="M38 28h6v14h-6z" fill="#ffffff" opacity="0.9"/>
</svg>'''
        return HttpResponse(svg_content, content_type='image/svg+xml')


def alert_history(request):
    """
    Get alert history from all monitoring services
    """
    try:
        alert_data = {
            'application_alerts': app_monitoring_service.alert_history[-50:] if app_monitoring_service.alert_history else [],
            'error_alerts': error_alerting_service.alert_history[-50:] if error_alerting_service.alert_history else [],
            'timestamp': timezone.now().isoformat()
        }
        
        return JsonResponse(alert_data)
        
    except Exception as e:
        error_response = {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }
        return JsonResponse(error_response, status=500)


def favicon_view(request):
    """Serve favicon directly to avoid 404 errors"""
    favicon_path = None
    
    # Try multiple possible locations
    possible_paths = [
        Path(settings.BASE_DIR.parent) / 'frontend' / 'static' / 'images' / 'favicon.svg',
        Path(settings.BASE_DIR) / 'static' / 'images' / 'favicon.svg',
        Path(settings.BASE_DIR.parent) / 'frontend' / 'staticfiles' / 'images' / 'favicon.svg',
    ]
    
    for path in possible_paths:
        if path.exists():
            favicon_path = path
            break
    
    if favicon_path and favicon_path.exists():
        return FileResponse(open(favicon_path, 'rb'), content_type='image/svg+xml')
    else:
        # Return inline SVG favicon as fallback
        svg_content = '''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#022b57"/>
      <stop offset="1" stop-color="#0d6efd"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="56" height="56" rx="14" fill="url(#g)"/>
  <path d="M20 40c6-10 12-16 24-20" fill="none" stroke="#ffffff" stroke-width="5" stroke-linecap="round"/>
  <path d="M22 24h6v18h-6z" fill="#ffffff" opacity="0.9"/>
  <path d="M30 20h6v22h-6z" fill="#ffffff" opacity="0.9"/>
  <path d="M38 28h6v14h-6z" fill="#ffffff" opacity="0.9"/>
</svg>'''
        return HttpResponse(svg_content, content_type='image/svg+xml')


def service_status(request):
    """
    Get detailed status of all services
    """
    try:
        # Get service status from application monitoring
        service_status_data = app_monitoring_service.service_status
        
        # Add uptime information
        uptime_data = uptime_monitoring_service.get_uptime_status()
        
        response_data = {
            'service_status': service_status_data,
            'uptime_data': uptime_data,
            'timestamp': timezone.now().isoformat()
        }
        
        return JsonResponse(response_data)
        
    except Exception as e:
        error_response = {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }
        return JsonResponse(error_response, status=500)


def favicon_view(request):
    """Serve favicon directly to avoid 404 errors"""
    favicon_path = None
    
    # Try multiple possible locations
    possible_paths = [
        Path(settings.BASE_DIR.parent) / 'frontend' / 'static' / 'images' / 'favicon.svg',
        Path(settings.BASE_DIR) / 'static' / 'images' / 'favicon.svg',
        Path(settings.BASE_DIR.parent) / 'frontend' / 'staticfiles' / 'images' / 'favicon.svg',
    ]
    
    for path in possible_paths:
        if path.exists():
            favicon_path = path
            break
    
    if favicon_path and favicon_path.exists():
        return FileResponse(open(favicon_path, 'rb'), content_type='image/svg+xml')
    else:
        # Return inline SVG favicon as fallback
        svg_content = '''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#022b57"/>
      <stop offset="1" stop-color="#0d6efd"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="56" height="56" rx="14" fill="url(#g)"/>
  <path d="M20 40c6-10 12-16 24-20" fill="none" stroke="#ffffff" stroke-width="5" stroke-linecap="round"/>
  <path d="M22 24h6v18h-6z" fill="#ffffff" opacity="0.9"/>
  <path d="M30 20h6v22h-6z" fill="#ffffff" opacity="0.9"/>
  <path d="M38 28h6v14h-6z" fill="#ffffff" opacity="0.9"/>
</svg>'''
        return HttpResponse(svg_content, content_type='image/svg+xml')


def trigger_test_alert(request):
    """
    Trigger a test alert to verify alerting system
    """
    try:
        if request.method == 'POST':
            alert_type = request.POST.get('alert_type', 'TEST_ALERT')
            
            # Trigger test alert through application monitoring
            app_monitoring_service._send_performance_alert(alert_type, {
                'test': True,
                'message': 'This is a test alert to verify the alerting system',
                'timestamp': timezone.now().isoformat()
            })
            
            response_data = {
                'message': f'Test alert "{alert_type}" triggered successfully',
                'timestamp': timezone.now().isoformat()
            }
            
            return JsonResponse(response_data, status=200)
        else:
            return JsonResponse({'error': 'Method not allowed'}, status=405)
            
    except Exception as e:
        error_response = {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }
        return JsonResponse(error_response, status=500)


def favicon_view(request):
    """Serve favicon directly to avoid 404 errors"""
    favicon_path = None
    
    # Try multiple possible locations
    possible_paths = [
        Path(settings.BASE_DIR.parent) / 'frontend' / 'static' / 'images' / 'favicon.svg',
        Path(settings.BASE_DIR) / 'static' / 'images' / 'favicon.svg',
        Path(settings.BASE_DIR.parent) / 'frontend' / 'staticfiles' / 'images' / 'favicon.svg',
    ]
    
    for path in possible_paths:
        if path.exists():
            favicon_path = path
            break
    
    if favicon_path and favicon_path.exists():
        return FileResponse(open(favicon_path, 'rb'), content_type='image/svg+xml')
    else:
        # Return inline SVG favicon as fallback
        svg_content = '''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#022b57"/>
      <stop offset="1" stop-color="#0d6efd"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="56" height="56" rx="14" fill="url(#g)"/>
  <path d="M20 40c6-10 12-16 24-20" fill="none" stroke="#ffffff" stroke-width="5" stroke-linecap="round"/>
  <path d="M22 24h6v18h-6z" fill="#ffffff" opacity="0.9"/>
  <path d="M30 20h6v22h-6z" fill="#ffffff" opacity="0.9"/>
  <path d="M38 28h6v14h-6z" fill="#ffffff" opacity="0.9"/>
</svg>'''
        return HttpResponse(svg_content, content_type='image/svg+xml')


def monitoring_config(request):
    """
    Get or update monitoring configuration
    """
    try:
        if request.method == 'GET':
            # Get current configuration
            config_data = {
                'application_monitoring': {
                    'monitoring_active': app_monitoring_service.monitoring_active,
                    'metrics_interval': app_monitoring_service.metrics_interval,
                    'alert_threshold': app_monitoring_service.alert_threshold
                },
                'uptime_monitoring': {
                    'monitoring_active': uptime_monitoring_service.monitoring_active,
                    'check_interval': uptime_monitoring_service.check_interval
                },
                'error_alerting': {
                    'error_thresholds': error_alerting_service.error_thresholds
                }
            }
            
            return JsonResponse(config_data)
            
        elif request.method == 'POST':
            # Update configuration
            data = json.loads(request.body)
            
            # Update application monitoring
            if 'application_monitoring' in data:
                app_config = data['application_monitoring']
                if 'metrics_interval' in app_config:
                    app_monitoring_service.metrics_interval = app_config['metrics_interval']
                if 'alert_threshold' in app_config:
                    app_monitoring_service.alert_threshold = app_config['alert_threshold']
                    
            # Update uptime monitoring
            if 'uptime_monitoring' in data:
                uptime_config = data['uptime_monitoring']
                if 'check_interval' in uptime_config:
                    uptime_monitoring_service.check_interval = uptime_config['check_interval']
                    
            # Update error alerting
            if 'error_alerting' in data:
                error_config = data['error_alerting']
                if 'error_thresholds' in error_config:
                    error_alerting_service.error_thresholds.update(error_config['error_thresholds'])
                    
            response_data = {
                'message': 'Monitoring configuration updated successfully',
                'timestamp': timezone.now().isoformat()
            }
            
            return JsonResponse(response_data, status=200)
            
        else:
            return JsonResponse({'error': 'Method not allowed'}, status=405)
            
    except Exception as e:
        error_response = {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }
        return JsonResponse(error_response, status=500)


def favicon_view(request):
    """Serve favicon directly to avoid 404 errors"""
    favicon_path = None
    
    # Try multiple possible locations
    possible_paths = [
        Path(settings.BASE_DIR.parent) / 'frontend' / 'static' / 'images' / 'favicon.svg',
        Path(settings.BASE_DIR) / 'static' / 'images' / 'favicon.svg',
        Path(settings.BASE_DIR.parent) / 'frontend' / 'staticfiles' / 'images' / 'favicon.svg',
    ]
    
    for path in possible_paths:
        if path.exists():
            favicon_path = path
            break
    
    if favicon_path and favicon_path.exists():
        return FileResponse(open(favicon_path, 'rb'), content_type='image/svg+xml')
    else:
        # Return inline SVG favicon as fallback
        svg_content = '''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#022b57"/>
      <stop offset="1" stop-color="#0d6efd"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="56" height="56" rx="14" fill="url(#g)"/>
  <path d="M20 40c6-10 12-16 24-20" fill="none" stroke="#ffffff" stroke-width="5" stroke-linecap="round"/>
  <path d="M22 24h6v18h-6z" fill="#ffffff" opacity="0.9"/>
  <path d="M30 20h6v22h-6z" fill="#ffffff" opacity="0.9"/>
  <path d="M38 28h6v14h-6z" fill="#ffffff" opacity="0.9"/>
</svg>'''
        return HttpResponse(svg_content, content_type='image/svg+xml')
