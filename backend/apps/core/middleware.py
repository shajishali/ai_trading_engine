"""
Core Middleware for AI Trading Engine

This module provides essential middleware for security, performance monitoring,
and API rate limiting in production environments.
"""

import time
import json
import hashlib
import logging
from collections import defaultdict, deque
from django.http import HttpResponse, JsonResponse
from django.conf import settings
from django.core.cache import cache
from django.utils.deprecation import MiddlewareMixin
from django.middleware.csrf import get_token
from django.utils import timezone
from django.contrib.auth.models import AnonymousUser
import ipaddress

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Middleware to add security headers to all responses
    """
    
    def process_response(self, request, response):
        # Safety check: ensure response is not None
        if response is None:
            logger.error(f"None response detected for path: {request.path}")
            response = HttpResponse("Internal Server Error", status=500)
        
        # Security Headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Content Security Policy
        csp_policy = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
            "img-src 'self' data: https:; "
            "font-src 'self'data:https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
            "connect-src 'self' wss:; "
            "frame-ancestors 'none';"
        )
        response['Content-Security-Policy'] = csp_policy
        
        # HSTS (HTTP Strict Transport Security)
        if hasattr(settings, 'SECURE_HSTS_SECONDS'):
            response['Strict-Transport-Security'] = f'max-age={settings.SECURE_HSTS_SECONDS}; includeSubDomains'
        
        # Remove server information
        if 'Server' in response:
            del response['Server']
        
        return response


class APIRateLimitMiddleware(MiddlewareMixin):
    """
    Middleware for API rate limiting with configurable limits
    """
    
    def __init__(self, get_response=None):
        super().__init__(get_response)
        self.rate_limits = getattr(settings, 'RATE_LIMITS', {
            'default': {'requests': 100, 'window': 3600},  # 100 requests per hour
            'api': {'requests': 500, 'window': 3600},      # 500 API requests per hour
            'login': {'requests': 5, 'window': 300},       # 5 login attempts per 5 minutes
            'signup': {'requests': 3, 'window': 3600},     # 3 signup attempts per hour
            'trading': {'requests': 1000, 'window': 3600}, # 1000 trading requests per hour
        })
        
        self.ip_blacklist = set()
        self.suspicious_ips = defaultdict(int)
    
    def get_client_ip(self, request):
        """Extract client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        
        return ip
    
    def is_ip_blacklisted(self, ip):
        """Check if IP is blacklisted"""
        # Never blacklist localhost/development IPs
        if ip in ['127.0.0.1', '::1', 'localhost']:
            return False
        return ip in self.ip_blacklist
    
    def add_suspicious_activity(self, ip, reason):
        """Track suspicious activity from IP"""
        # Never track suspicious activity for localhost/development IPs
        if ip in ['127.0.0.1', '::1', 'localhost']:
            return
            
        self.suspicious_ips[ip] += 1
        
        # Auto-blacklist after 5 suspicious activities
        if self.suspicious_ips[ip] >= 5:
            self.ip_blacklist.add(ip)
            logger.warning(f"IP {ip} auto-blacklisted due to suspicious activity: {reason}")
            
            # Store in cache for persistence
            cache.set(f'blacklisted_ip_{ip}', True, 86400)  # 24 hours
    
    def get_rate_limit_key(self, request, limit_type='default'):
        """Generate cache key for rate limiting"""
        ip = self.get_client_ip(request)
        user_id = getattr(request.user, 'id', 'anonymous')
        
        if limit_type == 'login':
            return f'rate_limit:login:{ip}'
        elif limit_type == 'signup':
            return f'rate_limit:signup:{ip}'
        elif limit_type == 'api':
            return f'rate_limit:api:{ip}:{user_id}'
        elif limit_type == 'trading':
            return f'rate_limit:trading:{ip}:{user_id}'
        else:
            return f'rate_limit:default:{ip}:{user_id}'
    
    def check_rate_limit(self, request, limit_type='default'):
        """Check if request exceeds rate limit"""
        ip = self.get_client_ip(request)
        
        # Skip rate limiting for localhost/development IPs
        if ip in ['127.0.0.1', '::1', 'localhost']:
            return True, None
        
        # Check blacklist first
        if self.is_ip_blacklisted(ip):
            return False, "IP address is blacklisted"
        
        # Get rate limit configuration
        limit_config = self.rate_limits.get(limit_type, self.rate_limits['default'])
        max_requests = limit_config['requests']
        window = limit_config['window']
        
        # Generate cache key
        cache_key = self.get_rate_limit_key(request, limit_type)
        
        # Get current request count
        current_requests = cache.get(cache_key, 0)
        
        if current_requests >= max_requests:
            # Rate limit exceeded
            self.add_suspicious_activity(ip, f"Rate limit exceeded for {limit_type}")
            return False, f"Rate limit exceeded. Maximum {max_requests} requests per {window} seconds"
        
        # Increment request count
        cache.set(cache_key, current_requests + 1, window)
        return True, None
    
    def determine_limit_type(self, request):
        """Determine the appropriate rate limit type for the request"""
        path = request.path.lower()
        
        if '/login/' in path or '/auth/login' in path:
            return 'login'
        elif '/signup/' in path or '/auth/signup' in path:
            return 'signup'
        elif '/api/trading/' in path or '/trading/' in path:
            return 'trading'
        elif '/api/' in path:
            return 'api'
        else:
            return 'default'
    
    def process_request(self, request):
        """Process incoming request for rate limiting"""
        # Skip rate limiting for certain paths
        if request.path.startswith('/static/') or request.path.startswith('/media/'):
            return None
        
        # Determine rate limit type
        limit_type = self.determine_limit_type(request)
        
        # Check rate limit
        allowed, message = self.check_rate_limit(request, limit_type)
        
        if not allowed:
            # Log the rate limit violation
            ip = self.get_client_ip(request)
            logger.warning(f"Rate limit violation from IP {ip}: {message}")
            
            # Return rate limit response
            if request.path.startswith('/api/'):
                return JsonResponse({
                    'error': 'Rate limit exceeded',
                    'message': message,
                    'retry_after': 3600  # 1 hour
                }, status=429)
            else:
                return HttpResponse(
                    f"Rate limit exceeded. {message}",
                    status=429,
                    content_type='text/plain'
                )
        
        return None


