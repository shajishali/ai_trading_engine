"""
Context processors for admin dashboard and general site context
"""

from django.urls import reverse
from apps.core.admin_widgets import get_statistics_cards, get_quick_actions, ActivityFeedItem
from apps.core.admin_site import CustomAdminSite


def live_crypto_prices(request):
    """Context processor for live crypto prices (placeholder)"""
    # This can be implemented to provide live crypto prices to templates
    return {}


def market_status(request):
    """Context processor for market status (placeholder)"""
    # This can be implemented to provide market status to templates
    return {}


def admin_dashboard_context(request):
    """Provide context for admin dashboard"""
    try:
        if not request.path.startswith('/admin/'):
            return {}
        
        # Only process for admin pages
        if not hasattr(request, 'user') or not request.user.is_staff:
            return {}
        
        # Get statistics
        admin_site = CustomAdminSite()
        stats = admin_site.get_dashboard_statistics()
        recent_activity = admin_site.get_recent_activity()
        
        # Convert activity to widget items
        activity_items = []
        for activity in recent_activity:
            activity_items.append(ActivityFeedItem(
                message=activity['message'],
                time=activity['time'],
                url=activity.get('url'),
                type=activity.get('type', 'info')
            ))
        
        return {
            'statistics_cards': get_statistics_cards(stats),
            'quick_actions': get_quick_actions(),
            'recent_activity': activity_items,
        }
    except Exception as e:
        # If there's any error, return empty dict to prevent 500 errors
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in admin_dashboard_context: {e}", exc_info=True)
        return {}
