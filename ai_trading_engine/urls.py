"""
URL configuration for ai_trading_engine project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework import routers
from apps.core import views

# API Router
router = routers.DefaultRouter()

# Custom error handlers for Phase 5
handler404 = 'apps.core.views.handler404'
handler500 = 'apps.core.views.handler500'
handler403 = 'apps.core.views.handler403'

# Serve static and media files during development FIRST (before catch-all patterns)
# This ensures static files are served before any catch-all patterns like dashboard
static_urlpatterns = []
if settings.DEBUG:
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns
    static_urlpatterns = staticfiles_urlpatterns()
    # Also serve from STATIC_ROOT if it exists
    if settings.STATIC_ROOT:
        static_urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    # Serve media files
    if settings.MEDIA_ROOT:
        static_urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
    path('api/auth/', include('rest_framework.urls')),
    path('accounts/', include('allauth.urls')),
    path('signals/', include('apps.signals.urls')),  # Move signals before dashboard
    path('trading/', include('apps.trading.urls')),
    path('data/', include('apps.data.urls')),
    path('sentiment/', include('apps.sentiment.urls')),
    path('analytics/', include('apps.analytics.urls')),
    path('subscription/', include('apps.subscription.urls')),
    path('core/', include('apps.core.urls')),
    path('', include('apps.dashboard.urls')),  # Dashboard last as catch-all
]

# Add static URL patterns at the BEGINNING so they're checked first
urlpatterns = static_urlpatterns + urlpatterns
