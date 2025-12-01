from django.shortcuts import redirect
from django.urls import reverse
from django.contrib.auth.models import AnonymousUser
from .models import UserProfile

class SubscriptionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Add subscription info to request
        if hasattr(request, 'user') and not isinstance(request.user, AnonymousUser):
            try:
                profile, created = UserProfile.objects.get_or_create(user=request.user)
                request.user_profile = profile
                request.subscription_tier = profile.subscription_plan.tier if profile.subscription_plan else 'free'
                request.subscription_active = profile.is_subscription_active
            except Exception:
                request.user_profile = None
                request.subscription_tier = 'free'
                request.subscription_active = False
        else:
            request.user_profile = None
            request.subscription_tier = 'free'
            request.subscription_active = False

        response = self.get_response(request)
        return response

class SubscriptionRedirectMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        # URLs that don't require subscription
        self.exempt_urls = [
            '/subscription/signup/',
            '/subscription/choice/',
            '/subscription/start_trial/',
            '/subscription/upgrade/',
            '/subscription/management/',
            '/subscription/cancel/',
            '/subscription/webhook/',
            '/accounts/',
            '/admin/',
            '/login/',
            '/logout/',
            '/',
        ]

    def __call__(self, request):
        # Check if user is authenticated and has no active subscription
        if (hasattr(request, 'user') and 
            not isinstance(request.user, AnonymousUser) and
            hasattr(request, 'user_profile') and
            request.user_profile and
            not request.subscription_active):
            
            # Check if current URL is exempt
            current_path = request.path
            is_exempt = any(current_path.startswith(url) for url in self.exempt_urls)
            
            # If not exempt and user has no active subscription, redirect to subscription choice
            if not is_exempt:
                return redirect('subscription:subscription_choice')

        response = self.get_response(request)
        return response



