class CSRFProtectionMiddleware(MiddlewareMixin):
    """
    Enhanced CSRF protection middleware
    """
    
    def process_request(self, request):
        """Process request for CSRF protection"""
        # Skip CSRF for GET requests and static files
        if request.method == 'GET' or request.path.startswith('/static/'):
            return None
        
        # Skip CSRF for API endpoints that use token authentication
        if request.path.startswith('/api/') and 'HTTP_AUTHORIZATION' in request.META:
            return None
        
        # Ensure CSRF token is present for POST/PUT/DELETE requests
        if request.method in ['POST', 'PUT', 'DELETE', 'PATCH']:
            csrf_token = request.META.get('CSRF_COOKIE')
            if not csrf_token:
                # Generate CSRF token if not present
                get_token(request)
        
        return None


class AuditLoggingMiddleware(MiddlewareMixin):
    """
    Middleware for comprehensive audit logging
    """
    
    def __init__(self, get_response=None):
        super().__init__(get_response)
        self.audit_logger = logging.getLogger('audit')
    
    def log_request(self, request, response, duration):
        """Log request details for audit purposes"""
        # Extract request information
        ip = self.get_client_ip(request)
        user = getattr(request.user, 'username', 'anonymous')
        method = request.method
        path = request.path
        status_code = response.status_code
        user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown')
        
        # Log sensitive operations
        if method in ['POST', 'PUT', 'DELETE', 'PATCH']:
            if '/login/' in path or '/auth/' in path:
                self.audit_logger.info(
                    f"AUTH_ATTEMPT|IP:{ip}|User:{user}|Method:{method}|Path:{path}|"
                    f"Status:{status_code}|Duration:{duration:.3f}s|UA:{user_agent}"
                )
            elif '/trading/' in path or '/api/trading/' in path:
                self.audit_logger.info(
                    f"TRADING_OPERATION|IP:{ip}|User:{user}|Method:{method}|Path:{path}|"
                    f"Status:{status_code}|Duration:{duration:.3f}s|UA:{user_agent}"
                )
            elif '/portfolio/' in path or '/api/portfolio/' in path:
                self.audit_logger.info(
                    f"PORTFOLIO_ACCESS|IP:{ip}|User:{user}|Method:{method}|Path:{path}|"
                    f"Status:{status_code}|Duration:{duration:.3f}s|UA:{user_agent}"
                )
        
        # Log errors
        if status_code >= 400:
            self.audit_logger.warning(
                f"ERROR_REQUEST|IP:{ip}|User:{user}|Method:{method}|Path:{path}|"
                f"Status:{status_code}|Duration:{duration:.3f}s|UA:{user_agent}"
            )
    
    def get_client_ip(self, request):
        """Extract client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def process_request(self, request):
        """Record request start time"""
        request.start_time = time.time()
        return None
    
    def process_response(self, request, response):
        """Log request details and add security headers"""
        # Safety check: ensure response is not None
        if response is None:
            logger.error(f"None response detected in AuditLoggingMiddleware for path: {request.path}")
            response = HttpResponse("Internal Server Error", status=500)
        
        if hasattr(request, 'start_time'):
            duration = time.time() - request.start_time
            self.log_request(request, response, duration)
        
        return response


class PerformanceMonitoringMiddleware(MiddlewareMixin):
    """
    Middleware for monitoring request performance
    """
    
    def __init__(self, get_response=None):
        super().__init__(get_response)
        self.performance_logger = logging.getLogger('performance')
    
    def process_request(self, request):
        """Record request start time"""
        request.start_time = time.time()
        return None
    
    def process_response(self, request, response):
        """Log performance metrics"""
        # Safety check: ensure response is not None
        if response is None:
            logger.error(f"None response detected in PerformanceMonitoringMiddleware for path: {request.path}")
            response = HttpResponse("Internal Server Error", status=500)
        
        if hasattr(request, 'start_time'):
            duration = time.time() - request.start_time
            
            # Log slow requests
            if duration > 1.0:  # Log requests taking more than 1 second
                self.performance_logger.warning(
                    f"SLOW_REQUEST|Path:{request.path}|Method:{request.method}|"
                    f"Duration:{duration:.3f}s|User:{getattr(request.user, 'username', 'anonymous')}"
                )
            
            # Add performance header
            response['X-Response-Time'] = f'{duration:.3f}s'
        
        return response


class IPWhitelistMiddleware(MiddlewareMixin):
    """
    Middleware for IP whitelisting (optional security feature)
    """
    
    def __init__(self, get_response=None):
        super().__init__(get_response)
        self.whitelisted_ips = getattr(settings, 'WHITELISTED_IPS', [])
        self.enabled = getattr(settings, 'IP_WHITELIST_ENABLED', False)
    
    def get_client_ip(self, request):
        """Extract client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def is_ip_whitelisted(self, ip):
        """Check if IP is in whitelist"""
        if not self.enabled:
            return True
        
        for whitelisted_ip in self.whitelisted_ips:
            try:
                if ipaddress.ip_address(ip) in ipaddress.ip_network(whitelisted_ip):
                    return True
            except ValueError:
                # If whitelisted_ip is not a valid network, treat as exact IP
                if ip == whitelisted_ip:
                    return True
        
        return False
    
    def process_request(self, request):
        """Check IP whitelist"""
        if not self.enabled:
            return None
        
        ip = self.get_client_ip(request)
        
        if not self.is_ip_whitelisted(ip):
            logger.warning(f"Access denied for non-whitelisted IP: {ip}")
            return HttpResponse(
                "Access denied. IP address not in whitelist.",
                status=403,
                content_type='text/plain'
            )
        
        return None


class RequestValidationMiddleware(MiddlewareMixin):
    """
    Middleware for validating request parameters and preventing attacks
    """
    
    def __init__(self, get_response=None):
        super().__init__(get_response)
        self.max_post_size = getattr(settings, 'MAX_POST_SIZE', 10 * 1024 * 1024)  # 10MB
        self.blocked_user_agents = getattr(settings, 'BLOCKED_USER_AGENTS', [
            'sqlmap', 'nikto', 'nmap', 'scanner', 'bot', 'crawler'
        ])
    
    def validate_request_size(self, request):
        """Validate request size"""
        if request.method == 'POST':
            content_length = request.META.get('CONTENT_LENGTH', 0)
            if content_length and int(content_length) > self.max_post_size:
                return False, f"Request too large. Maximum size: {self.max_post_size} bytes"
        return True, None
    
    def validate_user_agent(self, request):
        """Validate user agent"""
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        
        for blocked_agent in self.blocked_user_agents:
            if blocked_agent in user_agent:
                return False, f"Blocked user agent: {blocked_agent}"
        
        return True, None
    
    def validate_request_headers(self, request):
        """Validate request headers"""
        # Check for suspicious headers
        suspicious_headers = [
            'HTTP_X_FORWARDED_FOR',
            'HTTP_X_REAL_IP',
            'HTTP_CLIENT_IP'
        ]
        
        for header in suspicious_headers:
            if header in request.META:
                value = request.META[header]
                # Basic validation for IP headers
                if header.endswith('_IP') and value:
                    try:
                        ipaddress.ip_address(value)
                    except ValueError:
                        return False, f"Invalid IP address in header {header}: {value}"
        
        return True, None
    
    def process_request(self, request):
        """Validate incoming request"""
        # Validate request size
        valid_size, size_message = self.validate_request_size(request)
        if not valid_size:
            logger.warning(f"Request size validation failed: {size_message}")
            return HttpResponse(size_message, status=413)
        
        # Validate user agent
        valid_ua, ua_message = self.validate_user_agent(request)
        if not valid_ua:
            logger.warning(f"User agent validation failed: {ua_message}")
            return HttpResponse(ua_message, status=403)
        
        # Validate request headers
        valid_headers, header_message = self.validate_request_headers(request)
        if not valid_headers:
            logger.warning(f"Header validation failed: {header_message}")
            return HttpResponse(header_message, status=400)
        
        return None
