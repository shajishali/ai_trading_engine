"""
Decorators for email verification security
"""
from functools import wraps
from django.core.cache import cache
from django.http import JsonResponse
from django.contrib import messages
from django.shortcuts import redirect
from django.conf import settings


def rate_limit_email_action(action='send_email', max_attempts=None, cooldown_minutes=None):
    """
    Decorator to rate limit email verification actions
    
    Args:
        action: Action name for rate limiting
        max_attempts: Maximum attempts (defaults to settings)
        cooldown_minutes: Cooldown period in minutes (defaults to settings)
    """
    max_attempts = max_attempts or getattr(settings, 'EMAIL_VERIFICATION_MAX_ATTEMPTS', 3)
    cooldown_minutes = cooldown_minutes or getattr(settings, 'EMAIL_VERIFICATION_RESEND_COOLDOWN_MINUTES', 5)
    
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Get user ID for rate limiting
            user_id = None
            if request.user.is_authenticated:
                user_id = request.user.id
            else:
                # For signup, use IP address
                ip = request.META.get('REMOTE_ADDR', 'unknown')
                user_id = f'ip_{ip}'
            
            # Check rate limit
            cache_key = f'email_verification_rate_limit:{action}:{user_id}'
            attempts = cache.get(cache_key, 0)
            
            if attempts >= max_attempts:
                remaining_time = cache.ttl(cache_key)
                if remaining_time > 0:
                    minutes = remaining_time // 60
                    if request.headers.get('Content-Type') == 'application/json' or request.path.startswith('/api/'):
                        return JsonResponse({
                            'error': 'Rate limit exceeded',
                            'message': f'Too many requests. Please wait {minutes} minutes.',
                            'retry_after': remaining_time
                        }, status=429)
                    else:
                        messages.error(
                            request,
                            f'Too many requests. Please wait {minutes} minutes before trying again.'
                        )
                        return redirect('subscription:verification_pending')
            
            # Increment counter
            cache.set(cache_key, attempts + 1, cooldown_minutes * 60)
            
            # Call the view
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator

