"""
Template tags for admin widgets
"""

from django import template
from apps.core.admin_widgets import get_statistics_cards, get_quick_actions

register = template.Library()


@register.simple_tag
def get_dashboard_stats(stats):
    """Get statistics cards for dashboard"""
    return get_statistics_cards(stats)


@register.simple_tag
def get_dashboard_actions():
    """Get quick actions for dashboard"""
    return get_quick_actions()













